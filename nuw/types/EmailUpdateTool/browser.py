from Products.Five import BrowserView
from zope.publisher.browser import BrowserPage
from zope.interface import implements
from zope.component import getMultiAdapter
from plone.memoize import view
from Products.CMFPlone.utils import safe_unicode
from Products.CMFCore.utils import getToolByName

from nuw.types.EmailUpdateTool.interfaces import IEmailUpdateToolView
from email.Header import Header

from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from zope.interface import Interface

class EmailUpdateSuccess(BrowserView):
    __call__ = ViewPageTemplateFile('skins/EmailUpdate/emailupdate_finish.pt')

class EmailUpdateInvalid(BrowserView):
    __call__ = ViewPageTemplateFile('skins/EmailUpdate/emailupdate_invalid.pt')

class EmailUpdate(BrowserPage):
    def __init__(self, context, request):
        self.context = context
        self.request = request
        self._path = []
    
    def publishTraverse(self, request, name):
        self._path.append(name)
        return self
    
    def __call__(self):
        '''
        View will be called when user clicks activation link in their email.
        Will traverse the link, get the key, verify and finally update their
        email and redirect to success (finish) if no errors are encountered.
        Otherwise, redirect to invalid.
        '''
        email_tool = getToolByName(self.context, 'portal_email_update')
        self.request.response.redirect(self.context.absolute_url() + '/emailupdate_finish')
        
        try:
            key = self._path[0]
        except IndexError:
            self.request.response.redirect(self.context.absolute_url() + '/emailupdate_invalid')

        try:
            email_tool.verifyKey(key)
            email_tool.updateEmail(key)
        except Exception as e:
            self.request.response.redirect(self.context.absolute_url() + '/emailupdate_invalid')
    
    @property
    def traverse_subpath(self):
        return self._path

class EmailUpdateToolView(BrowserView):
    implements(IEmailUpdateToolView)

    @view.memoize_contextless
    def tools(self):
        """ returns tools view. Available items are all portal_xxxxx
            For example: catalog, membership, url
            http://dev.plone.org/plone/browser/plone.app.layout/trunk/plone/app/layout/globals/tools.py
        """
        return getMultiAdapter((self.context, self.request), name=u"plone_tools")

    @view.memoize_contextless
    def portal_state(self):
        """ returns
            http://dev.plone.org/plone/browser/plone.app.layout/trunk/plone/app/layout/globals/portal.py
        """
        return getMultiAdapter((self.context, self.request), name=u"plone_portal_state")

    def encode_mail_header(self, text):
        """ Encodes text into correctly encoded email header """
        return Header(safe_unicode(text), 'utf-8')

    def encoded_mail_sender(self):
        """ returns encoded version of Portal name <portal_email> """
        portal = self.portal_state().portal()
        from_ = portal.getProperty('email_from_name')
        mail  = portal.getProperty('email_from_address')
        return '"%s" <%s>' % (self.encode_mail_header(from_), mail)

    def registered_notify_subject(self):
        portal = self.portal_state().portal()
        portal_name = portal.Title()
        return u"Email update request"

    def mail_email_subject(self):
        portal = self.portal_state().portal()
        portal_name = portal.Title()
        return u"Email update request"

