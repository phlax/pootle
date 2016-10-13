# -*- coding: utf-8 -*-
#
# Copyright (C) Pootle contributors.
#
# This file is a part of the Pootle project. It is distributed under the GPL3
# or later license. See the LICENSE file for a copy of the license and the
# AUTHORS file for copyright and authorship information.

from collections import OrderedDict

from django.contrib import messages
from django.core.paginator import Paginator
from django.core.urlresolvers import reverse

from pootle.core.views.admin import PootleAdminFormView
from pootle.core.views.formtable import Formtable
from pootle.i18n.gettext import ugettext_lazy as _
from pootle_project.models import Project

from .forms import (
    FS_CHOICES, LangMappingFormSet, ProjectFSAdminForm,
    ProjectFSStateConflictingForm, ProjectFSStateUnsyncedForm,
    ProjectFSStateUntrackedForm)


class ProjectFSStateAdminView(PootleAdminFormView):
    template_name = 'admin/project_fs_state.html'
    form_class = ProjectFSStateUntrackedForm


class ProjectFSAdminBaseView(PootleAdminFormView):

    @property
    def project(self):
        return Project.objects.get(code=self.kwargs.get("project_code"))

    def get_form_kwargs(self, **kwargs):
        context = super(ProjectFSAdminBaseView, self).get_form_kwargs(**kwargs)
        context["project"] = self.project
        return context

    def form_valid(self, form):
        form.save()
        return super(ProjectFSAdminBaseView, self).form_valid(form)


class ProjectFSStateAdminBaseView(ProjectFSAdminBaseView):
    template_name = 'admin/project_fs_state.html'

    def form_valid(self, form):
        # TODO: save form and redirect if update_action
        if form.has_actions:
            form.save()
            messages.success(self.request, "Added some stuff")
            return super(ProjectFSStateAdminBaseView, self).form_valid(form)
        return self.render_to_response(self.get_context_data(form=form))

    def get_context_data(self, **kwargs):
        context = super(
            ProjectFSStateAdminBaseView, self).get_context_data(**kwargs)
        context["project"] = self.project
        form = context["form"]
        pageno = 1
        results_per_page = 10
        if form.is_valid():
            results_per_page = form.cleaned_data["results_per_page"]
            pageno = form.cleaned_data["page"]
        choices = form.search()

        paginator = Paginator(choices, results_per_page)
        page = paginator.page(pageno)
        form.fields[form.paginate_field].choices = page.object_list
        context["formtable"] = self.form_table_class(
            form,
            columns=["Pootle path", "Filesystem path", "State"],
            page=page)
        return context

    @property
    def success_url(self):
        return reverse(
            self.success_url_pattern,
            kwargs=dict(project_code=self.project.code))


class ProjectFSUnsyncedFormtable(Formtable):
    filters_template = "includes/fs/unsynced_filters.html"
    row_field = "unsynced"
    empty_message = _("There are no stores and files waiting to be synced")


class ProjectFSUntrackedFormtable(Formtable):
    filters_template = "includes/fs/untracked_filters.html"
    row_field = "untracked"
    empty_message = _("There are no untracked stores and files")


class ProjectFSConflictingFormtable(Formtable):
    filters_template = "includes/fs/conflicting_filters.html"
    row_field = "conflicting"
    empty_message = _("There are no stores and files currently conflicting")


class ProjectFSStateUntrackedAdminView(ProjectFSStateAdminBaseView):
    form_class = ProjectFSStateUntrackedForm
    form_table_class = ProjectFSUntrackedFormtable
    success_url_pattern = "pootle-admin-project-fs-state-untracked"


class ProjectFSStateUnsyncedAdminView(ProjectFSStateAdminBaseView):
    form_class = ProjectFSStateUnsyncedForm
    form_table_class = ProjectFSUnsyncedFormtable
    paginate_form_field = "unsynced"
    success_url_pattern = "pootle-admin-project-fs-state-unsynced"


class ProjectFSStateConflictingAdminView(ProjectFSStateAdminBaseView):
    form_class = ProjectFSStateConflictingForm
    form_table_class = ProjectFSConflictingFormtable
    paginate_form_field = "conflicting"
    success_url_pattern = "pootle-admin-project-fs-state-conflicting"


class ProjectFSAdminView(PootleAdminFormView):
    template_name = 'admin/project_fs.html'
    form_class = ProjectFSAdminForm
    forms = OrderedDict([
        ("conflict-untracked", ProjectFSAdminForm),
        ("syncable", ProjectFSAdminForm)])

    def get_context_data(self, **kwargs):
        context = super(ProjectFSAdminView, self).get_context_data(**kwargs)
        context["project"] = self.project
        context["lang_mapping_formset"] = self.get_lang_mapping_formset()
        context["fs_choices"] = FS_CHOICES
        return context

    def get_lang_mapping_formset(self):
        formset_data = {
            k: v for k, v
            in self.request.POST.items()
            if k.startswith("lang-mapping")}
        formset_kwargs = dict(project=self.project, prefix="lang-mapping")
        if formset_data:
            formset_kwargs["data"] = formset_data
        formset = LangMappingFormSet(**formset_kwargs)
        if formset_data and formset.is_valid():
            formset.save()
            del formset_kwargs["data"]
            formset = LangMappingFormSet(**formset_kwargs)
        return formset

    @property
    def project(self):
        return Project.objects.get(code=self.kwargs.get("project_code"))

    def get_form_kwargs(self, **kwargs):
        kwargs = super(ProjectFSAdminView, self).get_form_kwargs(**kwargs)
        kwargs.update(dict(project=self.project))
        kwargs["prefix"] = "fs-config"
        kwargs["data"] = {
            k: v for k, v
            in kwargs.get("data", {}).items()
            if k.startswith("fs-config")}
        if not kwargs["data"]:
            del kwargs["data"]
            if kwargs.get("files") is not None:
                del kwargs["files"]
        return kwargs

    def form_valid(self, form):
        form.save()
        return super(ProjectFSAdminView, self).form_valid(form)

    @property
    def success_url(self):
        return reverse(
            "pootle-admin-project-fs",
            kwargs=dict(project_code=self.project.code))
