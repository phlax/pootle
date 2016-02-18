# -*- coding: utf-8 -*-
#
# Copyright (C) Pootle contributors.
#
# This file is a part of the Pootle project. It is distributed under the GPL3
# or later license. See the LICENSE file for a copy of the license and the
# AUTHORS file for copyright and authorship information.

import pytest

from django.core.management import call_command
from django.core.management.base import CommandError


@pytest.mark.cmd
@pytest.mark.django_db
def test_export_noargs(capfd, en_tutorial_po_member_updated):
    """Export whole site"""
    call_command('export')
    out, err = capfd.readouterr()
    assert 'Created tutorial-en.zip' in out


@pytest.mark.cmd
@pytest.mark.django_db
def test_export_project(capfd, afrikaans_tutorial, french_tutorial):
    """Export a project"""
    call_command('export', '--project=tutorial')
    out, err = capfd.readouterr()
    assert 'tutorial.zip' in out


@pytest.mark.cmd
@pytest.mark.django_db
def test_export_project_and_lang(capfd, afrikaans_tutorial, french_tutorial):
    """Export a project TP"""
    call_command('export', '--project=tutorial', '--language=af')
    out, err = capfd.readouterr()
    assert 'tutorial-af.zip' in out


@pytest.mark.cmd
@pytest.mark.django_db
def test_export_language(capfd, afrikaans_tutorial, french_tutorial):
    """Export a language"""
    call_command('export', '--language=af')
    out, err = capfd.readouterr()
    assert 'af.zip' in out
    assert 'fr.zip' not in out


@pytest.mark.cmd
@pytest.mark.django_db
def test_export_path(capfd, afrikaans_tutorial, french_tutorial):
    """Export a path

    Testing variants of lang, TP, single PO file and whole site.
    """
    call_command('export', '--path=/af')
    out, err = capfd.readouterr()
    assert 'af.zip' in out
    assert 'fr.zip' not in out

    call_command('export', '--path=/af/tutorial')
    out, err = capfd.readouterr()
    assert 'af-tutorial.zip' in out

    call_command('export', '--path=/af/tutorial/tutorial.po')
    out, err = capfd.readouterr()
    assert 'tutorial.po' in out

    call_command('export', '--path=/')
    out, err = capfd.readouterr()
    assert 'export.zip' in out


@pytest.mark.cmd
@pytest.mark.django_db
def test_export_path_unknown():
    """Export an unknown path"""
    with pytest.raises(CommandError) as e:
        call_command('export', '--path=/af/unknown')
    assert "Could not find store matching '/af/unknown'" in str(e)
