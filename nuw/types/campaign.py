from five import grok
from group import Group
from industry import industries_vocab
from member import Person, User, get_user_person
from mooball.plone.activecampaign.tool import ActiveCampaignSubscriber
from plone.app.textfield import RichText
from plone.dexterity.content import Container
from plone.directives.dexterity import AddForm, EditForm
from plone.namedfile.field import NamedImage
from plone.uuid.interfaces import IUUID
from Products.CMFCore.utils import getToolByName
from role import Role, RoleType, add_or_get_roletype
from social import fb_pages_source, get_fb_pages
from z3c.form import field
from z3c.saconfig import named_scoped_session
from AccessControl import Unauthorized
from zope.app.container.interfaces import IObjectRemovedEvent, IObjectAddedEvent
from zope.app.component.hooks import getSite
from zope.component import getMultiAdapter
from zope.lifecycleevent import ObjectAddedEvent, ObjectRemovedEvent, ObjectModifiedEvent
from zope.schema.interfaces import IVocabularyFactory
from zope.schema.vocabulary import SimpleVocabulary, SimpleTerm
from zope.interface import Interface

import plone.directives.form
import uuid
import zope.schema
import datetime

Session = named_scoped_session('nuw.types')

grok.templatedir( 'templates' )

campaign_types = SimpleVocabulary(
    [
        SimpleTerm( value = u'union', title = u'Union Campaign' ),
        SimpleTerm( value = u'worksite', title = u'Worksite Campaign' ),
        SimpleTerm( value = u'social', title = u'Social Campaign' ),
    ]
)


class campaign_types_source( object ):
    grok.implements( IVocabularyFactory )

    def __call__( self, context ):
        return campaign_types
grok.global_utility( campaign_types_source, name=u"nuw.types.campaign_types" )


class ICampaign( plone.directives.form.Schema ):
    image = NamedImage(
        title = u'Campaign Image',
        description = u'Please provide a JPEG image that is 600px wide and 360px high (or bigger).',
        required = False,
    )
    body = RichText( title = u'Body Text', required = False )
    campaign_type = zope.schema.Choice(
        title = u'Campaign Type',
        vocabulary = campaign_types,
        default = u'union'
    )

    has_donation = zope.schema.Bool(
        title = u'Enable Donations to the Campaign',
        required = False,
    )

    # Facebook Stuff
    fb_page_id = zope.schema.Choice(
        title = u'Link to Facebook Page',
        source = fb_pages_source,
        required = False
    )
    fb_page_token = zope.schema.TextLine(
        title = u'Facebook Page Access Token',
        required = False
    )

    # Twitter Stuff
    tw_hash_tag = zope.schema.TextLine(
        title = u'Twitter Hash Tag for Campaign',
        required = False
    )

    # Active Campaign Stuff
    active_campaign_listid = zope.schema.Int(
        title = u'Active Campaign List ID',
        required = False
    )


class Campaign( Container ):
    def acquire_campaign(self):
        return self

    def get_db_group( self, create = True ):
        sess = Session()

        campid = str( uuid.UUID( IUUID(self, None) ) )

        grp = sess.query( Group ).filter( Group.groupid == campid ).first()

        if not grp and create:
            # No group object exists for this campaign. So just create one and return it.
            grp = Group( campid, name = self.Title(), type = 'Campaign' )
            sess.add( grp )
            zope.event.notify( ObjectAddedEvent( grp, self.__parent__, grp.id ) )

        return grp

    def can_subscribe( self ):
        return self.active_campaign_listid is not None

    def is_user_subscribed( self ):
        # Check if current user is subscribed to the campaign
        person = get_user_person( self )

        if person:
            return self.is_person_subscribed( person )

        return False


    def is_person_subscribed( self, person ):
        sess = Session()

        grp = self.get_db_group()

        role = sess.query( Role ).filter(
            Role.personid == person.personid, Role.groupid == grp.groupid,
            Role.type_id == RoleType.id, RoleType.token == 'Subscriber'
        ).first()

        if role:
            return True

        return False


    def set_person_subscription( self, person, subscribe ):
        # Adds subscription role for the provided person
        actool = getToolByName( self, 'portal_activecampaign' )

        sub = ActiveCampaignSubscriber( person.email, person.firstname, person.lastname )
        if subscribe:
            result = actool.sync_subscriber( sub, subids = [ str( self.active_campaign_listid ) ] )
            rolename = 'Subscriber'
        else:
            result = actool.sync_subscriber( sub, unsubids = [ str( self.active_campaign_listid ) ] )
            rolename = 'Unsubscriber'

        if result == 1:
            # Only add the subscribed role if editing the subscriber at AC worked.
            sess = Session()

            grp = self.get_db_group()

            # Check if there is already a role in there (ie previously (un)subscribed)
            role = sess.query( Role ).filter(
                Role.personid == person.personid, Role.groupid == grp.groupid
            ).first()

            if role:
                role.role = add_or_get_roletype( rolename, rolename )
                zope.event.notify( ObjectModifiedEvent( role ) )
            else:
                role = Role( str( uuid.uuid4() ), personid = person.personid, groupid = grp.groupid, role = rolename, startdate = datetime.datetime.now().isoformat() )
                zope.event.notify( ObjectAddedEvent( role, self, role.id ) )

            sess.add( role )

        else:
            # TODO: Something should really happen here.
            pass

    def subscribe_anonymous( self, firstname, lastname, email, mobile = None ):
        sess = Session()

        # Check if there already exists a person with the given email
        person = sess.query( Person ).filter( Person.email == email ).first()

        # If not, create one
        if not person:
            person = Person(
                str( uuid.uuid4() ), firstname = firstname, lastname = lastname,
                email = email, mobile = mobile, type = 'Supporter', status = 'supporter',
                webstatus = 'supporter', activity = 'non-union'
            )
            sess.add( person )
            zope.event.notify( ObjectAddedEvent( person, self, person.id ) )

        if not self.is_person_subscribed( person ):
            self.set_person_subscription( person, True )



