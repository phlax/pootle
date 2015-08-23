#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) Pootle contributors.
#
# This file is a part of the Pootle project. It is distributed under the GPL3
# or later license. See the LICENSE file for a copy of the license and the
# AUTHORS file for copyright and authorship information.

import pytest

import accounts

from .store import _update_from_upload_file


def _create_submission_and_suggestion(store, user,
                                      filename=None, suggestion=None):
    filename = filename or "tests/data/po/tutorial/en/tutorial_update.po"

    # Update store as user
    _update_from_upload_file(store, filename, user=user)

    # Add a suggestion
    unit = store.units.first()
    unit.add_suggestion(suggestion or 'SUGGESTION', user=user)

    return unit


def _test_user_merged(unit, src_user, target_user):
    # TODO: test reviews and comments

    if src_user.id:
        assert src_user.submitted.count() == 0
        assert src_user.suggestions.count() == 0

    assert target_user.submitted.first() == unit
    assert target_user.suggestions.first() == unit.get_suggestions().first()


@pytest.mark.django_db
def test_merge_user(en_tutorial_po, member, member2):
    """Test merging user to another user."""
    unit = _create_submission_and_suggestion(en_tutorial_po, member)
    accounts.utils.merge_user(member, member2)
    _test_user_merged(unit, member, member2)


@pytest.mark.django_db
def test_delete_user(en_tutorial_po, member, nobody):
    """Test default behaviour of User.delete - merge to nobody"""
    unit = _create_submission_and_suggestion(en_tutorial_po, member)
    member.delete()
    _test_user_merged(unit, member, nobody)


def _test_user_purging(store, member, member2, purge):
    assert store.units.first().target_f == ""
    assert store.get_max_unit_revision() == 1

    # member updates first unit, adding a suggestion
    _create_submission_and_suggestion(store, member)
    assert store.get_max_unit_revision() == 3
    assert store.units.count() == 1
    assert store.units.first().target_f == "Hello, world UPDATED"
    assert store.units.first().submitted_by == member
    assert store.units.first().get_suggestions().count() == 1

    # (evil) member2 updates with:
    #   - changes 1st unit
    #   - adds another unit
    #   - adds another suggestion
    filename = "tests/data/po/tutorial/en/tutorial_update_evil.po"
    _create_submission_and_suggestion(store,
                                      member2,
                                      filename=filename,
                                      suggestion="EVIL SUGGESTION")
    assert store.get_max_unit_revision() == 5
    assert store.units.count() == 2
    assert store.units.first().get_suggestions().count() == 2
    assert store.units.first().target_f == "Hello, world EVIL"
    assert store.units.first().submitted_by == member2
    assert store.units[1].target_f == "Goodbye, world EVIL"
    assert store.units[1].submitted_by == member2

    # purge evil member2
    purge(member2)

    # back to original update - although revision count has increased
    assert store.get_max_unit_revision() == 6
    assert store.units.count() == 1
    assert store.units.first().get_suggestions().count() == 1
    assert (store.units.first().get_suggestions().first().target_f
            == 'SUGGESTION')
    assert store.units.first().target_f == "Hello, world UPDATED"
    assert store.units.first().submitted_by == member


@pytest.mark.django_db
def test_purge_user(en_tutorial_po, member, member2):
    """Test purging user using `purge_user` function"""
    _test_user_purging(en_tutorial_po, member, member2,
                       lambda m: accounts.utils.purge_user(m))


@pytest.mark.django_db
def test_delete_purge_user(en_tutorial_po, member, member2):
    """Test purging user using `User.delete(purge=True)`"""
    _test_user_purging(en_tutorial_po, member, member2,
                       lambda m: m.delete(purge=True))
