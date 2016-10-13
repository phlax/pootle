# -*- coding: utf-8 -*-
#
# Copyright (C) Pootle contributors.
#
# This file is a part of the Pootle project. It is distributed under the GPL3
# or later license. See the LICENSE file for a copy of the license and the
# AUTHORS file for copyright and authorship information.

from collections import Counter, OrderedDict

from django import forms
from django.utils.functional import cached_property

from pootle.core.forms import FormtableForm
from pootle.core.views.widgets import TableSelectMultiple
from pootle.i18n.gettext import ugettext_lazy as _
from pootle_language.models import Language
from pootle_fs.utils import FSPlugin
from pootle_translationproject.models import TranslationProject

from .delegate import (
    fs_plugins, fs_translation_mapping_validator, fs_url_validator)


FS_CHOICES = (
    ("gnu", _("GNU-style"), "/po/<language_code>.<ext>"),
    ("non-gnu",
     _("non GNU-style"),
     "/<language_code>/<dir_path>/<filename>.<ext>"),
    ("django",
     _("Django-style"),
     "/locale/<lang_code>/LC_MESSAGES/<filename>.<ext>"),
    ("custom", _("Custom"), ""))


class ProjectFSAdminForm(forms.Form):

    fs_type = forms.ChoiceField(
        label=_("Filesystem backend"),
        help_text=_("Select a filesystem backend"),
        choices=(),
        widget=forms.Select(
            attrs={'class': 'js-select2'}))
    fs_url = forms.CharField(
        label=_("Backend URL or path"),
        help_text=_(
            "The URL or path to your translation files"))
    translation_mapping_presets = forms.ChoiceField(
        required=False,
        choices=(
            [("", "-----"), ]
            + [(x[0], x[1]) for x in FS_CHOICES]),
        widget=forms.Select(
            attrs={'class': 'js-select2 js-select-fs-mapping'}))
    translation_mapping = forms.CharField(
        label=_("Translation path mapping"),
        help_text=_("Translation path mapping that maps the localisation "
                    "files on the filesystem to stores on Pootle."),
        widget=forms.TextInput(
            attrs={'class': 'js-select-fs-mapping-target'}))

    def should_save(self):
        return self.is_valid()

    @property
    def fs_type_choices(self):
        return (
            (plugin_type, plugin.name or plugin.fs_type)
            for plugin_type, plugin
            in fs_plugins.gather().items())

    def __init__(self, *args, **kwargs):
        self.project = kwargs.pop("project")
        super(ProjectFSAdminForm, self).__init__(*args, **kwargs)
        self.fields["fs_type"].choices = self.fs_type_choices
        self.fields["fs_url"].initial = self.project.config.get("pootle_fs.fs_url")
        self.fields["fs_type"].initial = (
            self.project.config.get("pootle_fs.fs_type"))
        translation_mapping = (
            self.project.config.get("pootle_fs.translation_mappings"))
        if translation_mapping:
            self.fields["translation_mapping"].initial = (
                translation_mapping.get("default"))

    @property
    def fs_path_validator(self):
        return fs_translation_mapping_validator.get()

    @cached_property
    def fs_plugin(self):
        if self.cleaned_data.get("fs_type"):
            return fs_plugins.gather()[self.cleaned_data["fs_type"]]

    @cached_property
    def fs_url_validator(self):
        validator = fs_url_validator.get(self.fs_plugin)
        return validator and validator()

    def clean(self):
        if not hasattr(self, "cleaned_data") or not self.cleaned_data:
            return
        if self.cleaned_data.get("translation_mapping"):
            try:
                self.fs_path_validator(
                    self.cleaned_data["translation_mapping"]).validate()
            except ValueError as e:
                self.add_error("translation_mapping", e)
        if not self.fs_url_validator or not self.cleaned_data.get("fs_url"):
            return
        try:
            self.fs_url_validator.validate(self.cleaned_data["fs_url"])
        except forms.ValidationError as e:
            self.add_error(
                "fs_url",
                forms.ValidationError(
                    "Incorrect URL or path ('%s') for plugin type '%s': %s"
                    % (self.cleaned_data.get("fs_url"),
                       self.cleaned_data.get("fs_type"),
                       e)))

    def save(self):
        self.project.config["pootle_fs.fs_type"] = self.cleaned_data["fs_type"]
        self.project.config["pootle_fs.fs_url"] = self.cleaned_data["fs_url"]
        self.project.config["pootle_fs.translation_mappings"] = dict(
            default=self.cleaned_data["translation_mapping"])


