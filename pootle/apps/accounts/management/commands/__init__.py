#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) Pootle contributors.
#
# This file is a part of the Pootle project. It is distributed under the GPL3
# or later license. See the LICENSE file for a copy of the license and the
# AUTHORS file for copyright and authorship information.

from django.core.management.base import BaseCommand, CommandError


class UserCommand(BaseCommand):
    """Base class for handling user commands."""

    args = "user"

    def create_parser(self, prog_name, subcommand):
        self.prog_name = prog_name
        self.subcommand = subcommand
        return super(UserCommand, self).create_parser(prog_name, subcommand)

    def usage_string(self):
        return self.usage(self.subcommand).replace('%prog', self.prog_name)

    def check_args(self, *args):
        if not len(args) == len(self.args.split(" ")):
            raise CommandError("Wrong number of arguments\n\n%s"
                               % self.usage_string())
