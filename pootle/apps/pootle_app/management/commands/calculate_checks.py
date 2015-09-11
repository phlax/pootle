#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) Pootle contributors.
#
# This file is a part of the Pootle project. It is distributed under the GPL3
# or later license. See the LICENSE file for a copy of the license and the
# AUTHORS file for copyright and authorship information.

import logging
import os
from optparse import make_option

# This must be run before importing Django.
os.environ['DJANGO_SETTINGS_MODULE'] = 'pootle.settings'

from django.conf import settings
from django.core.urlresolvers import set_script_prefix
from django.utils import timezone
from django.utils.encoding import force_unicode, iri_to_uri

from django_rq import get_connection, job

from translate.filters.decorators import Category

from pootle.core.cache import get_cache
from pootle.core.mixins.treeitem import POOTLE_REFRESH_STATS, CachedMethods
from pootle_project.models import Project
from pootle_store.models import Store, QualityCheck, Unit
from pootle_store.util import UNTRANSLATED

from . import PootleCommand

logger = logging.getLogger('stats')
cache = get_cache('stats')


class Command(PootleCommand):
    help = "Allow stats and text indices to be refreshed manually."

    shared_option_list = (
        make_option('--check', action='append', dest='check_names',
                    help='Check to recalculate'),
    )
    cached_methods = [CachedMethods.CHECKS]
    option_list = PootleCommand.option_list + shared_option_list
    process_disabled_projects = True

    def handle_all_stores(self, translation_project, **options):
        store_fk_filter = {
            'store__translation_project': translation_project,
        }
        unit_fk_filter = {
            'unit__store__translation_project': translation_project,
        }
        store_filter = {
            'translation_project': translation_project,
        }

        self.register_refresh_stats(translation_project.pootle_path)
        self.process(store_fk_filter=store_fk_filter,
                     unit_fk_filter=unit_fk_filter,
                     store_filter=store_filter,
                      **options)

        translation_project.refresh_stats(include_children=True,
                                          cached_methods=self.cached_methods)
        self.unregister_refresh_stats()
        translation_project.update_parent_cache()

    def handle_store(self, store, **options):
        store_fk_filter = {
            'store': store,
        }
        unit_fk_filter = {
            'unit__store': store,
        }
        store_filter = {
            'pk': store.pk,
        }

        self.register_refresh_stats(store.pootle_path)
        self.process(store_fk_filter=store_fk_filter,
                     unit_fk_filter=unit_fk_filter,
                     store_filter=store_filter,
                     **options)
        self.unregister_refresh_stats()
        store.update_parent_cache()

    def handle_all(self, **options):
        if not self.projects and not self.languages:
            logger.info(u"Running %s (noargs)", self.name)
            try:
                self.register_refresh_stats('/')

                self.process(**options)
                logger.info('Refreshing directories stats...')

                prj_query = Project.objects.all()

                for prj in prj_query.iterator():
                    # Calculate stats for all directories and translation projects
                    prj.refresh_stats(include_children=True,
                                      cached_methods=self.cached_methods)

                self.unregister_refresh_stats()
            except Exception:
                logger.exception(u"Failed to run %s", self.name)
        else:
            super(Command, self).handle_all(**options)

    def calculate_checks(self, check_names, unit_fk_filter, store_fk_filter):
        logger.info('Calculating quality checks for all units...')

        QualityCheck.delete_unknown_checks()

        checks = QualityCheck.objects.filter(**unit_fk_filter)
        if check_names:
            checks = checks.filter(name__in=check_names)
        checks = checks.values('id', 'name', 'unit_id',
                               'category', 'false_positive')
        all_units_checks = {}
        for check in checks:
            all_units_checks.setdefault(check['unit_id'], {})[check['name']] = check

        unit_count = 0
        units = Unit.simple_objects.select_related('store')
        units.query.clear_ordering(True)
        for unit in units.filter(**store_fk_filter).iterator():
            unit_count += 1
            unit_checks = {}
            if unit.id in all_units_checks:
                unit_checks = all_units_checks[unit.id]

            if unit.update_qualitychecks(keep_false_positives=True,
                                         check_names=check_names,
                                         existing=unit_checks):
                # update unit.mtime
                # TODO: add new action type `quality checks were updated`?
                Unit.simple_objects.filter(id=unit.id).update(mtime=timezone.now())

            if unit_count % 10000 == 0:
                logger.info("%d units processed" % unit_count)

    def _set_qualitycheck_stats_cache(self, stats, key):
        if key:
            logger.info('Set get_checks for %s' % key)
            cache.set(iri_to_uri(key + ':get_checks'), stats, None)
            del self.cache_values[key]['get_checks']

    def _set_qualitycheck_stats(self, check_filter):
        checks = QualityCheck.objects.filter(unit__state__gt=UNTRANSLATED,
                                               false_positive=False)
        if check_filter:
            checks = checks.filter(**check_filter)

        queryset = checks.values('unit', 'unit__store', 'name', 'category') \
                         .order_by('unit__store', 'unit', '-category')

        saved_store = None
        saved_unit = None
        stats = None

        for item in queryset.iterator():
            if item['unit__store'] != saved_store:
                try:
                    key = Store.objects.live().get(id=item['unit__store']) \
                                              .get_cachekey()
                except Store.DoesNotExist:
                    continue
                saved_store = item['unit__store']
                stats = self.cache_values[key]['get_checks']

            if item['name'] in stats['checks']:
                stats['checks'][item['name']] += 1
            else:
                stats['checks'][item['name']] = 1

            if saved_unit != item['unit']:
                saved_unit = item['unit']
                if item['category'] == Category.CRITICAL:
                    stats['unit_critical_error_count'] += 1

        for key in self.cache_values:
            stats = self.cache_values[key]['get_checks']
            if stats['unit_critical_error_count'] > 0:
                self._set_qualitycheck_stats_cache(stats, key)


    def _init_stores(self, stores):
        self.cache_values = {}

        for store in stores.iterator():
            self.cache_values[store.get_cachekey()] = {}

    def _init_checks(self):
        for key in self.cache_values:
            self.cache_values[key].update({
                'get_checks': {'unit_critical_error_count': 0,
                               'checks': {}},
            })

    def _set_empty_values(self):
        for key, value in self.cache_values.items():
            for func in value.keys():
                cache.set(iri_to_uri(key + ':' + func), value[func], None)

    def register_refresh_stats(self, path):
        """Register that stats for current path is going to be refreshed"""
        r_con = get_connection()
        r_con.set(POOTLE_REFRESH_STATS, path)

    def unregister_refresh_stats(self):
        """Unregister current path when stats for this path were refreshed"""
        r_con = get_connection()
        r_con.delete(POOTLE_REFRESH_STATS)

    def handle_noargs(self, **options):
        self.process_in_thread(**options)
        calculate_checks.delay(**options)
        option_list = map(lambda x: '%s=%s' % (x, options[x]),
                          filter(lambda x: options[x], options))
        self.stdout.write('calculate checks RQ job added with options: %s. %s.' %
                          (', '.join(option_list),
                          'Please make sure rqworker is running'))

    def process_in_thread(self, **options):
        check_names = options.get('check_names', [])
        unit_fk_filter = options.get('unit_fk_filter', {})
        store_fk_filter = options.get('store_fk_filter', {})
        self.calculate_checks(check_names, unit_fk_filter, store_fk_filter)

    def process(self, **options):
        store_filter = options.get('store_filter', {})
        unit_fk_filter = options.get('unit_fk_filter', {})

        logger.info('Initializing stores...')

        stores = Store.objects.live()
        if store_filter:
            stores = stores.filter(**store_filter)

        self._init_stores(stores)
        self._init_checks()

        logger.info('Setting quality check stats values for all stores...')
        self._set_qualitycheck_stats(unit_fk_filter)
        logger.info('Setting empty values for other cache entries...')
        self._set_empty_values()


@job('default', timeout=18000)
def calculate_checks(**options):
    # The script prefix needs to be set here because the generated
    # URLs need to be aware of that and they are cached. Ideally
    # Django should take care of setting this up, but it doesn't yet:
    # https://code.djangoproject.com/ticket/16734
    script_name = (u'/' if settings.FORCE_SCRIPT_NAME is None
                        else force_unicode(settings.FORCE_SCRIPT_NAME))
    set_script_prefix(script_name)
    super(Command, Command()).handle_noargs(**options)
