# -*- coding: utf-8 -*-
#
# Copyright (C) Pootle contributors.
#
# This file is a part of the Pootle project. It is distributed under the GPL3
# or later license. See the LICENSE file for a copy of the license and the
# AUTHORS file for copyright and authorship information.

import os
import shutil

import pytest


def _add_stores(tp, n=(3, 2), parent=None):
    from pytest_pootle.factories import StoreFactory, UnitFactory

    from pootle_store.models import UNTRANSLATED, TRANSLATED, FUZZY, OBSOLETE

    for i in range(0, n[0]):
        # add 3 stores
        if parent is None:
            store = StoreFactory(translation_project=tp)
        else:
            store = StoreFactory(translation_project=tp, parent=parent)

        # add 8 units to each store
        for state in [UNTRANSLATED, TRANSLATED, FUZZY, OBSOLETE]:
            for i in range(0, n[1]):
                UnitFactory(store=store, state=state)


@pytest.fixture
def site_matrix_with_subdirs(site_matrix):
    from pytest_pootle.factories import DirectoryFactory

    from pootle_translationproject.models import TranslationProject

    for tp in TranslationProject.objects.all():
        subdir0 = DirectoryFactory(name="subdir0", parent=tp.directory)
        subdir1 = DirectoryFactory(name="subdir1", parent=subdir0)
        _add_stores(tp, n=(2, 1), parent=subdir0)
        _add_stores(tp, n=(1, 1), parent=subdir1)


@pytest.fixture
def site_matrix_with_vfolders(site_matrix):
    from pytest_pootle.factories import VirtualFolderFactory

    VirtualFolderFactory(filter_rules="store0.po")
    VirtualFolderFactory(filter_rules="store1.po")
    vfolder2 = VirtualFolderFactory(
        location='/{LANG}/project0/',
        filter_rules="store0.po")
    vfolder3 = VirtualFolderFactory(
        location='/{LANG}/project0/',
        filter_rules="store1.po")

    vfolder2.is_public = False
    vfolder2.save()
    vfolder3.is_public = False
    vfolder3.save()


@pytest.fixture(scope="session")
def site_root(request, system, settings):

    from pytest_pootle.factories import (
        ProjectFactory, DirectoryFactory, LanguageFactory
    )

    from pootle_app.models import Directory

    # create root and projects directories, first clear the class cache
    if "root" in Directory.objects.__dict__:
        del Directory.objects.__dict__['root']
    if "projects" in Directory.objects.__dict__:
        del Directory.objects.__dict__['projects']
    DirectoryFactory(
        name="projects",
        parent=DirectoryFactory(parent=None, name=""))

    # add 2 languages
    languages = [LanguageFactory() for i in range(0, 2)]

    for i in range(0, 2):
        # add 2 projects
        ProjectFactory(source_language=languages[0])

    def _teardown():
        if "root" in Directory.objects.__dict__:
            del Directory.objects.__dict__['root']
        if "projects" in Directory.objects.__dict__:
            del Directory.objects.__dict__['projects']
        # required to get clean slate 8/
        for trans_dir in os.listdir(settings.POOTLE_TRANSLATION_DIRECTORY):
            if trans_dir.startswith("project"):
                shutil.rmtree(
                    os.path.join(
                        settings.POOTLE_TRANSLATION_DIRECTORY, trans_dir))

    request.addfinalizer(_teardown)


@pytest.fixture(scope="session")
def site_matrix(site_root):
    from pootle_project.models import Project
    from pootle_language.models import Language
    from pytest_pootle.factories import TranslationProjectFactory

    for project in Project.objects.all():
        for language in Language.objects.all():
            # add a TP to the project for each language
            tp = TranslationProjectFactory(project=project, language=language)
            # As there are no files on the FS we have to currently unobsolete
            # the directory
            tp_dir = tp.directory
            tp_dir.obsolete = False
            tp_dir.save()
            _add_stores(tp)


