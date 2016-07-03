# -*- coding: utf-8 -*-
#
# Copyright (C) Pootle contributors.
#
# This file is a part of the Pootle project. It is distributed under the GPL3
# or later license. See the LICENSE file for a copy of the license and the
# AUTHORS file for copyright and authorship information.

import json
import logging
from collections import OrderedDict

from django.core.management import BaseCommand

from pootle_fs.utils import FSProject


logger = logging.getLogger('pootle.fs')


class Command(BaseCommand):
    help = "Init Pootle FS projects from JSON configuration."

    def add_arguments(self, parser):
        parser.add_argument(
            'config',
            metavar='CONFIG',
            help='JSON encoded configuration')

    def handle(self, **options):
        config = json.loads(options["config"], object_pairs_hook=OrderedDict)

        for project, info in config.items():
            FSProject(project, **info).sync()
