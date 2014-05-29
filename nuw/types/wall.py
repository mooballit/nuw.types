from AccessControl import getSecurityManager
from Acquisition import aq_inner
from five import grok
from nuw.types import Base
from nuw.types.authentication import get_user_worksite, User, Person
from nuw.types.emailing import send_email_to
from nuw.types.grouprole import GroupRole
from nuw.types.imagestore import DBImage
from nuw.types.member import get_user_person
from nuw.types.role import Role, RoleType
from nuw.types.superrole import SuperRole, SuperRoleType
from plone.dexterity.content import Item
from plone.app.layout.viewlets.interfaces import IBelowContent
from plone.uuid.interfaces import IUUID
from Products.CMFCore.interfaces import IFolderish
from Products.CMFCore.utils import getToolByName
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from Products.statusmessages.interfaces import IStatusMessage
from sqlalchemy import Column, Integer, Text, UnicodeText, String, Boolean, Sequence, ForeignKey, DateTime, or_, and_, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, joinedload, joinedload_all
from z3c.saconfig import named_scoped_session
from zope.component import getMultiAdapter
from zope.interface import Interface

import cgi
import datetime
import plone.directives.form
import zope.schema

grok.templatedir( 'templates' )
Session = named_scoped_session("nuw.types")

DEFNRPOSTS = 10


class Post( Base ):
    __tablename__ = 'post'

    id = Column( Integer, Sequence( "post_id" ), primary_key = True )
    wall_id = Column( String )
    parent_id = Column( Integer, ForeignKey( 'post.id' ) )
    posted = Column( DateTime, default = datetime.datetime.now )
    author = Column( String( 40 ), nullable = False, index = True )
    body = Column( Text )
    private = Column( Boolean, default = False )

    image_layout_width = Column( Integer, nullable = True )

    subposts = relationship( 'Post', order_by="asc(Post.posted)" )
    postimages = relationship( 'PostImage' )

    # Gives easy access to users info if post was added by an NUW user
    # For normal plone users this will be None
    user = relationship( 'User', primaryjoin = 'User.name == Post.author', foreign_keys = author )

class PostImage( Base ):
    __tablename__ = 'postimage'

    id = Column( Integer, Sequence( "postimage_id" ), primary_key = True )
    post_id = Column( Integer, ForeignKey( 'post.id' ) )
    image_id = Column( UUID )
    width = Column( Integer )
    height = Column( Integer )

    post = relationship( 'Post' )

class IWall(plone.directives.form.Schema):
    pass

def process_body( body ):
    # Escapes HTML and replaces newlines with <br />
    return cgi.escape( body ).encode( 'ascii', 'xmlcharrefreplace' ).replace( u'\n', u'<br />\n' )

def process_posts( context, dbposts ):
    '''
        Takes a list of posts from the db and looks up the portrait and author name for all of them
        and returns them as a list of dictionaries
    '''
    posts = []

    # Used to lookup portrait for each user, or memberdata for non NUW users
    members = getToolByName( context, 'portal_membership' )

    for post in dbposts:

        def post_fullname( post ):
            if post.user and post.user.person:
                return post.user.person.firstname + ' ' + post.user.person.lastname
            else:
                # Not posted by normal NUW user so lookup the memberdata fullname
                author = members.getMemberById( post.author )
                if author:
                    return author.getProperty( 'fullname' )
                else:
                    # Not posted by any user in db or plone, return author id
                    return post.author

        posts.append( {
            'id': post.id,
            'author': post_fullname( post ) or post.author,
            'portrait': members.getPersonalPortrait( post.author ),
            'posted': post.posted.strftime( '%a %d %B %Y' ),
            'body': process_body( post.body ),
            'private': post.private,
            'images': post.postimages,
            'image_layout_width': post.image_layout_width,
            'subposts': [
                {
                    'id': subpost.id,
                    'author': post_fullname( subpost ) or subpost.author,
                    'portrait': members.getPersonalPortrait( subpost.author ),
                    'posted': subpost.posted.strftime( '%a %d %B %Y' ),
                    'body': process_body( subpost.body )
                }
                for subpost in post.subposts
            ]
        } )

    return posts

class Wall( Item ):
    pass

