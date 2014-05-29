from five import grok
from plone.app.controlpanel.form import ControlPanelForm
from plone.directives import form
from plone.registry.interfaces import IRegistry
from Products.CMFDefault.formlib.schema import SchemaAdapterBase
from Products.CMFPlone.interfaces import IPloneSiteRoot
from zope.app.pagetemplate.viewpagetemplatefile import ViewPageTemplateFile
from zope.component import adapts, getUtility, queryUtility
from zope.interface import Interface
from zope.schema.interfaces import IContextSourceBinder, IVocabularyFactory
from zope.schema.vocabulary import SimpleVocabulary, SimpleTerm

import hashlib
import hmac
import json
import random
import string
import time
import urllib
import urllib2
import urlparse
import zope.schema
import logging

logger = logging.getLogger(__name__)

class ISocialSettings( form.Schema ):
    # Facebook details
    fb_app_key = zope.schema.TextLine( title = u'Facebook App Key', required = False )
    fb_app_secret = zope.schema.TextLine( title = u'Facebook App Secret', required = False )
    fb_user_token = zope.schema.TextLine( title = u'Facebook User Access Token', required = False )

    fb_default_page_id = zope.schema.Choice(
        title = u'Default Facebook Page for Posts',
        vocabulary = u"nuw.types.fb_pages_source",
        required = False
    )
    fb_default_page_token = zope.schema.TextLine(
        title = u'Default Facebook Page Access Token',
        required = False
    )

    # Twitter Details
    tw_app_key = zope.schema.TextLine( title = u'Twitter Consumer Key', required = False )
    tw_app_secret = zope.schema.TextLine( title = u'Twitter Consumer Secret', required = False )
    tw_auth_key = zope.schema.TextLine( title = u'Twitter Access Token', required = False )
    tw_auth_secret = zope.schema.TextLine( title = u'Twitter Access Token Secret', required = False )

    form.fieldset( 'twitter', u'Twitter Settings',
        u'You must login to <a href="http://dev.twitter.com">dev.twitter.com</a> and setup a new application, then complete the details below.',
        fields = [ 'tw_app_key', 'tw_app_secret', 'tw_auth_key', 'tw_auth_secret' ]
    )

class SettingsEditForm( form.SchemaEditForm ):
    zope.interface.implements( ISocialSettings )

    grok.context( IPloneSiteRoot )
    grok.name( 'social-settings' )
    grok.require( 'cmf.ManagePortal' )

    schema = ISocialSettings

    default_fieldset_label = u'Facebook Settings'

    def getContent( self ):
        registry = queryUtility( IRegistry )
        return registry.forInterface( ISocialSettings )

    def update( self ):
        registry = queryUtility( IRegistry )
        data = registry.forInterface( ISocialSettings )

        # Prevent field from getting reset...
        if data.fb_user_token:
            self.request.form['form.widgets.fb_user_token'] = data.fb_user_token

        # Retrive the page access token using the page id and store it
        if self.request.form.get( 'form.widgets.fb_default_page_id' ):
            for page in get_fb_pages():
                if self.request.form[ 'form.widgets.fb_default_page_id' ][0] == page['id']:
                    self.request.form[ 'form.widgets.fb_default_page_token' ] = page['token']
                    break


        if 'code' in self.request.form:
            # Handle callback from facebook's get access call
            data = self.getContent()

            # Exchange code from fb into user access token
            url = 'https://graph.facebook.com/oauth/access_token?' + urllib.urlencode( {
                'client_id': data.fb_app_key,
                'client_secret': data.fb_app_secret,
                'code': self.request.form['code'],
                'redirect_uri': self.request["ACTUAL_URL"]
            } )
            conn = urllib2.urlopen( url )
            ret = urlparse.parse_qs( conn.read() )

            registry['nuw.types.social.ISocialSettings.fb_user_token'] = unicode( ret['access_token'][0] )

        super( SettingsEditForm, self ).update()

    def updateWidgets( self ):
        super( SettingsEditForm, self ).updateWidgets()

        self.widgets['fb_default_page_token'].disabled = 'disabled'

        data = self.getContent()

        w = self.widgets['fb_user_token']
        w.disabled = 'disabled'
        w.template = ViewPageTemplateFile( 'templates/fb_user_token_field.pt' )

        if data.fb_app_key and data.fb_app_secret:
            w.get_token_url = 'https://www.facebook.com/dialog/oauth?' + urllib.urlencode( {
                'client_id': data.fb_app_key,
                'scope': 'manage_pages,publish_stream',
                'redirect_uri': self.request["ACTUAL_URL"]
            } )
        else:
            w.get_token_url = None

