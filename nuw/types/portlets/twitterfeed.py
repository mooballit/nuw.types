from five import grok
from nuw.types.campaign import ICampaign
from plone.portlets.interfaces import IPortletDataProvider
from plone.app.portlets.portlets import base
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from zope import schema
from zope.formlib import form
from zope.interface import implements
from nuw.types.api.settings import IAPISettings
from plone.registry.interfaces import IRegistry
from zope.component import queryUtility
import oauth2 as oauth
import json, urllib, urllib2

class ICampaignTwitterFeedPortlet( IPortletDataProvider ):
    nr_tweets = schema.Int( title = u'Number of Tweets to show' )

class Assignment( base.Assignment ):
    implements( ICampaignTwitterFeedPortlet )

    title = u'Campaign Twitter Feed Portlet'

    def __init__( self, nr_tweets = 3 ):
        self.nr_tweets = nr_tweets

class AddForm( base.AddForm ):
    form_fields = form.Fields( ICampaignTwitterFeedPortlet )

    def create( self, data ):
        return Assignment( **data )

class EditForm( base.EditForm ):
    form_fields = form.Fields( ICampaignTwitterFeedPortlet )

class Renderer( base.Renderer ):
    _template = ViewPageTemplateFile( 'templates/campaigntwitterfeed.pt' )

    @property
    def available( self ):
        # Only show portlet on campaigns with Twitter Hash tag set
        return ICampaign.providedBy( self.context ) and self.context.tw_hash_tag is not None and self.context.tw_hash_tag != ''

    def render( self ):
        return self._template()

def oauth_req(url, http_method="GET"):
    registry = queryUtility(IRegistry)
    settings = registry.forInterface(IAPISettings)
    # Get authentication details from registry

    consumer = oauth.Consumer(key=settings.consumer_key,
        secret=settings.consumer_secret)
    token = oauth.Token(key=settings.token_key,
        secret=settings.token_secret)
    client = oauth.Client(consumer, token)

    resp, content = client.request(
        url,
        method=http_method,
    )
    return content

class TwitterJson(grok.View):

    grok.context(ICampaign)
    grok.name('twitter-json')

    def render(self):
        form = self.request.form
        response = self.request.response
        response.setHeader("Content-type", "application/json")

        context = self.context

        params = {
            'q': form.get('request[parameters][q]'),
            'count': form.get('request[parameters][count]'),
        }
        url = 'https://api.twitter.com/1.1/search/tweets.json?' + urllib.urlencode(params)
        json_data = oauth_req(url)
        return json.dumps({'response' : json.loads(json_data)})
