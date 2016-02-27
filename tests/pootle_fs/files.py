#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) Pootle contributors.
#
# This file is a part of the Pootle project. It is distributed under the GPL3
# or later license. See the LICENSE file for a copy of the license and the
# AUTHORS file for copyright and authorship information.

import os

import pytest

from pootle_language.models import Language
from pootle_translationproject.models import TranslationProject

from pootle_fs.files import FSFile
from pootle_fs.models import StoreFS


def _test_store_fs_files(src_path):
    for store_fs in StoreFS.objects.all():
        fs_file = FSFile(store_fs)
        assert fs_file.fs == store_fs.fs
        assert fs_file.project == store_fs.project
        assert fs_file.store == store_fs.store
        assert fs_file.pootle_path == store_fs.pootle_path
        assert fs_file.path == store_fs.path

        # latest hash must be implemented by the plugin's file class
        with pytest.raises(NotImplementedError):
            fs_file.latest_hash

        if fs_file.exists:
            src_file_path = os.path.join(src_path, fs_file.path.strip("/"))
            with open(src_file_path, "r") as src_file:
                assert src_file.read() == fs_file.read()

        assert (
            str(fs_file)
            == ("<%s: %s::%s>"
                % (fs_file.__class__.__name__,
                   fs_file.pootle_path, fs_file.path)))
        directory = fs_file.directory
        if directory:
            if store_fs.store:
                assert directory == store_fs.store.parent
        else:
            assert not store_fs.store
        assert (
            fs_file.language
            == Language.objects.get(code=fs_file.pootle_path.split("/")[1]))
        assert (
            fs_file.translation_project
            == TranslationProject.objects.get(
                language=fs_file.language, project=fs_file.project))


@pytest.mark.django
def test_file_instance(fs_plugin_suite):
    with pytest.raises(TypeError):
        FSFile("Not a StoreFS!")
    _test_store_fs_files(fs_plugin_suite.fs.url)


@pytest.mark.django
def test_file_instances_add(fs_plugin_suite):
    plugin = fs_plugin_suite
    plugin.add_translations()
    _test_store_fs_files(plugin.fs.url)
    plugin.add_translations(force=True)
    _test_store_fs_files(plugin.fs.url)
    plugin.sync_translations()
    _test_store_fs_files(plugin.fs.url)


@pytest.mark.django
def test_file_instances_fetch(fs_plugin_suite):
    plugin = fs_plugin_suite
    plugin.fetch_translations()
    _test_store_fs_files(plugin.fs.url)
    plugin.fetch_translations(force=True)
    _test_store_fs_files(plugin.fs.url)
    plugin.sync_translations()
    _test_store_fs_files(plugin.fs.url)


@pytest.mark.django
def test_file_instances_merge_fs(fs_plugin_suite):
    plugin = fs_plugin_suite
    plugin.merge_translations()
    _test_store_fs_files(plugin.fs.url)
    plugin.sync_translations()
    _test_store_fs_files(plugin.fs.url)


@pytest.mark.django
def test_file_instances_merge_pootle(fs_plugin_suite):
    plugin = fs_plugin_suite
    plugin.merge_translations(pootle_wins=True)
    _test_store_fs_files(plugin.fs.url)
    plugin.sync_translations()
    _test_store_fs_files(plugin.fs.url)


@pytest.mark.django
def test_file_instances_rm(fs_plugin_suite):
    plugin = fs_plugin_suite
    plugin.rm_translations()
    _test_store_fs_files(plugin.fs.url)
    plugin.sync_translations()
    _test_store_fs_files(plugin.fs.url)


@pytest.mark.django
def test_file_push_unchanged(fs_plugin_suite, caplog):
    plugin = fs_plugin_suite
    plugin.merge_translations()
    plugin.add_translations()
    plugin.fetch_translations()
    plugin.rm_translations()
    plugin.sync_translations()
    unchanged = plugin.status().get_unchanged()
    synced_logs = [
        x for x in caplog.records()
        if x.levelname == "DEBUG"]

    # test that nothing happens when pushing unchanged files
    # by checking for debug log records that would have been
    # emitted
    for store_fs in unchanged:
        store_fs.file.push(debug=True)
        store_fs.file.pull()

    new_logs = [
        x for x in caplog.records()
        if x.levelname == "DEBUG"
        and x not in synced_logs]
    assert not new_logs
