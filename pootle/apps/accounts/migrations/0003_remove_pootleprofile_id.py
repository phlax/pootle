# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations


def fix_accounts_alt_src_langs(apps, schema_editor):
    cursor = schema_editor.connection.cursor()

    # check its mysql - should probs check its not too old
    if not hasattr(cursor.db, "mysql_version"):
        return

    # get the db_name and table_name
    db_name = cursor.db.get_connection_params()['db']
    table_name = (apps.get_model("accounts.User")
                  ._meta.local_many_to_many[0].m2m_db_table())

    # check the problem column exists
    cursor.execute("SELECT COLUMN_NAME"
                   " FROM INFORMATION_SCHEMA.COLUMNS"
                   " WHERE TABLE_SCHEMA = '%s'"
                   "   AND TABLE_NAME = '%s'"
                   "   AND COLUMN_NAME = 'pootleprofile_id';"
                   % (db_name, table_name))
    if not cursor.fetchone():
        return

    # get constraints for column
    cursor.execute("SELECT CONSTRAINT_NAME "
                   "  FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE "
                   "  WHERE TABLE_SCHEMA = '%s' "
                   "    AND TABLE_NAME = '%s' "
                   "    AND COLUMN_NAME = 'pootleprofile_id'"
                   % (db_name, table_name))
    uniq = None
    fk = None
    default = False
    for constraint in cursor.fetchall():
        if constraint[0].endswith("uniq"):
            uniq = constraint[0]
        elif constraint[0].startswith("pootleprofile_id_refs"):
            fk = constraint[0]
        elif constraint[0] == "def":
            default = True

    if uniq:
        # remove unique constraint
        cursor.execute("ALTER TABLE %s.%s "
                       "  DROP KEY %s"
                       % (db_name, table_name, uniq))
    if fk:
        # remove foreign key constraint
        cursor.execute("ALTER TABLE %s.%s "
                       "  DROP FOREIGN KEY %s"
                       % (db_name, table_name, fk))

    if default:
        # remove unique constraint from older migrated db
        cursor.execute("DROP INDEX pootleprofile_id"
                       "   ON %s.%s;" % (db_name, table_name))

    # remove column
    cursor.execute("ALTER TABLE %s.%s "
                   "  DROP COLUMN pootleprofile_id"
                   % (db_name, table_name))


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_user_alt_src_langs'),
    ]

    operations = [
        migrations.RunPython(fix_accounts_alt_src_langs),
    ]