@grok.subscribe( ICampaign, IObjectRemovedEvent )
def delete_handler( obj, event ):
    context = event.oldParent

    sess = Session()

    grp = obj.get_db_group( False )

    if grp:
        sess.delete( grp )
        zope.event.notify( ObjectRemovedEvent( grp, context, grp.id ) )

    if obj.active_campaign_listid is not None:
        actool = getToolByName( context, 'portal_activecampaign' )

        actool.delete_lists( [ str( obj.active_campaign_listid ) ] )

@grok.subscribe( ICampaign, IObjectAddedEvent )
def setup_campaign( campaign, event ):
    '''
    On creation of campaign, create 'Gallery' folder with Thumbnail view.
    '''
    def get_virtual_path( obj ):
        return '/' + '/'.join(obj.getPhysicalPath()[len(getSite().getPhysicalPath()):])

    campaign.invokeFactory( 'Folder', 'gallery', title = 'Gallery' )
    campaign.gallery.setLayout('atct_album_view')

class CampaignView( grok.View ):
    grok.name( 'view' )
    grok.context( ICampaign )

    def update( self ):
        try:
            self.wall = self.context.restrictedTraverse( 'wall' )
            self.canaccesswall = True
        except Unauthorized:
            self.wall = True
            self.canaccesswall = False
        except KeyError:
            self.wall = None
            self.canaccesswall = False

        catalog = getToolByName( self.context, 'portal_catalog' )
        self.news_items = catalog.searchResults( {
            'portal_type': 'News Item', 'sort_on': 'effective',
            'sort_order': 'descending', 'review_state': 'published',
            'sort_limit': 10
        }, path = { 'query': '/'.join( self.context.getPhysicalPath() ) } )[:10]

        if 'subscribe' in self.request.form and self.context.can_subscribe():
            # If user is anonymous do anon subscription
            if getMultiAdapter( ( self.context, self.request ), name = u'plone_portal_state' ).anonymous():
                self.context.subscribe_anonymous( self.request.form['firstname'], self.request.form['lastname'], self.request.form['email'], self.request.form.get( 'mobile', None ) )
            else:
                person = get_user_person( self.context )

                if self.request.form['subscribe'] == 'true':
                    if person and not self.context.is_person_subscribed( person ):
                        self.context.set_person_subscription( person, True )
                elif self.request.form['subscribe'] == 'false':
                    self.context.set_person_subscription( person, False )