def get_posts( context, wall_id, count = None, before = None ):
    # Query all posts with no parent linked to this wall
    sess = Session()

    dbposts = (
        sess.query( Post ).filter( Post.parent_id == None, Post.wall_id == wall_id ) #, User, Person
        .options(
            # Join in all the relations to get one query instead of many!
            joinedload( Post.subposts ),
            joinedload( Post.postimages ),
            joinedload( Post.user ),
            joinedload_all( 'user.person' ),
            joinedload_all( 'subposts.user' ),
            joinedload_all( 'subposts.user.person' )
        )
        .order_by( Post.posted.desc() )
    )

    if before is not None:
        dbposts = dbposts.filter( Post.id < before )
    if count is not None:
        dbposts = dbposts.limit( count )

    return process_posts( context, dbposts )

def add_post( parent_id, author, body, wall_id, private = False, images = [] ):
    img_w = None
    if images:
        img_w, images = calc_image_layout( images )

    sess = Session()

    post = Post( parent_id = parent_id, author = author, body = body, wall_id = wall_id, private = private, image_layout_width = img_w )

    sess.add( post )

    for imgid, w, h in images:
        sess.add( PostImage( post = post, image_id = imgid, width = w, height = h ) )

def del_post( wall_id, post_id ):
    sess = Session()

    posts = sess.query( Post ).filter( Post.wall_id == wall_id, or_( Post.id == post_id, Post.parent_id == post_id ) )
    post_imgs = sess.query( PostImage ).filter( PostImage.post_id == post_id )
    post_imgs_s = post_imgs.subquery()
    images = sess.query( DBImage ).join( post_imgs_s, DBImage.imageid == post_imgs_s.c.image_id )

    for item in images.all() + post_imgs.all() + posts.all():
        sess.delete( item )

def calc_horiz_stack( image_infos, width, spacing ):
    # Calculate overall aspect ratio
    ar = sum( [ img[1] / float( img[2] ) for img in image_infos ] )

    # Calculate the height
    height = ( width - ( len( image_infos ) - 1 ) * spacing ) / ar

    return [ ( imgid, w * ( height / h ), height ) for imgid, w, h in image_infos ]

def calc_image_layout( image_infos, width = 430, spacing = 5 ):
    if len( image_infos ) == 1:
        img = image_infos[0]
        ret = [ ( img[0], width, int( img[2] * ( width / float( img[1] ) ) ) ) ]
        total_spacing = spacing
    elif len( image_infos ) == 2:
        ret = calc_horiz_stack( image_infos, width, spacing )
        total_spacing = spacing * 2
    elif len( image_infos ) == 3:
        tall = []
        wide = []

        # Calculate aspect ratios and sort
        for imgid, w, h in image_infos:
            ar = w / float( h )

            if ar < 1:
                tall.append( { 'imgid': imgid, 'ar': ar, 'w': w, 'h': h } )
            else:
                wide.append( { 'imgid': imgid, 'ar': ar, 'w': w, 'h': h } )

        if len( tall ) == 1:
            ar = tall[0]['ar'] + wide[0]['ar'] / ( 1 + wide[0]['ar'] / wide[1]['ar'] )

            image_infos = [ ( img['imgid'], img['w'], img['h'] ) for img in tall + wide ]

            tall[0]['h'] = width / ar
            tall[0]['w'] = tall[0]['h'] * tall[0]['ar']

            wide[0]['w'] = wide[1]['w'] = width - tall[0]['w'] - spacing
            wide[0]['h'] = wide[0]['w'] / wide[0]['ar']
            wide[1]['h'] = wide[1]['w'] / wide[1]['ar']

            ret = [ ( img['imgid'], img['w'], img['h'] ) for img in tall + wide ]
            total_spacing = spacing * 2
        elif len( wide ) == 3:
            # Find the image with the highest aspect ratio and set it as the bottom one
            bottom = None
            for i, img in enumerate( wide ):
                if bottom == None or wide[ bottom ]['ar'] < img['ar']:
                    bottom = i
            image_infos.append( image_infos.pop( bottom ) )
            bottom = wide.pop( bottom )

            ret = calc_horiz_stack( [ ( img['imgid'], img['w'], img['h'] ) for img in wide ], width, spacing ) + \
                    [ ( bottom['imgid'], width, bottom['h'] * ( width / float( bottom['w'] ) ) ) ]
            total_spacing = spacing * 2
        else:
            ret = calc_horiz_stack( image_infos, width, spacing )
            total_spacing = spacing * 3

    # Check if layout is too big for given images, and if so, compensate
    size_comp = None
    for i, img in enumerate( ret ):
        if img[ 1 ] > image_infos[ i ][ 1 ] and ( size_comp == None or image_infos[ i ][ 1 ] / float( img[ 1 ] ) < size_comp ):
            size_comp = image_infos[ i ][ 1 ] / float( img[ 1 ] )

    if size_comp:
        return calc_image_layout( image_infos, width * size_comp, spacing )

    return width + total_spacing, ret



