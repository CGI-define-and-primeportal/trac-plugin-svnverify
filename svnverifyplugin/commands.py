# -*- coding: utf-8 -*-
#
# Copyright (c) 2010, Logica
# Author: Nick Piper <nick.piper@logica.com>

import pkg_resources
import re
import urllib
from subprocess import Popen, PIPE

from genshi.builder import tag

from trac.util.datefmt import from_utimestamp, to_utimestamp, utc
from datetime import datetime

from trac.admin import AdminCommandError, IAdminCommandProvider
from trac.core import Component, implements, ExtensionPoint
from trac.util.translation import _
from trac.config import ListOption, Option
from trac.versioncontrol import RepositoryManager, IRepositoryChangeListener
from tracrpc.api import IXMLRPCHandler
from trac.perm import IPermissionRequestor

# this uses paths, IDs and names... Maybe it can be simplified to use
# only a single item as the keying variable. Trac itself seems to have
# a bit of a mix still, as until recently, they only supported a
# single repository per project.

class SVNVerifyCommands(Component):
    """Perform integrity checks on subversion repository"""
    
    implements(IAdminCommandProvider,
               IXMLRPCHandler,
               IPermissionRequestor,
               IRepositoryChangeListener)
    
    # IPermissionRequestor methods
    def get_permission_actions(self):
        return ['SVNVERIFY_REPORT', 'SVNVERIFY_RUN']

    # IRepositoryChangeListener
    def changeset_added(self, repos, changeset):
        if repos.name.split(":",2)[0] == "svn":
            self.log.debug("Verifying new changeset %s to %s", changeset.rev, repos.repos.path)
            self.verify(repos.id, repos.repos.path, changeset.rev)
        
    def changeset_modified(repos, changeset, old_changeset):
        pass

    #IAdminCommandProvider methods
    def get_admin_commands(self):
        yield ('svn verify', '',
               'Run svnadmin verify against repository',
               self._complete_admin_command, self._admin_verify)

    def _complete_admin_command(self, args):
        return []

    def _admin_verify(self):
        return self.verifyAll()
        
    # IXMLRPCHandler methods
    def xmlrpc_namespace(self):
        return 'svn'

    def xmlrpc_methods(self):
        yield ('SVNVERIFY_RUN', ((bool, int, str, int),), self._rpcverify, "verify")
        yield ('SVNVERIFY_RUN', ((bool, ),), self._rpcverifyall, "verifyAll")
        yield ('SVNVERIFY_REPORT', ((bool, ),), self.getStatus)

    def _rpcverifyall(self, req):
        """Run svnadmin verify against a repository
        Pass revision as None or -1 to check all revisions."""
        req.perm.require('TRAC_ADMIN')        
        return bool(self.verifyAll()==0)

    def _rpcverify(self, req, repository_id, path, revision):
        """Run svnadmin verify against a repository
        Pass revision as None or -1 to check all revisions."""
        req.perm.require('TRAC_ADMIN')
        return bool(self.verify(repository_id, path, revision)==0)

    # own methods
    def getStatus(self, req):
        """Get overall status from the last time verification was performed."""
        db = self.env.get_read_db()
        cursor = db.cursor()
        rm = RepositoryManager(self.env)
        for reponame, info in rm.get_all_repositories().iteritems():
            if info.get('type',rm.repository_type) == "svn" or (rm.repository_type == 'svn' and info.get('type') == ''):
                self.log.debug("Checking database for status of %s", info)
                cursor.execute("SELECT result FROM svnverify_log WHERE repository_id = %s ORDER BY time DESC LIMIT 1" % info['id'])
                row = cursor.fetchone()
                if row and row[0] != 0:
                    return False
        return True
    
    def verify(self, repository_id, path, revision=None):
        """Run svnadmin verify against a repository.
        Pass revision as None or -1 to check all revisions.
        """
        if revision < 0:
            revision = None
        self.log.info("Verifying %s at %s" % (repository_id, path))
        if revision is None:
            cmdline = ["svnadmin","verify",path]
            level   = "full"
        else:
            cmdline = ["svnadmin","verify","-r",str(int(revision)),path]
            level   = "revision"
        self.log.debug(cmdline)
        child = Popen(cmdline, bufsize=-1, stdin=PIPE, stdout=PIPE,
                      stderr=PIPE)
        (out, err) = child.communicate()
        self.log.debug(out)
        if child.returncode == 0:
            self.log.debug(err)
        else:
            self.log.warning("Failed svnadmin of %s", path)
            self.log.warning(err)
        @self.env.with_transaction()
        def do_insert(db):
            cursor = db.cursor()
            cursor.execute("INSERT INTO svnverify_log (repository_id, type, result, log, time) VALUES (%s,%s,%s,%s,%s)",
                           (repository_id, level, child.returncode, err, to_utimestamp(datetime.now(utc))))
        
        if child.returncode == 0:
            return True

    def verifyAll(self):
        all_verified_good = True
        rm = RepositoryManager(self.env)
        for reponame, info in rm.get_all_repositories().iteritems():
            self.log.debug("Considering %s", info)
            if info.get('type',rm.repository_type) == "svn" or (rm.repository_type == 'svn' and info.get('type') == ''):
                if not self.verify(info['id'], info['dir']):
                    all_verified_good = False
        if not all_verified_good:
            return 1
        else:
            return 0
