#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) Pootle contributors.
#
# This file is a part of the Pootle project. It is distributed under the GPL3
# or later license. See the LICENSE file for a copy of the license and the
# AUTHORS file for copyright and authorship information.

import pytest

from pytest_pootle.factories import UserFactory
from pytest_pootle.fixtures.models.permission_set import _require_permission_set
from pytest_pootle.utils import items_equal

from pootle_app.models import PermissionSet
from pootle_project.models import Project


@pytest.mark.django_db
def test_no_root_view_permissions(nobody, default, admin, view,
                                  project_foo, project_bar):
    """Tests user-accessible projects when there are no permissions set at
    the root.
    """
    PermissionSet.objects.all().delete()

    ALL_PROJECTS = [project.code for project in Project.objects.all()]

    ADDED_PROJECTS = ["foo", "bar"]

    foo_user = UserFactory.create(username='foo')
    bar_user = UserFactory.create(username='bar')

    # By setting explicit `view` permissions for `foo_user` in `project_foo`,
    # only `foo_user` will be able to access that project
    _require_permission_set(foo_user, project_foo.directory, [view])

    admin_projects = Project.accessible_by_user(admin)
    assert admin_projects == ALL_PROJECTS

    assert project_foo.code in Project.accessible_by_user(foo_user)
    assert project_foo.code not in Project.accessible_by_user(bar_user)

    assert items_equal(Project.accessible_by_user(bar_user), [])
    assert items_equal(Project.accessible_by_user(default), [])
    assert items_equal(Project.accessible_by_user(nobody), [])

    # Now let's allow showing `project_bar` to all registered users, but keep
    # `project_foo` visible only to `foo_user`.
    _require_permission_set(default, project_bar.directory, [view])

    assert items_equal(Project.accessible_by_user(admin), ALL_PROJECTS)
    assert items_equal(Project.accessible_by_user(foo_user), ADDED_PROJECTS)
    assert items_equal(
        Project.accessible_by_user(bar_user),
        [project_bar.code])
    assert items_equal(Project.accessible_by_user(default), [project_bar.code])
    assert items_equal(Project.accessible_by_user(nobody), [])


@pytest.mark.django_db
def test_root_view_permissions(nobody, default, admin, view,
                               project_foo, project_bar, root):
    """Tests user-accessible projects with view permissions at the root."""

    PermissionSet.objects.all().delete()

    foo_user = UserFactory.create(username='foo')
    bar_user = UserFactory.create(username='bar')

    # We'll only give `bar_user` access to all projects server-wide
    _require_permission_set(bar_user, root, [view])

    assert (
        sorted(Project.accessible_by_user(admin))
        == sorted(Project.objects.values_list("code", flat=True)))
    assert (
        sorted(Project.accessible_by_user(bar_user))
        == sorted(Project.objects.values_list("code", flat=True)))

    assert items_equal(Project.accessible_by_user(foo_user), [])
    assert items_equal(Project.accessible_by_user(default), [])
    assert items_equal(Project.accessible_by_user(nobody), [])

    # Now we'll also allow `foo_user` access `project_foo`
    _require_permission_set(foo_user, project_foo.directory, [view])

    assert items_equal(
        Project.accessible_by_user(foo_user),
        [project_foo.code])

    # Let's change server-wide defaults: all registered users have access to
    # all projects. `foo_user`, albeit having explicit access for
    # `project_foo`, will be able to access any project because they fall back
    # and extend with the defaults.
    _require_permission_set(default, root, [view])

    assert (
        sorted(Project.accessible_by_user(admin))
        == sorted(Project.objects.values_list("code", flat=True)))
    assert (
        sorted(Project.accessible_by_user(foo_user))
        == sorted(Project.objects.values_list("code", flat=True)))
    assert (
        sorted(Project.accessible_by_user(bar_user))
        == sorted(Project.objects.values_list("code", flat=True)))
    assert (
        sorted(Project.accessible_by_user(default))
        == sorted(Project.objects.values_list("code", flat=True)))

    assert items_equal(Project.accessible_by_user(nobody), [])

    # Let's give anonymous users access to all projects too
    _require_permission_set(nobody, root, [view])

    assert (
        sorted(Project.accessible_by_user(nobody))
        == sorted(Project.objects.values_list("code", flat=True)))


