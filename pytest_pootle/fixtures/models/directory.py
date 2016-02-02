#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) Pootle contributors.
#
# This file is a part of the Pootle project. It is distributed under the GPL3
# or later license. See the LICENSE file for a copy of the license and the
# AUTHORS file for copyright and authorship information.

import pytest


@pytest.fixture(scope="session")
def root(system):
    """Require the root directory."""
    from pootle_app.models import Directory
    return Directory.objects.get(pootle_path="/")


@pytest.fixture(scope="session")
def projects(root):
    """Require the projects directory."""
    from pootle_app.models import Directory
    return Directory.objects.get(pootle_path="/projects/")

    from pootle_app.models import Directory

    dirs = Directory.objects

    if "projects" in dirs.__dict__:
        del dirs.__dict__['projects']

    projects, created = dirs.get_or_create(name='projects',
                                           parent=root)
    projects.save()
    return projects
