from five import grok
from Products.CMFCore.utils import getToolByName
from plone.portlets.interfaces import IPortletDataProvider
from zope.interface import implements
from zope.formlib import form
from zope import schema
from plone.app.portlets.portlets import base
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from zope.interface import Interface

import urllib

grok.templatedir( 'templates' )

class ISocialSharePortlet( IPortletDataProvider ):
    twitter_ref = schema.TextLine(
                        title = u'Twitter Screen Name',
                        description = u'The Twitter @screen_name used, an example tweet: "National Union of Workers http://nuw.org.au/ @NatUnionWorkers"',
                        default=u"@NatUnionWorkers"
                        )

class Assignment( base.Assignment ):
    implements( ISocialSharePortlet )

    title = u'Social Share Portlet'
    
    def __init__( self, twitter_ref = None ):
        self.twitter_ref = twitter_ref
    
    def get_twitter_ref( self ):
        return self.twitter_ref
    
    def get_encoded_url( self ):
        return urllib.quote_plus(self.context.absolute_url())
    
    def get_encoded_title( self ):
        return urllib.quote_plus(self.context.title)
    
    def get_encoded_twitter_ref( self ):
        return urllib.quote_plus(self.twitter_ref)

class AddForm( base.AddForm ):
    form_fields = form.Fields( ISocialSharePortlet )

    def create( self, data ):
        return Assignment( twitter_ref = data.get( 'twitter_ref', None ) )

class EditForm( base.EditForm ):
    form_fields = form.Fields( ISocialSharePortlet )

class Renderer( base.Renderer ):
    _template = ViewPageTemplateFile( 'templates/socialshare.pt' )

    def render( self ):
        return self._template()

    @property
    def available(self):
        return True

class EmailShare( grok.View ):
    grok.context( Interface )
    
    email_template = ViewPageTemplateFile( 'templates/emailshare_email.pt' )
    
    def update( self ):
        self.posted = False
        if 'recipients' in self.request.form:
            host = getToolByName( self.context, 'MailHost' )
            sender_name = self.request.form[ 'sender_name' ]
            sender_email = self.request.form[ 'sender_email' ]
            url = self.context.absolute_url()
            
            for rec in self.request.form['recipients']:
                if rec:
                    emailcontent = self.email_template( to_email = rec, from_name = sender_name, from_email = sender_email, url = url )
                    
                    host.send( emailcontent )
            self.posted = True
