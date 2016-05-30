# -*- coding: utf-8 -*-
#
# Copyright (C) Pootle contributors.
#
# This file is a part of the Pootle project. It is distributed under the GPL3
# or later license. See the LICENSE file for a copy of the license and the
# AUTHORS file for copyright and authorship information.

from fnmatch import fnmatch

from django.db.models import F, Max
from django.utils.functional import cached_property

from pootle_store.models import Store

from .models import StoreFS
from .utils import StoreFSPathFilter, StorePathFilter


class FSProjectResources(object):

    def __init__(self, project):
        self.project = project

    def __str__(self):
        return (
            "<%s(%s)>"
            % (self.__class__.__name__,
               self.project))

    @property
    def stores(self):
        return Store.objects.filter(
            translation_project__project=self.project)

    @property
    def tracked(self):
        return StoreFS.objects.filter(
            project=self.project).select_related("store")

    @property
    def synced(self):
        return (
            self.tracked.exclude(last_sync_revision__isnull=True)
                        .exclude(last_sync_hash__isnull=True))

    @property
    def unsynced(self):
        return (
            self.tracked.filter(last_sync_revision__isnull=True)
                        .filter(last_sync_hash__isnull=True))

    @property
    def trackable_stores(self):
        return self.stores.exclude(obsolete=True).filter(fs__isnull=True)


class FSProjectStateResources(object):

    def __init__(self, context, pootle_path=None, fs_path=None):
        self.context = context
        self.pootle_path = pootle_path
        self.fs_path = fs_path

    def match_fs_path(self, path):
        if not self.fs_path or fnmatch(path, self.fs_path):
            return path

    def _exclude_staged(self, qs):
        return (
            qs.exclude(staged_for_removal=True)
              .exclude(staged_for_merge=True))

    @cached_property
    def fs_translations(self):
        return sorted(self.context.find_translations(
            fs_path=self.fs_path, pootle_path=self.pootle_path))

    @cached_property
    def resources(self):
        return self.context.resources

    @cached_property
    def store_filter(self):
        return StorePathFilter(
            pootle_path=self.pootle_path)

    @cached_property
    def storefs_filter(self):
        return StoreFSPathFilter(
            pootle_path=self.pootle_path,
            fs_path=self.fs_path)

    @cached_property
    def synced(self):
        """Returns tracked StoreFSs that have sync information, and are not
        currently staged for any kind of operation
        """
        return self.storefs_filter.filtered(
            self._exclude_staged(self.resources.synced))

    @cached_property
    def trackable(self):
        """Stores that are not currently tracked but could be"""
        _trackable = []
        stores = self.store_filter.filtered(self.resources.trackable_stores)
        for store in stores:
            fs_path = self.match_fs_path(
                self.context.get_fs_path(store.pootle_path))
            if fs_path:
                _trackable.append((store, fs_path))
        return _trackable

    @cached_property
    def trackable_paths(self):
        return {
            store.pootle_path: fs_path
            for store, fs_path
            in self.trackable}

    @cached_property
    def tracked(self):
        return self.storefs_filter.filtered(self.resources.tracked)

    @cached_property
    def tracked_paths(self):
        return dict(self.tracked.values_list("path", "pootle_path"))

    @cached_property
    def unsynced(self):
        """Returns tracked StoreFSs that have NO sync information, and are not
        currently staged for any kind of operation
        """
        return self.storefs_filter.filtered(
            self._exclude_staged(
                self.resources.unsynced))

    @cached_property
    def pootle_changed(self):
        return (
            self.synced.annotate(max_revision=Max("store__unit__revision"))
                .exclude(last_sync_revision=F("max_revision")))

    def reload(self):
        for k, v in self.__dict__.items():
            if k in ["context", "pootle_path", "fs_path"]:
                continue
            del self.__dict__[k]
