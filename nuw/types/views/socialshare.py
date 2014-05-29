from five import grok
from nuw.types.campaign import ICampaign
from nuw.types.social import post_to_fb_page, tweet
from plone.registry.interfaces import IRegistry
from zope.component import getUtility
from zope.interface import Interface

grok.templatedir( 'templates' )

class SocialShare( grok.View ):
    grok.context( Interface )
    grok.name( 'social-share' )
    grok.require( 'cmf.ModifyPortalContent' )
    
    def update( self ):
        self.status = None
        if self.request.form:
            self.status = []
            if self.request.form.get( 'enable-facebook-post', None ) == 'on' and self.request.form.get( 'facebook-post', '' ) != '':
                page_id = page_auth = None
                if ICampaign.providedBy( self.context ) and self.context.fb_page_id and self.context.fb_page_token:
                    page_id = self.context.fb_page_id
                    page_auth = self.context.fb_page_token
                else:
                    registry = getUtility( IRegistry )
                    if registry['nuw.types.social.ISocialSettings.fb_default_page_id']:
                        page_id = registry['nuw.types.social.ISocialSettings.fb_default_page_id']
                        page_auth = registry['nuw.types.social.ISocialSettings.fb_default_page_token']

                if page_id and page_auth:
                    post_to_fb_page( page_id, page_auth, self.request.form[ 'facebook-post' ], self.context.absolute_url() )
                    self.status.append( 'Successfully posted to Facebook.' )
                else:
                    self.status.append( 'Could not post to Facebook. Default Facebook page not set up.' )
            if self.request.form.get( 'enable-twitter-post', None ) == 'on' and self.request.form.get( 'twitter-post', '' ) != '':
                tweet( self.request.form[ 'twitter-post' ] )
                self.status.append( 'Successfully posted to Twitter.' )
            
            self.status = ' '.join( self.status )
            
        
        self.facebook_post = '%s: %s' % ( self.context.Title(), self.context.Description() )
        self.twitter_post = '%s %s' % ( self.context.Title(), self.context.absolute_url() )
        if ICampaign.providedBy( self.context ) and self.context.tw_hash_tag:
            self.twitter_post += ' #%s' % self.context.tw_hash_tag
