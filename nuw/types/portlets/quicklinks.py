from plone.portlets.interfaces import IPortletDataProvider
from zope import schema
from plone.app.portlets.portlets import base
from zope.interface import implements
from zope.formlib import form
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile

class IQuickLinksPortlet( IPortletDataProvider ):
    links = schema.Text( title = u'Links', description = u'One link per line in the following format "name|URL"' )

class Assignment( base.Assignment ):
    implements( IQuickLinksPortlet )
    
    title = u'Quick Links Portlet'
    
    def __init__( self, links = None ):
        self.links = links
    
    def get_links( self ):
        return [ { 'title': link[0], 'url': link[1] } for link in [ row.split( '|' ) for row in self.links.split( '\n' ) ] ]
    
class AddForm( base.AddForm ):
    form_fields = form.Fields( IQuickLinksPortlet )
    
    def create( self, data ):
        return Assignment( links = data.get( 'links', None ) )
    
class EditForm( base.EditForm ):
    form_fields = form.Fields( IQuickLinksPortlet )

class Renderer( base.Renderer ):
    _template = ViewPageTemplateFile( 'templates/quicklinks.pt' )

    def render( self ):
        return self._template()
        
