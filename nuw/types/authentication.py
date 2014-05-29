# coding=utf-8
"""
Authentication
==============

Authentication (www.nuw.org.au)
-------------------------------

Login to the main site depends on the ‘webstatus’ property value only

    * person.webstatus = “member” - can login
    * person.webstatus = “non-financial” - can login
    * person.webstatus = “non-member” - can not login
    * person.webstatus = “ex-member” - can not login

Authentication (unionrep.nuw.org.au)
------------------------------------

To successfully login the person must have:

    * person.webstatus = “member” AND
    * role.typeid => rolestype.token = “Web Rep”

Groups (common to both sites)
-----------------------------

Assign groups based on person.webstatus property:

    * person.webstatus = “member” => "NUW Members" group
    * person.webstatus = “non-financial” => "Non Financial" group

Additional Groups will be assigned based on Roles e.g.

    * role.typeid => rolestype.token = “Delegate” => "Delegates" group
    * role.typeid => rolestype.token = “Web Rep” => "Web Reps" group
    * role.typeid => rolestype.token = “NUW Admin” => "NUW Admin" group
    * role.typeid => rolestype.token = “Official” => "Officials" group
    * superrole.typeid => superrolestype.token = “Organiser” => "Organisers" group

API
---
"""
# Based partly on:
# http://svn.plone.org/svn/collective/PASPlugins/pas.plugins.sqlalchemy/trunk/src/pas/plugins/sqlalchemy/plugin.py

from AccessControl import ClassSecurityInfo
from Products.CMFCore.utils import getToolByName
from Products.CMFPlone.interfaces.siteroot import IPloneSiteRoot
from Products.PlonePAS.interfaces.capabilities import IDeleteCapability
from Products.PlonePAS.interfaces.capabilities import IPasswordSetCapability
from Products.PlonePAS.interfaces.plugins import IUserManagement
from Products.PlonePAS.sheet import MutablePropertySheet
from Products.PluggableAuthService.interfaces.plugins import\
        IAuthenticationPlugin, IUserEnumerationPlugin, IGroupsPlugin,\
        IPropertiesPlugin
from Products.PluggableAuthService.plugins.BasePlugin import BasePlugin
from Products.PluggableAuthService.utils import classImplements
from nuw.types.group import Group, GroupType
from nuw.types.interfaces import IUnionRep
from nuw.types.member import User, Person
from nuw.types.role import Role, RoleType, get_person_worksites
from AccessControl import getSecurityManager
from nuw.types.role import get_roletype_from_person
from nuw.types.superrole import SuperRole, SuperRoleType
from sqlalchemy.exc import DatabaseError
from z3c.saconfig import named_scoped_session
from zope.lifecycleevent import ObjectRemovedEvent
from datetime import datetime
import Products.PlonePAS.interfaces.group
import logging
import zope.component
import zope.interface


logger = logging.getLogger(__name__)
Session = named_scoped_session('nuw.types.auth')
PLUGIN_NAME = 'nuw-members'

def get_user_worksite( context ):
    plone_user = getToolByName(context, 'portal_membership').getAuthenticatedMember()

    sess = Session()

    person = sess.query( Person ).filter(
        User.name == plone_user.getUserName(), Person.user_id == User.id,
        ).first()

    # Handle admin worksite (for plone users that do not have a worksite assigned)
    if getSecurityManager().checkPermission( 'nuw.types: Access all worksites', context ):
        sdm = getToolByName( context, 'session_data_manager' )

        if 'admin-worksite' in context.REQUEST.form:
            # Pop from request to prevent session being set 1000 times
            admin_worksite = context.REQUEST.form.pop( 'admin-worksite' )

            if admin_worksite != 'null':
                session = sdm.getSessionData( create = True )
                session.set( 'admin-worksite', admin_worksite )
            else:
                if sdm.hasSessionData():
                    session = sdm.getSessionData()
                    if session.has_key( 'admin-worksite' ):
                        del session[ 'admin-worksite' ]

        if sdm.hasSessionData():
            session = sdm.getSessionData()

            if session.get( 'admin-worksite', None ):
                site = sess.query( Group ).filter( Group.groupid == session['admin-worksite'] ).first()

                return site

    if not person:
        return None

    worksites = get_person_worksites( person.personid )
    if len(worksites):
        return worksites[0]


