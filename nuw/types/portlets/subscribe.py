from five import grok
from nuw.types.campaign import ICampaign
from plone.app.portlets.portlets import base
from plone.portlets.interfaces import IPortletDataProvider
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from zope.formlib import form
from zope.interface import implements

class ISubscriptionPortlet( IPortletDataProvider ):
    pass

class Assignment( base.Assignment ):
    implements( ISubscriptionPortlet )

    title = u'Subscription Portlet'
    
class AddForm( base.AddForm ):
    form_fields = form.Fields( ISubscriptionPortlet )

    def create( self, data ):
        return Assignment()


class EditForm( base.EditForm ):
    form_fields = form.Fields( ISubscriptionPortlet )

class Renderer( base.Renderer ):
    _template = ViewPageTemplateFile( 'templates/subscriptionportlet.pt' )

    @property
    def available( self ):
        return ICampaign.providedBy( self.context ) and self.context.can_subscribe()

    def render( self ):
        return self._template()