@pytest.mark.django_db
def test_no_root_hide_permissions(nobody, default, admin, hide, view,
                                  project_foo, project_bar, root):
    """Tests user-accessible projects when there are no `hide` permissions
    set at the root.
    """

    PermissionSet.objects.all().delete()

    foo_user = UserFactory.create(username='foo')
    bar_user = UserFactory.create(username='bar')

    # By default everyone has access to projects
    _require_permission_set(default, root, [view])
    _require_permission_set(nobody, root, [view])

    # Make `project_foo` is inaccessible to anon users...
    _require_permission_set(
        nobody, project_foo.directory,
        negative_permissions=[hide])

    assert (
        sorted(Project.accessible_by_user(admin))
        == sorted(Project.objects.values_list("code", flat=True)))
    assert (
        sorted(Project.accessible_by_user(default))
        == sorted(Project.objects.values_list("code", flat=True)))
    assert (
        sorted(Project.accessible_by_user(foo_user))
        == sorted(Project.objects.values_list("code", flat=True)))
    assert (
        sorted(Project.accessible_by_user(bar_user))
        == sorted(Project.objects.values_list("code", flat=True)))

    assert project_bar.code in Project.accessible_by_user(nobody)
    assert project_foo.code not in Project.accessible_by_user(nobody)

    # Make `project_foo` inaccessible to registered users...
    _require_permission_set(
        default, project_foo.directory,
        negative_permissions=[hide])

    assert project_bar.code in Project.accessible_by_user(default)
    assert project_foo.code not in Project.accessible_by_user(default)

    assert project_bar.code in Project.accessible_by_user(nobody)
    assert project_foo.code not in Project.accessible_by_user(nobody)

    assert project_bar.code in Project.accessible_by_user(foo_user)
    assert project_foo.code not in Project.accessible_by_user(foo_user)

    assert project_bar.code in Project.accessible_by_user(bar_user)
    assert project_foo.code not in Project.accessible_by_user(bar_user)

    # Make `project_foo` accessible for `foo_user`
    _require_permission_set(
        foo_user, project_foo.directory, [view])

    assert project_foo.code in Project.accessible_by_user(foo_user)

    # Make `project_bar` inaccessible for anonymous users
    _require_permission_set(
        nobody, project_bar.directory,
        negative_permissions=[hide])
    assert project_bar.code not in Project.accessible_by_user(nobody)


@pytest.mark.django_db
def __test_root_hide_permissions(nobody, default, admin, hide, view,
                                 project_foo, project_bar, root, projects):
    """Tests user-accessible projects when there are `hide` permissions
    set at the root.
    """
    PermissionSet.objects.all().delete()

    ALL_PROJECTS = Project.objects.all()

    foo_user = UserFactory.create(username='foo')
    bar_user = UserFactory.create(username='bar')

    # By default everyone has access to root
    # _require_permission_set(default, root, [view])
    # _require_permission_set(nobody, root, [view])

    # Hide projects for default/nobody
    _require_permission_set(default, projects, negative_permissions=[hide])
    _require_permission_set(nobody, projects, negative_permissions=[hide])

    assert (
        sorted(Project.accessible_by_user(admin))
        == sorted(Project.objects.values_list("code", flat=True)))

    Project.accessible_by_user(default)

    assert items_equal(Project.accessible_by_user(default), [])
    assert items_equal(Project.accessible_by_user(nobody), [])
    assert items_equal(Project.accessible_by_user(foo_user), [])
    assert items_equal(Project.accessible_by_user(bar_user), [])

    # Now let's make `project_foo` accessible to `foo_user`.
    _require_permission_set(foo_user, project_foo.directory, [view])

    assert (
        sorted(Project.accessible_by_user(admin))
        == sorted(Project.objects.values_list("code", flat=True)))

    assert items_equal(Project.accessible_by_user(default), [])
    assert items_equal(Project.accessible_by_user(nobody), [])

    assert project_foo.code in Project.accessible_by_user(foo_user)

    assert items_equal(Project.accessible_by_user(bar_user), [])

    # Making projects accessible for anonymous users should open the door for
    # everyone
    _require_permission_set(nobody, root, [view])

    assert items_equal(Project.accessible_by_user(admin), ALL_PROJECTS)
    assert items_equal(Project.accessible_by_user(default), ALL_PROJECTS)
    assert items_equal(Project.accessible_by_user(nobody), ALL_PROJECTS)
    assert items_equal(Project.accessible_by_user(foo_user), ALL_PROJECTS)
    assert items_equal(Project.accessible_by_user(bar_user), ALL_PROJECTS)