class INUWAuthPlugin(zope.interface.Interface):
    """ Authentication plugin, which authenticates members off the SQL
        database.
    """

    def _query_for_auth_user(login, password):
        """Returns the user from the database given login
           and password. None otherwise.
        """

    def _can_authenticate(user):
        """ Returns true, if the user has the attributes authenticate
            him against the provided login and password attributes.

        This helper method returns True if:

            * the user is associated with a person and it's
              webstatus is set to one of the lines set in the
              'webstatus' property

            * the nearest plone site is providing IUnionRep, the members
              webstatus == 'member' and it's roletype == 'Web Rep'
              (hardcoded)
        """

    def get_groups_by_username(username):
        """ Returns a sequence of group names associated to the given
            user or an empty list.
        """

    def enumerateGroups(id=None, title=None, exact_match=False,
                        sort_by=None, max_results=None, **kw):
        """ Return all possible groups.

            ..  note::
                The groups retrieved are filtered against the list of
                group ids returned by the `portal_groups` tool.
                Therefore only groups are returned which have a
                corresponding group in `acl_users.source_groups`.
        """


class NUWAuthPlugin(BasePlugin):
    _dont_swallow_my_exceptions = True
    zope.interface.implements(INUWAuthPlugin)
    security = ClassSecurityInfo()

    def __init__( self, id, title = None ):
        self._setId( id )
        self.title = title

    def _query_for_auth_user(self, login, password):
        try:
            sess = Session()
            user = sess.query(User).filter(
                User.name == login, User.password == password).first()
        except DatabaseError, e:
            # Something went wrong with the database/query, log the
            # error and return none to not screw up the system.
            logger.info(
                'Member auth got db error when trying to authenticate %s: %s'
                % (login, e))
            return

        return user

    def _can_authenticate(self, user):
        """
        User is kicked when has a 'denied' webstatus at all times.
        If not limiting to groups, the default webstatus property will be used
        to determine who gets in and who does not.
        The 'webstatus' property is defined in 'acl_users/nuw-members' and can
        be delimited by both lines and commas.
        For example:
        webstatus = 'financial-member,webrep
                     unfinancial-member
                     union-employee'
        Lines mean OR, and commas mean AND. By using a combination, specific
        groups can be let in or kicked.
        """
        if user and hasattr( user, 'person' ):
            if 'denied' in user.person.webstatuses:
                return False

            # If group limitations are enabled, check if user belongs to any
            # of the allowed groups
            if self.getProperty( 'limit_to_groups' ):
                usrgroups = self.get_groups_by_username( user.name )

                for groupset in self.limit_to_groups:
                    groupset = [ grps.strip() for grps in groupset.split( ',' ) ]

                    for grp in groupset:
                        if grp not in usrgroups:
                            break
                    else:
                        # User has all of the required groups (=allowed)
                        return True
            else:
                if not hasattr(self, 'webstatus'):
                    logger.info(
                        "Please add or fill in the 'webstatus' property " +
                        "within the ZMI under 'acl_users/nuw-members'"
                        )
                    return False

                for webstatus in self.webstatus:
                    user_allowed = True
                    for status in webstatus.split(','):
                        if not status.strip() in user.person.webstatuses:
                            user_allowed = user_allowed and False

                    if user_allowed:
                        return True

                return False

        return False

    # IAuthenticationPlugin
    def authenticateCredentials(self, credentials):
        login = credentials.get('login')
        password = credentials.get('password')

        if not login or not password:
            return None

        user = self._query_for_auth_user(login, password)
        if not self._can_authenticate( user ):
            return

        return (login, login)


    # IUserEnumerationPlugin
    def enumerateUsers( self, id = None, login = None, exact_match = False, sort_by = None, max_results = None, **kw ):
        if exact_match and not ( login or id ):
            return ()

        try:
            sess = Session()

            query = sess.query( User )

            def clause( column, value ):
                if exact_match or not isinstance( value, basestring ):
                    return ( column == value )
                elif isinstance( value, str ):
                    return column.ilike( '%%%s%%' % value )
                elif isinstance( value, unicode ):
                    return column.ilike( u'%%%s%%' % value )
                return ( column == value )

            if id:
                kw['id'] = id
            if login:
                kw['login'] = login

            for key, val in kw.items():
                if key in [ 'id', 'login','email' ]:
                    column = User.name
                elif key == 'fullname':
                    query = query.filter( User.id == Person.user_id )
                    column = Person.firstname + ' ' + Person.lastname
                else:
                    # Unrecognized column return nothing!
                    return ()

                if isinstance( val, list ) or isinstance( val, tuple ):
                    parts = [ clause( column, v ) for v in val ]
                    query = query.filter( sql.or_( *parts ) )
                else:
                    query = query.filter( clause( column, val ) )


            if sort_by is not None and hasattr( sort_by, User ):
                query = query.order_by( getattr( sort_by, User ) )
            if max_results is not None and max_results != '':
                query = query.limit( max_results )

            ret = []

            for user in query:
                login = user.name
                if login:
                    login = login.encode('utf8', 'ignore')
                ret.append( { 'id': login, 'login': login, 'pluginid': self.getId() } )
        except DatabaseError, e:
            # Something went wrong with the database/query, log the
            # error and return none to not screw up the system.
            logger.info( 'Member auth got db error when trying enumerate users: %s' % ( e, ) )
            return None

        return tuple( ret )

    def get_groups_by_username(self, username):
        groups = []
        session = Session()
        result = None
        try:
            result = session.query(
                User, Person, Group, Role, RoleType).filter(
                User.name == username,
                Person.user_id == User.id,
                Role.groupid == Group.hubid,
                Role.personid == Person.hubid,
                Role.type_id == RoleType.id,
            ).first()
            # everything else than super
            superresult = session.query(
                User, Person, SuperRole, SuperRoleType).filter(
                User.name == username,
                Person.user_id == User.id,
                SuperRole.type_id == SuperRoleType.id,
                SuperRole.personid == Person.hubid).first()
        except DatabaseError, e:
            logger.error('Member auth got db error when trying fetch '
                         'groups for principal {username}: {error}'.format(
                             username=username, error=e))

        if result:
            groups = result.Person.webstatuses + [ result.RoleType.token ]
            if superresult:
                groups.append(superresult.SuperRoleType.token)
        return groups

    # IGroupsPlugin
    def getGroupsForPrincipal(self, principal, request=None):
        # Only give roles for users ( Groups could be supported later if
        # needed )
        if not hasattr(principal, 'getUserName'):
            return []

        username = principal.getUserName()
        # The recursive groups plugin returns wrapped groupdata in their
        # principal - bug?
        # Since we know it's a group, we don't search for the groups
        # group.
        if Products.PlonePAS.interfaces.group.IGroupData.providedBy(username):
            return []
        return self.get_groups_by_username(username)

    # IPropertiesPlugin
    def getPropertiesForUser(self, user, request=None):
        data = {}

        session = Session()
        result = session.query(User, Person).filter(
            User.name == user.getUserName(),
            Person.user_id == User.id).first()

        if result:
            person = result.Person

            data = dict(
                fullname=u'{firstname} {lastname}'.format(
                    firstname=person.firstname, lastname=person.lastname),
                email=person.email or u'',
                )

        return MutablePropertySheet(self.getId(), **data)


    # Called when doing setPropertiesForUser on MutablePropertySheet
    def setPropertiesForUser( self, user, props ):
        # Limit what fields can be set to prevent db errors.
        valid_fields = [ 'fullname', 'email' ]
        data = dict( filter( lambda prop: prop[0] in valid_fields, props.propertyItems() ) )

        # Convert fullname to first and last name (assumes they only have one first name so may not be very accurate)
        if 'fullname' in data:
            names = data.pop( 'fullname' ).split( ' ' )
            data['firstname'], data['lastname'] = names[0], ' '.join( names[1:] )

        sess = Session()

        user = sess.query( User ).filter( User.name == user.getUserName() ).first()

        sess.query( Person ).filter( Person.user_id == user.id ).update( data )
        
    # IUserManagement
    def doChangeUser( self, user_id, password, **kw ):
        sess = Session()
        
        user = sess.query( User ).filter( User.name == user_id ).first()
        
        user.password = password

    def doDeleteUser( self, login ):
        sess = Session()
        
        user = sess.query( User ).filter( User.name == login ).first()
        
        sess.delete( user )
        zope.event.notify(
            ObjectRemovedEvent( user, self, user.id )
        )
        
        return True
        

    # IDeleteCapability
    def allowDeletePrincipal( self, id ):
        return True

    # IPasswordSetCapability
    def allowPasswordSet( self, id ):
        return True


classImplements(
    NUWAuthPlugin,
    IAuthenticationPlugin,
    IUserEnumerationPlugin,
    IGroupsPlugin,
    IPropertiesPlugin,
    IUserManagement,
    IDeleteCapability,
    IPasswordSetCapability
)