class WallView( grok.View ):
    '''
        Uses WallRenderer to render the wall with the site around it
    '''
    grok.name( 'view' )
    grok.context( IWall )

    walltemplate = ViewPageTemplateFile( 'templates/walltemplate.pt' )
    wallposttemplate = ViewPageTemplateFile( 'templates/wallposttemplate.pt' )

    def renderwall( self ):
        return self.walltemplate()

    def renderposts( self ):
        return self.wallposttemplate()

    def can_post( self ):
        return getSecurityManager().checkPermission( 'nuw.types: Add wall post', self.context )

    def can_reply( self ):
        return getSecurityManager().checkPermission( 'nuw.types: Reply to wall posts', self.context )

    def can_del_post( self ):
        return getSecurityManager().checkPermission( 'nuw.types: Delete wall posts/replies', self.context )

    def can_view_private( self ):
        return getSecurityManager().checkPermission( 'nuw.types: View private wall posts', self.context )

    def get_wall_id( self ):
        return IUUID( self.context )

    def get_posts( self ):
        return get_posts( self.context, self.get_wall_id(), DEFNRPOSTS )

    def update( self ):
        # Add posts if one has been posted
        portal_state = getMultiAdapter((self.context, self.request), name="plone_portal_state")

        self.post_errors = []
        private =  False
        redirect = False

        if self.can_view_private() and self.request.form.has_key( 'private' ):
            self.request.form.pop( 'private' )
            private = True

        if 'post-body' in self.request.form and self.can_post():
            self.post_body = self.request.form.pop( 'post-body' )
            images = self.request.form.pop( 'images', [] )

            # Handle posted images
            store = getToolByName( self.context, 'image_store' )
            image_infos = []
            for image in images:
                if image:
                    try:
                        image_infos.append( store.add_image( image ) )
                    except IOError:
                        self.post_errors.append( 'Unable to upload "%s" - not valid image' % image.filename )
                        return False

            add_post( None, portal_state.member().getMemberId(), self.post_body, self.get_wall_id(), private, image_infos[:3] )

            send_email = self.can_send_email() and self.request.form.pop( 'send_email', False )

            # Only send email if this is a worksite noticeboard
            if hasattr( self, 'worksite' ):
                self.send_post_email( self.post_body, send_email )

            redirect = True

        elif 'subpost-body' in self.request.form and self.can_reply():
            body = self.request.form.pop( 'subpost-body' )
            parent = self.request.form.pop( 'subpost-parent' )

            add_post( parent, portal_state.member().getMemberId(), body, self.get_wall_id(), private )

            # Only send email if this is a worksite noticeboard
            if hasattr( self, 'worksite' ):
                self.send_post_email( body, False, True )

            redirect = True

        elif 'del-post' in self.request.form and self.can_del_post():
            del_post( self.get_wall_id(), self.request.form['del-post'] )

            redirect = True

        # Redirect user to prevent double posts
        if redirect:
            self.request.response.redirect( self.request.ACTUAL_URL )


class InlineWallView( WallView ):
    grok.name( 'inlineview' )
    grok.context( IWall )
    grok.template( 'walltemplate' )

