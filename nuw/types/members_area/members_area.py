from five import grok
from zope.interface import Interface
from OFS.interfaces import IFolder
from Products.CMFCore.utils import getToolByName

from z3c.saconfig import named_scoped_session

from zope.app.component.hooks import getSite
from AccessControl import Unauthorized

from nuw.types.member import User
from nuw.types.wall import Post
from nuw.types.file import get_group_files
from nuw.types.role import get_person_worksites

Session = named_scoped_session( 'nuw.types' )

grok.templatedir( 'templates' )

class IMembersArea( Interface ):
    pass

def get_or_kick_user( context, request ):
    plone_user = getToolByName(context, 'portal_membership').getAuthenticatedMember()
    
    sess = Session()
    
    user = sess.query( User ).filter( User.name == plone_user.getUserName() ).first()
    if user:
        return user
    else:
        raise Unauthorized

class WorksiteAgreements( grok.View ):
    grok.context( IFolder )
    grok.name( 'worksite-agreements' )
    
    def update( self ):
        self.user = get_or_kick_user( self.context, self.request )
        self.person = self.user.person
    
    def get_files( self ):
        self.files = list()
        for group in get_person_worksites(self.person.personid):
            self.files += get_group_files(group.groupid)
        return self.files

    def get_date( self, date ):
        if date != None and date != '':
            return date.strftime("%d %B %Y")

class Subscriptions( grok.View ):
    grok.context( IFolder )
    
    def update( self ):
        self.campaigns = list()
        self.user = get_or_kick_user( self.context, self.request )
        self.person = self.user.person

        catalog = getToolByName( self.context, 'portal_catalog' )
        for campaign in catalog( { 'portal_type': 'nuw.types.campaign' } ):
            campaign = campaign.getObject()
            self.campaigns.append(campaign)

            if self.request.form:
                self.modify_subscription(campaign)

    def get_campaigns( self ):
        return self.campaigns

    def modify_subscription( self, campaign ):
        if campaign.can_subscribe():
            subscribed_already = campaign.is_person_subscribed(self.person)
            has_key = self.request.form.has_key(campaign.id)
            if has_key and not subscribed_already:
                campaign.set_person_subscription(self.person, True)
            if not has_key and subscribed_already:
                campaign.set_person_subscription(self.person, False)

class DummyViewletManager( grok.ViewletManager ):
    grok.context( Interface )
    grok.name( 'nuw.types.dummyviewletmanager' )

class MembersAreaNav( grok.Viewlet ):
    grok.context( Interface )
    grok.viewletmanager( DummyViewletManager )

    def __of__( self, context ):
        # This is defined cause plone.portlet.viewlet requires it.
        return self
    
    def update( self ):
        self.menu = [
            { 'id': 'worksitenoticeboard', 'Title': 'Worksite noticeboard' },
            { 'id': 'contact-details', 'Title': 'Contact details' },
            { 'id': 'events', 'Title': 'Events' },
            { 'id': 'training', 'Title': 'Training' },
            { 'id': 'worksite-agreements', 'Title': 'Worksite agreements' },
            { 'id': 'subscriptions', 'Title': 'Subscriptions' },
            { 'id': 'payment-methods', 'Title': 'Payment methods' },
        ]
        
        self.cur_item = self.request['URL'].split( '/' )[-1]