class BaseCampaignForm( object ):
    def addExtraFields( self ):
        if ICampaign.providedBy( self.context ) and self.context.get( 'wall' ) is not None:
            self.fields += field.Fields(
                zope.schema.Bool(
                    __name__ = 'del_wall',
                    title = u'Delete the campaign Wall',
                    required = False
                )
            )
        else:
            self.fields += field.Fields(
                zope.schema.Bool(
                    __name__ = 'add_wall',
                    title = u'Add a wall to the Campaign',
                    required = False
                )
            )

        if ICampaign.providedBy( self.context ) and self.context.active_campaign_listid is not None:
            self.fields += field.Fields(
                zope.schema.Bool(
                    __name__ = 'del_ac_list',
                    title = u'Disable Active Campaign Subscriptions',
                    required = False
                )
            )
        else:
            self.fields += field.Fields(
                zope.schema.Bool(
                    __name__ = 'add_ac_list',
                    title = u'Enable Active Campaign Subscriptions',
                    required = False
                )
            )

    def getExtraData( self ):
        return {
            'add_wall': self.request.form.pop( 'form.widgets.add_wall', None ) == [ 'selected' ],
            'del_wall': self.request.form.pop( 'form.widgets.del_wall', None ) == [ 'selected' ],
            'add_ac_list': self.request.form.pop( 'form.widgets.add_ac_list', None ) == [ 'selected' ],
            'del_ac_list': self.request.form.pop( 'form.widgets.del_ac_list', None ) == [ 'selected' ],
        }

    def applyExtraFields( self, data, obj ):
        if data['add_wall'] and 'wall' not in obj:
            obj.invokeFactory( 'nuw.types.wall', 'wall', title = 'Campaign Wall' )
        elif data['del_wall'] and 'wall' in obj:
            obj.manage_delObjects( [ 'wall' ] )
        elif data['add_ac_list'] and obj.active_campaign_listid is None:
            actool = getToolByName( self.context, 'portal_activecampaign' )

            listid = actool.add_list( 'campaign-%s' % obj.getId(), 'Campaign - %s' % obj.Title() )
            obj.active_campaign_listid = listid
        elif data['del_ac_list'] and obj.active_campaign_listid is not None:
            actool = getToolByName( self.context, 'portal_activecampaign' )

            actool.delete_lists( [ str( obj.active_campaign_listid ) ] )
            obj.active_campaign_listid = None




class CampaignAddForm( BaseCampaignForm, AddForm ):
    grok.name( 'nuw.types.campaign' )

    def add( self, obj ):
        # Retrive the page access token using the page id and store it
        if obj.fb_page_id:
            for page in get_fb_pages():
                if obj.fb_page_id == page['id']:
                    obj.fb_page_token = page['token']
                    break

        super( CampaignAddForm, self ).add( obj )

        # Re-get the object so it has correct aq chains etc.
        obj = self.context[ obj.getId() ]

        # Make sure the db group gets created
        obj.get_db_group()

        self.applyExtraFields( self.extradata, obj )

    def update( self ):
        self.extradata = self.getExtraData()
        super( CampaignAddForm, self ).update()

    def updateWidgets( self ):
        self.addExtraFields()
        super( CampaignAddForm, self ).updateWidgets()
        del self.widgets['fb_page_token']

class CampaignEditForm( BaseCampaignForm, EditForm ):
    grok.context( ICampaign )

    def applyChanges( self, data ):
        # Retrive the page access token using the page id and store it
        if data['fb_page_id']:
            for page in get_fb_pages():
                if data['fb_page_id'] == page['id']:
                    data['fb_page_token'] = page['token']
                    break

        super( CampaignEditForm, self ).applyChanges( data )

        # Make sure the db group is created
        grp = self.context.get_db_group()

        # And change it's name if title was changed
        if data['IDublinCore.title'] != grp.name:
            sess = Session()

            grp.name = data['IDublinCore.title']

            sess.add( grp )

        self.applyExtraFields( self.extradata, self.context )

    def update( self ):
        self.extradata = self.getExtraData()
        super( CampaignEditForm, self ).update()

    def updateWidgets( self ):
        self.addExtraFields()
        super( CampaignEditForm, self ).updateWidgets()
        del self.widgets['fb_page_token']

class CampaignListing( grok.View ):
    grok.context( Interface )

    def update( self ):
        if self.context.portal_type == 'Folder':
            self.items = self.context.getFolderContents( { 'sort_on': 'sortable_title' } )
        elif self.context.portal_type == 'Collection':
            self.items = self.context.results()


class Petitions( grok.View ):
    '''
    View that lists the petitions stored against the campaign and alows admin to add/edit/delete them
    '''
    grok.context( ICampaign )
    grok.require( 'cmf.ModifyPortalContent' )

    def update( self ):
        if 'delete_selected' in self.request.form:
            ids = self.request.form.get( 'selected', [] )
            self.context.plone_utils.addPortalMessage( '%s Petitions Deleted' % len( ids ) )
            self.context.manage_delObjects( ids )

