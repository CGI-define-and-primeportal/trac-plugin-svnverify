# -*- coding: utf-8 -*-
#
# Copyright (C) 2010 Logica
# All rights reserved.
#

from trac.core import Component, implements, TracError
from trac.db import Table, Column, Index
from trac.db import DatabaseManager
from trac.env import IEnvironmentSetupParticipant

schema_version = 1

class SVNVerifyDB(Component):
    implements(IEnvironmentSetupParticipant)
    
    # IEnvironmentSetupParticipant
    SCHEMA = [
        Table('svnverify_log', key=('id'))[
            Column('id', auto_increment=True),
            Column('repository_id', type='int'),
            Column('type'),            
            Column('result', type='int'),            
            Column('log'),
            Column('time', type='int64'),
            Index(['repository_id']),
            Index(['type']),
            Index(['result']),            
            Index(['time'])],
        ]

    def environment_created(self):
        @self.env.with_transaction()
        def do_create(db):
            self._upgrade_db(self.env.get_db_cnx())

    def environment_needs_upgrade(self, db):
        cursor = db.cursor()

        cursor.execute("SELECT value FROM system WHERE name='svnverify_version'")
        row = cursor.fetchone()
        if row:
            return False
        return True

    def upgrade_environment(self, db):
        self._upgrade_db(db)

    def _upgrade_db(self, db):
        try:
            db_backend, _ = DatabaseManager(self.env)._get_connector()
            cursor = db.cursor()
            for table in self.SCHEMA:
                for stmt in db_backend.to_sql(table):
                    self.log.debug(stmt)
                    cursor.execute(stmt)
                    db.commit()
            cursor.execute("INSERT INTO system (name, value) "
                           "VALUES ('svnverify_version',%s)",
                           (str(schema_version),))
        except Exception, e:
            db.rollback()
            self.log.error(e, exc_info=True)
            raise TracError(str(e))