@pytest.fixture
def site_permissions(pootle_content_type, view, hide, suggest,
                     translate, review, administrate, site_root,
                     nobody, default):
    from pootle_app.models import Directory, PermissionSet
    criteria = {
        'user': nobody,
        'directory': Directory.objects.root}
    permission_set = PermissionSet.objects.create(**criteria)
    permission_set.positive_permissions = [view, suggest]
    permission_set.save()

    criteria['user'] = default
    permission_set = PermissionSet.objects.create(**criteria)
    permission_set.positive_permissions = [view, suggest, translate]
    permission_set.save()


@pytest.fixture
def site_matrix_with_announcements(site_matrix):
    from pytest_pootle.factories import AnnouncementFactory

    from pootle_project.models import Project
    from pootle_language.models import Language
    from pootle_translationproject.models import TranslationProject

    for language in Language.objects.all():
        AnnouncementFactory(
            title="Language announcement for: %s" % language,
            body=(
                '<div dir="ltr" lang="en">This is an example announcements. '
                'Just like a real announcement it contains text and some '
                'markup, and even a random link about localisation.<br />'
                '<a href="http://docs.translatehouse.org/languages/'
                'localization-guide/en/latest/guide/start.html">localisation '
                'guide</a>.</div>'),
            virtual_path="announcements/%s" % language.code)

    for project in Project.objects.all():
        AnnouncementFactory(
            title="Project announcement for: %s" % project,
            body=(
                '<div dir="ltr" lang="en">This is an example announcements. '
                'Just like a real announcement it contains text and some '
                'markup, and even a random link about localisation.<br />'
                '<a href="http://docs.translatehouse.org/projects/'
                'localization-guide/en/latest/guide/start.html">localisation '
                'guide</a>.</div>'),
            virtual_path="announcements/projects/%s" % project.code)

    for tp in TranslationProject.objects.all():
        AnnouncementFactory(
            title="TP announcement for: %s" % tp,
            body=(
                '<div dir="ltr" lang="en">This is an example announcements. '
                'Just like a real announcement it contains text and some '
                'markup, and even a random link about localisation.<br />'
                '<a href="http://docs.translatehouse.org/tps/'
                'localization-guide/en/latest/guide/start.html">localisation '
                'guide</a>.</div>'),
            virtual_path="announcements/%s/%s"
            % (tp.language.code, tp.project.code))


@pytest.fixture
def case_sensitive_schema(db):
    from django.db import connection
    from django.apps import apps

    from pootle.core.utils.db import set_mysql_collation_for_column

    cursor = connection.cursor()

    # Language
    set_mysql_collation_for_column(
        apps,
        cursor,
        "pootle_language.Language",
        "code",
        "utf8_general_ci",
        "varchar(50)")

    # Project
    set_mysql_collation_for_column(
        apps,
        cursor,
        "pootle_project.Project",
        "code",
        "utf8_bin",
        "varchar(255)")

    # Directory
    set_mysql_collation_for_column(
        apps,
        cursor,
        "pootle_app.Directory",
        "pootle_path",
        "utf8_bin",
        "varchar(255)")
    set_mysql_collation_for_column(
        apps,
        cursor,
        "pootle_app.Directory",
        "name",
        "utf8_bin",
        "varchar(255)")

    # Store
    set_mysql_collation_for_column(
        apps,
        cursor,
        "pootle_store.Store",
        "pootle_path",
        "utf8_bin",
        "varchar(255)")
    set_mysql_collation_for_column(
        apps,
        cursor,
        "pootle_store.Store",
        "name",
        "utf8_bin",
        "varchar(255)")

    # VirtualFolderTreeItem
    set_mysql_collation_for_column(
        apps,
        cursor,
        "virtualfolder.VirtualFolderTreeItem",
        "pootle_path",
        "utf8_bin",
        "varchar(255)")

    # VirtualFolder
    set_mysql_collation_for_column(
        apps,
        cursor,
        "virtualfolder.VirtualFolder",
        "name",
        "utf8_bin",
        "varchar(70)")
    set_mysql_collation_for_column(
        apps,
        cursor,
        "virtualfolder.VirtualFolder",
        "location",
        "utf8_bin",
        "varchar(255)")