class WorksiteNoticeboardView( WallView ):
    grok.name( 'worksitenoticeboard' )
    grok.context( Interface )

    membernoticeemail_html = ViewPageTemplateFile( 'templates/membernoticeemail.html.pt' )
    membernoticeemail_text = ViewPageTemplateFile( 'templates/membernoticeemail.text.pt' )

    staffnoticeemail_html = ViewPageTemplateFile( 'templates/staffnoticeemail.html.pt' )
    staffnoticeemail_text = ViewPageTemplateFile( 'templates/staffnoticeemail.text.pt' )

    def can_send_email( self ):
        pers = get_user_person( self.context )

        if pers and 'delegate_email' in pers.webstatuses:
            return True

    def get_wall_id( self ):
        return 'worksite/' + self.worksite.groupid

    def update( self ):
        self.worksite = get_user_worksite( self.context )

        if self.worksite:
            super( WorksiteNoticeboardView, self ).update()

    def is_admin(self):
        return getSecurityManager().checkPermission(
                'nuw.types: Access all worksites', self.context )

    def send_post_email( self, post_body, is_rep_post = False, is_reply = False ):
        portal_state = getMultiAdapter((self.context, self.request), name="plone_portal_state")

        messages = IStatusMessage(self.request)

        sess = Session()

        pers = get_user_person( self.context )
        if pers:
            sender = '%s %s' % ( pers.firstname, pers.lastname )
        else:
            sender = portal_state.member().getUser().getName()

        url = self.context.absolute_url() + '/@@worksitenoticeboard'

        if is_rep_post:
            # Email send initiated via send_email checkbox
            # Send email to members and/or potential members
            subject = 'New wall post - %s' % self.request.form.pop( 'email_subject' )
            send_to = self.request.form.pop( 'send_to', [] )


            # Lookup recipients
            recipients = sess.query( Person ).filter(
                Role.personid == Person.personid, Role.groupid == self.worksite.groupid,
                Role.enddate.is_( None ) | ( Role.enddate > func.current_timestamp() ),
                RoleType.id == Role.type_id, Person.email.isnot( None ), Person.email != ''
            ).group_by( Person )

            # Filter recipients depending on selections
            if 'all_members' in send_to or 'potential_members' in send_to:
                # Send to reps and employees (depending on webstatus)
                statuses = []

                if 'all_members' in send_to:
                    statuses += [
                        'Leave without Pay', 'Workers Compensation',
                        'On Books Not Working', 'Paying', 'Unions Australia',
                        'Awaiting 1st payment', 'Parental Leave', 'Life Member'
                    ]
                if 'potential_members' in send_to:
                    statuses += [ 'Potential Member' ]

                statuses = [ s.lower() for s in statuses ]

                recipients = recipients.filter(
                    RoleType.token == 'Employee',
                    func.lower( Person.status ).in_( statuses )
                )

                # Send out the emails to found recipients
                send_email_to( self, recipients, sender + ' <no-reply@nuw.org.au>',
                    self.membernoticeemail_html, self.membernoticeemail_text,
                    url = url, content = post_body, from_name = sender,
                    site_name = self.worksite.name,
                    is_potential = 'potential_members' in send_to,
                    is_members = 'all_members' in send_to,
                    subject = subject
                )

                messages.addStatusMessage( 'Sent email to %s people' % ( recipients.count() ) )

        # Send notice email to reps, organisers and Industry MSOs

        # First we get the reps
        recipients = sess.query( Person ).filter(
            Role.groupid == self.worksite.groupid, RoleType.token.in_( ( 'Web Rep', 'Delegate' ) ),
            Role.enddate.is_( None ) | ( Role.enddate > func.current_timestamp() ),
            Role.personid == Person.personid, Role.type_id == RoleType.id,
            Person.email.isnot( None ), Person.email != ''
        )

        # Then the orgs abd MSOs
        recipients = recipients.union( sess.query( Person ).filter(
            GroupRole.groupid == self.worksite.groupid,
            SuperRoleType.token.in_( ( 'Industry MSO', 'Organiser' ) ),
            GroupRole.supergroupid == SuperRole.supergroupid,
            SuperRole.type_id == SuperRoleType.id,
            SuperRole.personid == Person.personid,
            Person.email.isnot( None ), Person.email != ''
        ) )

        # (Hopefully) Ensure people dont get multiple emails.
        recipients = recipients.group_by( Person )

        dt = datetime.datetime.now()

        send_email_to( self, recipients, sender + ' <no-reply@nuw.org.au>',
            self.staffnoticeemail_html, self.staffnoticeemail_text, url = url,
            content = post_body, site_name = self.worksite.name,
            is_reply = is_reply, time = dt.strftime('%X'), date = dt.strftime('%x'),
            subject = 'Notification - New Worksite Noticeboard post'
        )

class AjaxWallPosts( WallView ):
    grok.name( 'wallposts' )
    grok.context( Interface )
    grok.template( 'wallposttemplate' )

    def get_wall_id( self ):
        return self.wall_id

    def update( self ):
        self.wall_id = self.request.form.get( 'wall_id' )
        self.before = self.request.form.get( 'before' )
        self.count = self.request.form.get( 'count', DEFNRPOSTS )

    def get_posts( self ):
        return get_posts( self.context, self.wall_id, self.count, self.before )