class LangMappingForm(forms.Form):
    remove = forms.BooleanField(required=False)
    pootle_code = forms.ModelChoiceField(
        Language.objects.all(),
        to_field_name="code",
        widget=forms.Select(attrs={'class': 'js-select2'}))
    fs_code = forms.CharField(
        max_length=32)

    def __init__(self, *args, **kwargs):
        self.project = kwargs.pop("project")
        existing_codes = kwargs.pop("existing_codes")
        super(LangMappingForm, self).__init__(*args, **kwargs)
        if existing_codes:
            excluded_codes = (
                [c for c in existing_codes if c != self.initial["pootle_code"]]
                if self.initial and self.initial.get("pootle_code")
                else existing_codes)
            self.fields["pootle_code"].queryset = (
                self.fields["pootle_code"].queryset.exclude(
                    code__in=excluded_codes))


class BaseLangMappingFormSet(forms.BaseFormSet):

    def __init__(self, *args, **kwargs):
        self.project = kwargs.pop("project")
        mappings = self.project.config.get("pootle.core.lang_mapping", {})
        if mappings:
            kwargs["initial"] = [
                dict(pootle_code=v, fs_code=k)
                for k, v in mappings.items()]
        super(BaseLangMappingFormSet, self).__init__(*args, **kwargs)

    @property
    def cleaned_mapping(self):
        mapping = OrderedDict()
        for mapped in self.cleaned_data:
            if not mapped or mapped["remove"]:
                continue
            mapping[mapped["fs_code"]] = mapped["pootle_code"].code
        return mapping

    def save(self):
        self.project.config["pootle.core.lang_mapping"] = self.cleaned_mapping

    def clean(self):
        if any(self.errors):
            return
        fs_counter = Counter([v["fs_code"] for v in self.cleaned_data if v])
        if set(fs_counter.values()) != set([1]):
            raise forms.ValidationError(
                _("Filesystem language codes must be unique"))
        pootle_counter = Counter([v["pootle_code"] for v in self.cleaned_data if v])
        if set(pootle_counter.values()) != set([1]):
            raise forms.ValidationError(
                _("Pootle language mappings must be unique"))

    def get_form_kwargs(self, index):
        kwargs = super(BaseLangMappingFormSet, self).get_form_kwargs(index)
        kwargs["project"] = self.project
        kwargs["existing_codes"] = (
            [i["pootle_code"] for i in self.initial]
            if self.initial
            else [])
        return kwargs


LangMappingFormSet = forms.formset_factory(
    LangMappingForm,
    formset=BaseLangMappingFormSet)


class ProjectFSStateBaseForm(FormtableForm):
    form_class = "pootle-fs-config-form"
    filter_state = forms.ChoiceField(
        choices=(),
        required=False,
        widget=forms.Select(
            attrs={'class': 'js-select2'}))
    filter_language = forms.ModelChoiceField(
        queryset=TranslationProject.objects.none(),
        required=False,
        widget=forms.Select(
            attrs={'class': 'js-select2'}))

    def __init__(self, *args, **kwargs):
        self.project = kwargs.pop("project")
        super(ProjectFSStateBaseForm, self).__init__(*args, **kwargs)
        self.fields["filter_state"].choices = getattr(self, "state_choices", ())
        self.fields["filter_language"].queryset = (
            self.project.translationproject_set.all())

    @property
    def fs(self):
        return FSPlugin(self.project)

    @property
    def items_to_save(self):
        return (
            [x[0] for x in self.fields[self.search_field].queryset]
            if self.cleaned_data["select_all"]
            else self.cleaned_data[self.search_field])

    @cached_property
    def state(self):
        return self.fs.state()

    def count_choices(self, choices):
        return len(choices)

    def search(self):
        if not self.is_valid():
            return self.fields[self.paginate_field].choices
        choices = []
        tp = (
            self.cleaned_data["filter_language"]
            if self.cleaned_data.get("filter_language")
            else None)
        state = (
            self.cleaned_data["filter_state"]
            if self.cleaned_data.get("filter_state")
            else None)
        for path, choice in self.fields[self.paginate_field].choices:
            if tp and not choice.pootle_path.startswith(tp.pootle_path):
                continue
            if state and not choice.state_type == state:
                continue
            choices.append((path, choice))
        return choices


