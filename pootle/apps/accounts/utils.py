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

from pootle_store.models import SuggestionStates
from pootle_store.util import FUZZY, UNTRANSLATED


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
    """Merges one user to another.

    The following are fields are updated (model: fields):
    - units: submitted_by, commented_by, reviewed_by
    - submissions: submitter
    - suggestions: user, reviewer

    :param src_user: `User` instance to merge from.
    :param target_user: `User` instance to merge to.
    """

    # Update submitted_by, commented_by and reviewed_by on units
    for unit in src_user.submitted.iterator():
        unit.submitted_by = target_user
        unit.save()

    for unit in src_user.commented.iterator():
        unit.commented_by = target_user
        unit.save()

    for unit in src_user.reviewed.iterator():
        unit.reviewed_by = target_user
        unit.save()

    # Update submitter on submissions
    for submission in src_user.submission_set.iterator():
        submission.submitter = target_user

        # Before we can save we first have to remove existing score_logs for
        # this submission - they will be recreated on save with correct user.
        for score_log in submission.scorelog_set.iterator():
            score_log.delete()
        submission.save()

    # Update user and reviewer on suggestions
    for suggestion in src_user.suggestions.iterator():
        suggestion.user = target_user
        suggestion.save()

    for suggestion in src_user.reviews.iterator():
        suggestion.reviewer = target_user
        suggestion.save()


def remove_units_created_by(user):
    """Remove units created by user that have not had further
    activity.

    :param user: `User` to remove units for.
    """

    # Delete units created by user without submissions by others.
    for unit in user.units_created.iterator():

        # Find submissions by other users on this unit.
        other_subs = unit.submission_set.exclude(submitter=user)

        if not other_subs.exists():
            unit.delete()


def revert_units_state_changed_by(user):
    """Revert unit edits made by a user to previous edit.

    :param user: `User` to revert submissions for.
    """
    for submission in user.unit_states_changed.iterator():
        unit = submission.unit

        # We have to get latest by pk as on mysql precision is not to
        # microseconds - so creation_time can be ambiguous
        if submission != unit.state_changes.latest('pk'):
            # If the unit has been changed more recently we don't need to
            #  revert the unit state.
            submission.delete()
            return
        submission.delete()
        other_submissions = unit.state_changes.exclude(submitter=user)
        if other_submissions.exists():
            new_state = other_submissions.latest().new_value
        else:
            new_state = UNTRANSLATED
        if new_state != unit.state:
            if unit.state == FUZZY:
                unit.markfuzzy(False)
            elif new_state == FUZZY:
                unit.markfuzzy(True)
            unit.state = new_state
            unit._state_updated = True
            unit.save()


def revert_units_edited_by(user):
    """Revert unit edits made by a user to previous edit.

    :param user: `User` to revert submissions for.
    """
    # Revert unit target where user is the last submitter.
    for unit in user.submitted.iterator():

        # Find the last submission by different user that updated the
        # unit.target.
        edits = unit.edits.exclude(submitter=user)

        if edits.exists():
            last_edit = edits.last()
            unit.target_f = last_edit.new_value
            unit.submitted_by = last_edit.submitter
            unit.submitted_on = last_edit.creation_time
        else:
            # if there is no previous submissions set the target to ""
            # and set the unit.submitted_by to None
            unit.target_f = ""
            unit.submitted_by = None
            unit.submitted_on = unit.creation_time
        unit._target_updated = True
        unit.save()


def revert_units_reviewed_by(user):
    """Revert reviews made by user on suggestions to previous state.

    :param user: `User` to revert reviews for.
    """

    # Revert reviews by this user.
    for review in user.suggestion_reviews.iterator():
        suggestion = review.suggestion
        if suggestion.user == user:
            # If the suggestion was also created by this user then remove both
            # review and suggestion.
            suggestion.delete()
        elif suggestion.reviewer == user:
            # If the suggestion is showing as reviewed by the user, then set
            # the suggestion back to pending and update reviewer/review_time.
            suggestion.state = SuggestionStates.PENDING
            suggestion.reviewer = None
            suggestion.review_time = None
            suggestion.save()

        # Remove the review.
        review.delete()

    for unit in user.reviewed.iterator():
        reviews = unit.suggestion_reviews.exclude(submitter=user)
        if reviews.exists():
            previous_review = reviews.latest()
            unit.reviewed_by = previous_review.submitter
            unit.reviewed_on = previous_review.creation_time
        else:
            unit.reviewed_by = None
            unit.reviewed_on = None
        unit._target_updated = True
        unit.save()


def revert_units_commented_by(user):
    """Revert comments made by user on units to previous comment or else
    just remove the comment.

    :param user: `User` to remove submissions for.
    """

    # Revert unit comments where user is latest commenter.
    for unit in user.commented.iterator():

        # Find comments by other users
        comments = unit.comments.exclude(submitter=user)

        if comments.exists():
            # If there are previous comments by others update the
            # translator_comment, commented_by, and commented_on
            last_comment = comments.latest()
            unit.translator_comment = last_comment.new_value
            unit.commented_by = last_comment.submitter
            unit.commented_on = last_comment.creation_time
        else:
            unit.translator_comment = ""
            unit.commented_by = None
            unit.commented_on = None
        unit._comment_updated = True
        unit.save()


def purge_user(user):
    """Purges user from site reverting any changes that they have made.

    The following steps are taken:
    - Delete units created by user and without other submissions.
    - Revert units edited by user.
    - Revert reviews made by user.
    - Revert unit comments by user.
    - Delete any remaining submissions and suggestions.

    :param user: `User` to purge.
    """
    remove_units_created_by(user)
    revert_units_edited_by(user)
    revert_units_reviewed_by(user)
    revert_units_commented_by(user)
    revert_units_state_changed_by(user)

    # Delete remaining submissions.
    for submission in user.submission_set.iterator():
        submission.delete()

    # Delete remaining suggestions.
    for suggestion in user.suggestions.iterator():
        suggestion.delete()
