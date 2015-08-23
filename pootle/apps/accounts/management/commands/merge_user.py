#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) Pootle contributors.
#
# This file is a part of the Pootle project. It is distributed under the GPL3
# or later license. See the LICENSE file for a copy of the license and the
# AUTHORS file for copyright and authorship information.

from django.contrib.auth import get_user_model
from django.core.management.base import CommandError

from . import UserCommand
import accounts


class Command(UserCommand):
    args = "user other_user"
    help = "Merge user to other_user"

    def handle(self, *args, **kwargs):
        self.check_args(*args)
        User = get_user_model()
        try:
            src_user = User.objects.get(username=args[0])
        except User.DoesNotExist:
            raise CommandError("User %s does not exist" % args[0])
        try:
            target_user = User.objects.get(username=args[1])
        except User.DoesNotExist:
            raise CommandError("User %s does not exist" % args[1])
        accounts.utils.merge_user(src_user, target_user)
