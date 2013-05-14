# -*- coding: utf-8 -*-
#
# Copyright (c) 2010, Logica
# Author: Nick Piper <nick.piper@logica.com>

import pkg_resources
import re
import urllib

from genshi.builder import tag

from trac.admin.api import IAdminPanelProvider
from trac.core import Component, implements, ExtensionPoint
from trac.util.translation import _
from trac.web.chrome import add_notice, add_stylesheet, add_warning,\
                            ITemplateProvider
from trac.config import ListOption, Option
from trac.versioncontrol import RepositoryManager, is_default
from trac.util.text import breakable_path
from trac.util.datefmt import from_utimestamp, to_utimestamp, utc, utcmax, format_datetime

class SVNVerifyUI(Component):

    implements(IAdminPanelProvider,
               ITemplateProvider)

    # IAdminPanelProvider methods
    def get_admin_panels(self, req):
        if 'SVNVERIFY_REPORT' in req.perm:
            yield ('versioncontrol', _('Version Control'),'verify',_('Verification'))

    def render_admin_panel(self, req, cat, page, path_info):
        req.perm.require('SVNVERIFY_REPORT')
        
        rm = RepositoryManager(self.env)
        all_repos = rm.get_all_repositories()
        db = self.env.get_read_db()
        cursor = db.cursor()
        
        if path_info:
            # detailed
            reponame = not is_default(path_info) and path_info or ''
            info = all_repos.get(reponame)
            if info is None:
                raise TracError(_("Repository '%(repo)s' not found",
                                  repo=path_info))

            cursor.execute("SELECT type, time, result, log FROM svnverify_log WHERE repository_id = %s ORDER BY time DESC LIMIT 1" % info['id'])
            row = cursor.fetchone()
            if row:
                info['check_type'] = row[0]
                info['time_checked'] = format_datetime(from_utimestamp(row[1]))
                info['pretty_status'] = int(row[2]) == 0 and "OK" or "Warning"
                info['status'] = row[2]
                info['log'] = row[3]
            info['prettydir'] = breakable_path(info['dir'])
            if info['name'] == '':
                info['name'] = "(default)"
            return 'svnverify.html', {"info": info}
        else:
            repositories = {}
            for reponame, info in all_repos.iteritems():
                if info.get('type',rm.repository_type) == "svn" or (rm.repository_type == 'svn' and info.get('type') == ''):
                    info['prettydir'] = breakable_path(info['dir'])
                    try:
                        r = RepositoryManager(self.env).get_repository(reponame)
                        info['rev'] = r.get_youngest_rev()
                        info['display_rev'] = r.display_rev(info['rev'])
                    except:
                        pass
                    cursor.execute("SELECT type, time, result FROM svnverify_log WHERE repository_id = %s ORDER BY time DESC LIMIT 1" % info['id'])
                    row = cursor.fetchone()
                    if row:
                        info['check_type'] = row[0]
                        info['time_checked'] = format_datetime(from_utimestamp(row[1]))
                        info['pretty_status'] = int(row[2]) == 0 and "OK" or "Warning"
                        info['status'] = row[2]

                    repositories[reponame] = info

            add_stylesheet(req, 'svnverify/css/svnverify.css')
            return 'svnverifylist.html', {"repositories": repositories}

    # ITemplateProvider methods

    def get_htdocs_dirs(self):
        return [('svnverify', pkg_resources.resource_filename(__name__, 'htdocs'))]

    def get_templates_dirs(self):
        return [pkg_resources.resource_filename(__name__, 'templates')]