# TODO: Memoize for a day
def get_fb_pages():
    '''
    Returns list of available pages along with their id, auth-token and title
    '''
    registry = getUtility( IRegistry )
    token = registry['nuw.types.social.ISocialSettings.fb_user_token']

    if token is not None:
        url = 'https://graph.facebook.com/me/accounts?' + urllib.urlencode( {
            'access_token': token
        } )

        try:
            conn = urllib2.urlopen( url )

            data = json.loads( conn.read() )

            for acc in data['data']:
                if acc['category'] != 'Application':
                    yield { 'id': acc['id'], 'token': acc['access_token'], 'name': acc['name'] }
        except urllib2.HTTPError as err:
            logger.info(
                    "error: %s"
                    % (err))




@grok.provider( IContextSourceBinder )
def fb_pages_source( context ):
    pages = get_fb_pages()

    terms = []
    for page in pages:
        terms.append( SimpleTerm( value = page['id'], token = page['id'], title = page['name'] ) )

    return SimpleVocabulary( terms )

# Needed cause registry requires named vocabs
class fb_pages_vocab( object ):
    grok.implements(IVocabularyFactory)

    def __call__( self, context ):
        return fb_pages_source( context )

grok.global_utility( fb_pages_vocab, name=u"nuw.types.fb_pages_source" )

def post_to_fb_page( fb_page_id, fb_page_auth, content, link = None ):
    url = 'https://graph.facebook.com/%s/feed?%s' % ( fb_page_id, urllib.urlencode( {
        'access_token': fb_page_auth
    } ) )
    data = {
        'message': content
    }
    if link:
        data['link'] = link

    req = urllib2.Request( url, urllib.urlencode( data ) )

    conn = urllib2.urlopen( req )
    conn.read()

def tweet( message ):
    registry = getUtility( IRegistry )

    app_key = registry[ 'nuw.types.social.ISocialSettings.tw_app_key' ]
    app_secret = registry[ 'nuw.types.social.ISocialSettings.tw_app_secret' ]
    auth_key = registry[ 'nuw.types.social.ISocialSettings.tw_auth_key' ]
    auth_secret = registry[ 'nuw.types.social.ISocialSettings.tw_auth_secret' ]

    # Make sure all required config fields are set
    if not ( app_key and app_secret and auth_key and auth_secret ):
        raise ValueError, "Twitter Configuration not complete!"

    url = 'http://api.twitter.com/1.1/statuses/update.json'
    data = {
        'status': message
    }

    # Construct the OAuth Header
    oauth = {
        'oauth_consumer_key': app_key,
        'oauth_nonce': ''.join( [ random.choice( string.ascii_uppercase + string.ascii_lowercase + string.digits ) for x in range( 32 ) ] ),
        'oauth_signature_method': 'HMAC-SHA1',
        'oauth_timestamp': str( int( time.time() ) ),
        'oauth_token': auth_key,
        'oauth_version': '1.0'
    }

    # Generate signature ( see https://dev.twitter.com/docs/auth/creating-signature )
    enc_sig_params = oauth.copy()
    enc_sig_params.update( data )
    enc_sig_params = dict( [ ( urllib.quote( k, '' ), urllib.quote( v, '' ) ) for k, v in enc_sig_params.items() ] )
    enc_sig_params = '&'.join( [ '%s=%s' % ( k, enc_sig_params[ k ] ) for k in sorted( enc_sig_params.keys() ) ] )
    sig_base_str = '&'.join( [ urllib.quote( i, '' ) for i in ( [ 'POST', url, enc_sig_params ] ) ] )
    sig_key = '%s&%s' % ( urllib.quote( app_secret, '' ), urllib.quote( auth_secret, '' ) )

    oauth['oauth_signature'] = hmac.new( sig_key, sig_base_str, hashlib.sha1 ).digest().encode( 'base64' ).strip()

    oauth_header = 'OAuth ' + ', '.join( [ '%s="%s"' % ( urllib.quote( k, '' ), urllib.quote( v, '' ) ) for k, v in oauth.items() ] )

    req = urllib2.Request( url, urllib.urlencode( data ), { 'Authorization': oauth_header } )

    conn = urllib2.urlopen( req )