class ProjectFSStateUntrackedForm(ProjectFSStateBaseForm):
    search_field = "untracked"
    paginate_field = "untracked"
    action_choices = (
        ("rm", "Remove both Pootle and filesystem store"),
        ("fetch", "Fetch the version from the Filesystem"),
        ("add", "Add the version from Pootle"))
    untracked = forms.MultipleChoiceField(
        required=False,
        widget=TableSelectMultiple(
            item_attrs=["pootle_path", "fs_path", "state_type"]),
        choices=[])

    def __init__(self, *args, **kwargs):
        super(ProjectFSStateUntrackedForm, self).__init__(*args, **kwargs)
        self.fields["untracked"].choices = [
            ("%s%s" % (assoc.state_type, assoc.pootle_path), assoc)
            for assoc in self.state_untracked]

    @property
    def state_choices(self):
        return (
            ("", ""),
            ("conflict_untracked", _("Untracked conflicting")),
            ("pootle_untracked", _("Untracked Pootle stores")),
            ("fs_untracked", _("Untracked files")))

    @property
    def state_untracked(self):
        return (
            self.state["conflict_untracked"]
            + self.state["pootle_untracked"]
            + self.state["fs_untracked"])

    def save(self):
        for item in self.items_to_save:
            # TODO: check still in same state?
            # state_type = item.split("/")[0]
            pootle_path = "/".join(item.split("/")[1:])
            pootle_path = "/%s" % pootle_path
            self.fs.rm(pootle_path=pootle_path, force=True)


class ProjectFSStateUnsyncedForm(ProjectFSStateBaseForm):
    search_field = "unsynced"
    paginate_field = "unsynced"
    action_choices = (
        ("unstage", "Unstage any actions"),
        ("sync", "Synchronize Pootle and the filesystem now"))
    unsynced = forms.MultipleChoiceField(
        required=False,
        widget=TableSelectMultiple(
            item_attrs=["pootle_path", "fs_path", "state_type"]),
        choices=[])

    def __init__(self, *args, **kwargs):
        super(ProjectFSStateUnsyncedForm, self).__init__(*args, **kwargs)
        self.fields["unsynced"].choices = [
            ("%s%s" % (assoc.state_type, assoc.pootle_path), assoc)
            for assoc in self.state_unsynced]

    @property
    def state_choices(self):
        return (
            ("", ""),
            ("remove", _("Files marked for removal")),
            ("pootle_ahead", _("Update from pootle")),
            ("fs_ahead", _("Update from filesystem")))

    @property
    def state_unsynced(self):
        return (
            self.state["remove"]
            + self.state["pootle_ahead"]
            + self.state["fs_ahead"])

    def save(self):
        for item in self.items_to_save:
            # TODO: check still in same state?
            # state_type = item.split("/")[0]
            pootle_path = "/".join(item.split("/")[1:])
            pootle_path = "/%s" % pootle_path
            if self.cleaned_data["actions"] == "unstage":
                self.fs.unstage(pootle_path=pootle_path)


class ProjectFSStateConflictingForm(ProjectFSStateBaseForm):
    search_field = "conflicting"
    action_choices = (
        ("unstage", "Unstage any actions"),
        ("sync", "Synchronize Pootle and the filesystem now"))
    paginate_field = "conflicting"
    conflicting = forms.MultipleChoiceField(
        required=False,
        widget=TableSelectMultiple(
            item_attrs=["pootle_path", "fs_path", "state_type"]),
        choices=[])

    def __init__(self, *args, **kwargs):
        super(ProjectFSStateConflictingForm, self).__init__(*args, **kwargs)
        self.fields["conflicting"].choices = [
            ("%s%s" % (assoc.state_type, assoc.pootle_path), assoc)
            for assoc in self.state_conflicting]

    @property
    def state_conflicting(self):
        return self.state["conflict"]

    def save(self):
        for item in self.items_to_save:
            # TODO: check still in same state?
            # state_type = item.split("/")[0]
            pootle_path = "/".join(item.split("/")[1:])
            pootle_path = "/%s" % pootle_path
            self.fs.rm(pootle_path=pootle_path, force=True)
