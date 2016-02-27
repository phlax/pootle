# -*- coding: utf-8 -*-
#
# Copyright (C) Pootle contributors.
#
# This file is a part of the Pootle project. It is distributed under the GPL3
# or later license. See the LICENSE file for a copy of the license and the
# AUTHORS file for copyright and authorship information.

import logging
import os

from django.utils.functional import cached_property

from translate.storage.factory import getclass

from pootle_app.models import Directory
from pootle_language.models import Language
from pootle_statistics.models import SubmissionTypes
from pootle_store.models import Store
from pootle_store import models as store_models
from pootle_translationproject.models import TranslationProject

from .models import FS_WINS, POOTLE_WINS, StoreFS


logger = logging.getLogger(__name__)


class FSFile(object):

    def __init__(self, store_fs):
        """
        :param store_fs: ``FSStore`` object
        """
        if not isinstance(store_fs, StoreFS):
            raise TypeError(
                "pootle_fs.FSFile expects a StoreFS")
        self.store_fs = store_fs
        self.pootle_path = store_fs.pootle_path
        self.path = store_fs.path

    def __str__(self):
        return "<%s: %s::%s>" % (
            self.__class__.__name__, self.pootle_path, self.path)

    @property
    def directory(self):
        if self.store_fs.store:
            return self.store_fs.store.parent
        if not self.translation_project:
            return
        directory = self.translation_project.directory
        if self.directory_path:
            for subdir in self.directory_path.split("/"):
                try:
                    directory = directory.child_dirs.get(name=subdir)
                except Directory.DoesNotExist:
                    return
        return directory

    @property
    def directory_path(self):
        return '/'.join(self.pootle_path.split("/")[3:-1])

    @property
    def exists(self):
        return os.path.exists(self.file_path)

    @property
    def filename(self):
        return self.pootle_path.split("/")[-1]

    @property
    def file_path(self):
        return os.path.join(
            self.fs.plugin.local_fs_path,
            self.path.strip("/"))

    @cached_property
    def fs(self):
        return self.project.fs.get()

    @property
    def fs_changed(self):
        latest_hash = self.latest_hash
        return (
            latest_hash
            and (
                latest_hash
                != self.store_fs.last_sync_hash))

    @cached_property
    def language(self):
        if self.store_fs.store:
            return self.store_fs.store.translation_project.language
        return Language.objects.get(code=self.pootle_path.split("/")[1])

    @property
    def latest_hash(self):
        raise NotImplementedError

    @property
    def plugin(self):
        return self.fs.plugin

    @property
    def pootle_changed(self):
        return (
            self.store
            and (
                self.store.get_max_unit_revision()
                != self.store_fs.last_sync_revision))

    @property
    def project(self):
        return self.store_fs.project

    @property
    def store(self):
        if self.store_fs.store:
            return self.store_fs.store
        try:
            return Store.objects.get(
                pootle_path=self.pootle_path)
        except Store.DoesNotExist:
            return

    @property
    def translation_project(self):
        if self.store_fs.store:
            return self.store_fs.store.translation_project
        try:
            return self.project.translationproject_set.get(
                language=self.language)
        except TranslationProject.DoesNotExist:
            return

    def add(self):
        logger.debug("Adding file: %s" % self.path)
        self.store_fs.resolve_conflict = POOTLE_WINS
        self.store_fs.save()

    def create_store(self):
        """
        Creates a ```Store``` and if necessary the ```TranslationProject```
        parent ```Directories```
        """
        if not self.translation_project:
            logger.debug(
                "Created translation project: %s/%s"
                % (self.project.code, self.language.code))
            tp = TranslationProject.objects.create(
                project=self.project,
                language=self.language)
            tp.directory.obsolete = False
            tp.directory.save()
        if not self.directory:
            directory = self.translation_project.directory
            if self.directory_path:
                for subdir in self.directory_path.split("/"):
                    directory, created = directory.child_dirs.get_or_create(
                        name=subdir)
                    if created:
                        logger.debug(
                            "Created directory: %s" % directory.path)
        if not self.store:
            store, created = Store.objects.get_or_create(
                parent=self.directory, name=self.filename,
                translation_project=self.translation_project)
            if created:
                store.save()
                logger.debug("Created Store: %s" % store.pootle_path)
        if not self.store_fs.store == self.store:
            self.store_fs.store = self.store
            self.store_fs.save()

    def delete(self):
        """
        Delete the file from FS and Pootle

        This does not commit/push
        """
        store = self.store
        if store and store.pk:
            store.makeobsolete()
        if self.store_fs.pk:
            self.store_fs.delete()
        self.remove_file()

    def fetch(self):
        """
        Called when FS file is fetched
        """
        logger.debug("Fetching file: %s" % self.path)
        if self.store and not self.store_fs.store:
            self.store_fs.store = self.store
        self.store_fs.resolve_conflict = FS_WINS
        self.store_fs.save()
        return self.store_fs

    def on_sync(self, latest_hash, revision):
        """
        Called after FS and Pootle have been synced
        """
        self.store_fs.resolve_conflict = None
        self.store_fs.staged_for_merge = False
        self.store_fs.last_sync_hash = latest_hash
        self.store_fs.last_sync_revision = revision
        self.store_fs.save()
        logger.debug("File synced: %s" % self.path)

    def pull(self):
        """
        Pull FS file into Pootle
        """
        current_hash = self.latest_hash
        last_hash = self.store_fs.last_sync_hash
        if self.store and last_hash == current_hash:
            return
        logger.debug("Pulling file: %s" % self.path)
        if not self.store:
            self.create_store()
        if not self.store_fs.store == self.store:
            self.store_fs.store = self.store
            self.store_fs.save()
        self.sync_to_pootle()

    def push(self, debug=False):
        """
        Push Pootle ``Store`` into FS
        """
        current_revision = self.store.get_max_unit_revision()
        last_revision = self.store_fs.last_sync_revision
        if self.exists and last_revision == current_revision:
            return
        logger.debug("Pushing file: %s" % self.path)
        directory = os.path.dirname(self.store_fs.file.file_path)
        if not os.path.exists(directory):
            logger.debug("Creating directory: %s" % directory)
            os.makedirs(directory)
        self.sync_from_pootle()

    def read(self):
        with open(self.file_path) as f:
            return f.read()

    def remove_file(self):
        if self.exists:
            os.unlink(self.file_path)

    def sync_from_pootle(self):
        """
        Update FS file with the serialized content from Pootle ```Store```
        """
        with open(self.file_path, "w") as f:
            f.write(self.store.serialize())
        logger.debug("Pushed file: %s" % self.path)

    def sync_to_pootle(self, pootle_wins=False, merge=False):
        """
        Update Pootle ``Store`` with the parsed FS file.
        """
        resolve_conflict = (
            pootle_wins
            and store_models.POOTLE_WINS
            or store_models.FILE_WINS)
        with open(self.file_path) as f:
            if merge:
                revision = self.store_fs.last_sync_revision
            else:
                revision = self.store.get_max_unit_revision() + 1
            tmp_store = getclass(f)(f.read())
            self.store.update(
                tmp_store,
                submission_type=SubmissionTypes.UPLOAD,
                user=self.plugin.pootle_user,
                store_revision=revision,
                resolve_conflict=resolve_conflict)
        logger.debug("Pulled file: %s" % self.path)
        self.on_sync(
            self.latest_hash,
            self.store.get_max_unit_revision())
