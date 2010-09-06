# -*- coding: utf-8 -*-
#
# Copyright (c) 2010, Logica
# Author: Nick Piper <nick.piper@logica.com>


from trac.core import Component, implements
from trac.config import ListOption, Option
from trac.web.chrome import Chrome

from genshi.template import TemplateLoader, NewTextTemplate

from announcer.api import AnnouncementSystem, AnnouncementEvent, \
    IAnnouncementProducer, IAnnouncementSubscriber, IAnnouncementFormatter

class SVNVerifyFailEvent(AnnouncementEvent):
    def __init__(self, realm, category, target, log):
        AnnouncementEvent.__init__(self, realm, category, target)
        self.log = log

class SVNVerifyAnnouncer(Component):
    implements(IAnnouncementProducer,
               IAnnouncementFormatter,
               IAnnouncementSubscriber)

    text_template_name = Option('svn', 
                                'verify_fail_text_template_name', 
                                "verifyfail_plaintext.txt",
                                doc="""Filename of genshi template to use for plain text 
                                       svn verify fail mails.""")

    email_notification_targets = ListOption("svn", 
                                            "verification_notice_to", "",
                                            doc="""List of email addresses or usernames
                                                   to send warnings to.""")
    # IAnnouncementSubscriber
    def subscriptions(self, event):
        if event.realm != 'versioncontrol' or event.category != 'verifyfail':
            return
        for target in self.email_notification_targets:
            if "@" in target:
                result = ('email', None, True, target)
            else:
                result = ('email', target, True, None)
            self.log.debug("SVNVerifyCommands added subscriber '%s' ('%s')", 
                           result[1], result[3])
            yield result



    # IAnnouncementFormatter
    def styles(self, transport, realm):
        if realm == "versioncontrol":
            yield "text/plain"
        
    def alternative_style_for(self, transport, realm, style):
        if realm == "versioncontrol" and style != 'text/plain':
            return "text/plain"
        
    def format(self, transport, realm, style, event):
        if realm == "versioncontrol":
            if style == "text/plain":
                return self._format_plaintext(event)

    def _format_plaintext(self, event):
        data = dict(
            event = event,
            project_name = self.env.project_name,
            project_desc = self.env.project_description,
            project_link = self.env.project_url or self.env.abs_href(),
        )
        chrome = Chrome(self.env)        
        dirs = []
        for provider in chrome.template_providers:
            dirs += provider.get_templates_dirs()
        templates = TemplateLoader(dirs, variable_lookup='lenient')
        template = templates.load(self.text_template_name, 
                cls=NewTextTemplate)
        if template:
            stream = template.generate(**data)
            output = stream.render('text')
        return output

    def _header_fields(self, ticket):
        headers = self.ticket_email_header_fields
        fields = TicketSystem(self.env).get_ticket_fields()
        if len(headers) and headers[0].strip() != '*':
            def _filter(i):
                return i['name'] in headers
            fields = filter(_filter, fields)
        return fields
 
