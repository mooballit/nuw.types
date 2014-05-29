from Products.CMFCore.utils import getToolByName
from five import grok
from zope.app.component.hooks import getSite
from zope.app.container.interfaces import IObjectAddedEvent
from zope.schema.interfaces import IContextSourceBinder
from zope.schema.vocabulary import SimpleVocabulary
import plone.directives.form
import zope.schema


grok.templatedir( 'templates' )


class IIndustry(plone.directives.form.Schema):

    email = zope.schema.TextLine(
        title=u'Contact Email Address',
        required=False
    )

@grok.subscribe( IIndustry, IObjectAddedEvent )
def setup_industry( industry, event ):
    '''
    When an insdustry gets added this function makes sure all the required subfolders and collections are created and configured
    '''

    def get_virtual_path( obj ):
        return '/' + '/'.join(obj.getPhysicalPath()[len(getSite().getPhysicalPath()):])

    # News foler
    industry.invokeFactory( 'Folder', 'news', title = 'News' )

    # News Collection
    industry['news'].invokeFactory( 'Collection', 'news', title = 'News' )
    coll = industry['news']['news']

    coll.query = [
        { 'i': 'portal_type', 'o': 'plone.app.querystring.operation.selection.is', 'v': [ 'News Item' ] },
        { 'i': 'path', 'o': 'plone.app.querystring.operation.string.path', 'v': get_virtual_path( industry['news'] ) }
    ]

    coll.sort_on = 'created'
    coll.sort_reversed = True

    industry['news'].default_page = 'news'

    # Campaigns Folder
    industry.invokeFactory( 'Folder', 'campaigns', title = 'Campaigns' )

    # Campaigns Collection
    industry['campaigns'].invokeFactory( 'Collection', 'campaigns', title = 'Campaigns' )
    coll = industry['campaigns']['campaigns']

    coll.query = [
        { 'i': 'portal_type', 'o': 'plone.app.querystring.operation.selection.is', 'v': [ 'nuw.types.campaign' ] },
        { 'i': 'path', 'o': 'plone.app.querystring.operation.string.relativePath', 'v': '../' },
    ]

    coll.sort_on = 'created'
    coll.sort_reversed = True

    # Set default view of collection to Campaign listing
    # coll.setLayout( '@@campaignlisting' )

    # Set default view of folder to be collection.
    industry['campaigns'].default_page = 'campaigns'

    # Events Folder
    industry.invokeFactory( 'Folder', 'events', title = 'Events' )

    # Events Collection
    industry['events'].invokeFactory( 'Collection', 'events', title = 'Events' )
    coll = industry['events']['events']

    coll.query = [
        { 'i': 'portal_type', 'o': 'plone.app.querystring.operation.selection.is', 'v': [ 'Event' ] },
        { 'i': 'path', 'o': 'plone.app.querystring.operation.string.relativePath', 'v': '../' }
    ]

    coll.sort_on = 'created'
    coll.sort_reversed = True

    industry['events'].default_page = 'events'

    # About page
    industry.invokeFactory( 'Document', 'about', title = 'About the industry' )

@grok.provider( IContextSourceBinder )
def industries_vocab( context ):
    catalog = getToolByName( context, 'portal_catalog' )

    terms = []

    industries = catalog.searchResults( portal_type = 'nuw.types.industry' )
    for industry in industries:
        terms.append( SimpleVocabulary.createTerm( industry.getId, industry.getId, industry.Title ) )

    return SimpleVocabulary( terms )
