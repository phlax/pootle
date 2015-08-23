#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) Pootle contributors.
#
# This file is a part of the Pootle project. It is distributed under the GPL3
# or later license. See the LICENSE file for a copy of the license and the
# AUTHORS file for copyright and authorship information.

from django.contrib.auth import get_user_model

from allauth.account.models import EmailAddress

from pootle.core.models import Revision
from pootle_statistics.models import SubmissionTypes


def get_user_by_email(email):
    """Retrieves auser by its email address.

    First it looks up the `EmailAddress` entries, and as a safety measure
    falls back to looking up the `User` entries (these addresses are
    sync'ed in theory).

    :param email: address of the user to look up.
    :return: `User` instance belonging to `email`, `None` otherwise.
    """
    try:
        return EmailAddress.objects.get(email__iexact=email).user
    except EmailAddress.DoesNotExist:
        try:
            User = get_user_model()
            return User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return None


def merge_user(src_user, target_user):
    """Merges one user to another

    The following are updated:
    - units: submitted_by, commented_by, reviewed_by
    - submissions: submitter
    - suggestions: user, reviewer

    :param src_user: `User` instance to merge from
    :param target_user: `User` instance to merge to
    """

    # move units to target_user
    for unit in src_user.submitted.iterator():
        unit.submitted_by = target_user
        unit.save()

    for unit in src_user.commented.iterator():
        unit.commented_by = target_user
        unit.save()

    for unit in src_user.reviewed.iterator():
        unit.reviewed_by = target_user
        unit.save()

    # move submissions to target_user
    for submission in src_user.submission_set.iterator():
        submission.submitter = target_user

        # before we can save we first have to remove existing score_logs for
        # this submission - they will be recreated on save with correct user
        for score_log in submission.scorelog_set.iterator():
            score_log.delete()
        submission.save()

    # move suggestions to target_user
    for suggestion in src_user.suggestions.iterator():
        suggestion.user = target_user
        suggestion.save()

    for suggestion in src_user.reviews.iterator():
        suggestion.reviewer = target_user
        suggestion.save()


def purge_user(user):
    """Purges user from site reverting any changes that they have made

    The following steps are taken:
    - Delete units created by user and without other submissions
    - Revert units where user is last submitter but increment revision
    - Delete any remaining submissions
    - Delete user's suggestions

    :param user: `User` to purge
    """

    submissions = user.submission_set
    units = user.submitted
    suggestions = user.suggestions

    User = get_user_model()
    editing_types = (SubmissionTypes.NORMAL,
                     SubmissionTypes.REVERT,
                     SubmissionTypes.SYSTEM,
                     SubmissionTypes.UNIT_CREATE,
                     SubmissionTypes.UPLOAD)

    # Delete units created by user without submissions by others
    created_by_user = submissions.filter(type=SubmissionTypes.UNIT_CREATE)
    for submission in created_by_user.iterator():

        # TODO: this should prob check only against non-rejection submissions
        other_subs = submission.unit.submission_set.exclude(submitter=user)
        if not other_subs.exists():
            submission.unit.delete()

    # Update units where user is the last submitter
    for unit in units.iterator():
        other_subs = (unit.submission_set
                      .exclude(submitter=user)
                      .exclude(new_value__isnull=True)
                      .filter(type__in=editing_types)
                      .order_by("-creation_time"))
        if other_subs.exists():
            sub = other_subs.first()
            unit.target_f = sub.new_value
            unit.submitted_by = sub.submitter
        else:
            unit.target_f = ""
            unit.submitted_by = User.objects.get_nobody_user()
        unit.revision = Revision.incr()
        unit.save()

    # Delete remaining submissions
    for submission in submissions.iterator():
        submission.delete()

    # Delete remaining suggestions
    for suggestion in suggestions.iterator():
        suggestion.delete()
