# -*- coding: utf-8 -*-
#
# Copyright (C) Pootle contributors.
#
# This file is a part of the Pootle project. It is distributed under the GPL3
# or later license. See the LICENSE file for a copy of the license and the
# AUTHORS file for copyright and authorship information.

import os

import pytest

from django.core.management import call_command

from pootle_project.models import Project


@pytest.mark.cmd
@pytest.mark.django_db
def test_update_stores_noargs(capfd, en_tutorial_po_member_updated):
    """Site wide update_stores"""
    if en_tutorial_po_member_updated.file.exists():
        os.remove(en_tutorial_po_member_updated.file.path)
    call_command('update_stores')
    out, err = capfd.readouterr()
    # Store and Unit are deleted as there are no files on disk
    # SO - Store Obsolete
    assert 'system\tSO\t/en/tutorial/tutorial.po' in err
    # UO - Unit Obsolete
    assert 'system\tUO\ten' in err

    # Repeat and we should have zero output
    call_command('update_stores')
    out, err = capfd.readouterr()
    assert 'system\tSO' not in err
    assert 'system\tUO' not in err


@pytest.mark.cmd
@pytest.mark.django_db
def test_update_stores_project_tree_none(capfd):
    project = Project.objects.get(code="project0")
    project.treestyle = "none"
    project.save()
    call_command("update_stores", "--project", project.code)
    out, err = capfd.readouterr()
    assert not out
    assert not err
