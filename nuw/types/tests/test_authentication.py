# Copyright (c) 2012 Mooball IT
# See also LICENSE.txt
from Products.PlonePAS.interfaces.group import IGroupData
from nuw.types.api.auth import APIAuthHelper, USERNAME
from nuw.types.authentication import NUWAuthPlugin
from nuw.types.group import Group
from nuw.types.interfaces import IUnionRep
from nuw.types.member import User, Person
from nuw.types.role import Role, RoleType
from nuw.types.supergroup import SuperGroup
from nuw.types.superrole import SuperRole, SuperRoleType
from nuw.types.testing import NUWTYPES_FUNCTIONAL_TESTING
from nuw.types.testing import NUWTYPES_SQLINTEGRATION_TESTING
from sqlalchemy.exc import DatabaseError
from z3c.saconfig import named_scoped_session
import datetime
import logging
import mock
import nuw.types.authentication
import testfixtures
import transaction
import unittest
import uuid
import zope.component
import zope.interface


Session = named_scoped_session('nuw.types.auth')


class TestAPIAuthenticationUnit(unittest.TestCase):

    def setUp(self):
        self.plugin = APIAuthHelper('test')

    @mock.patch.object(zope.component, 'getUtility')
    def test_api_authenticateCredentials(self, fake_getUtility):
        settings = mock.Mock()
        settings.api_key = 'asdf'

        registry = mock.Mock()
        registry.forInterface.return_value = settings

        fake_getUtility.return_value = registry

        self.assertTupleEqual(
            (None, None),
            self.plugin.authenticateCredentials(dict(login='', password=''))
            )
        self.assertTupleEqual(
            (None, None),
            self.plugin.authenticateCredentials(
                dict(login='jamesbond',
                     password=settings.api_key))
            )
        self.assertTupleEqual(
            (USERNAME, USERNAME),
            self.plugin.authenticateCredentials(
                dict(login=USERNAME,
                     password=settings.api_key))
            )


class TestAuthenticationUnit(unittest.TestCase):

    def setUp(self):
        self.plugin = NUWAuthPlugin('test')

    @mock.patch.object(zope.component, 'getUtility')
    @mock.patch.object(nuw.types.authentication.NUWAuthPlugin,
                       '_query_for_auth_user')
    def test_authenticateCredentials_no_user(self,
                                             fake_query_for_user,
                                             fake_getUtility):
        fake_query_for_user.return_value = None
        fake_getUtility.return_value = mock.Mock()

        self.assertFalse(self.plugin.authenticateCredentials(
            dict(login='foo', password='bar')))

    @mock.patch('nuw.types.authentication.Session')
    def test_get_groups_by_username_error(self,
                                          fake_Session):
        query = mock.Mock()
        query.side_effect = DatabaseError('Sql statement', [], 'foo')

        session = mock.Mock()
        session.query = query
        fake_Session.return_value = session

        with testfixtures.LogCapture(level=logging.ERROR) as l:
            self.plugin.get_groups_by_username('test')
            l.check(
                (nuw.types.authentication.__name__,
                 'ERROR',
                 ("Member auth got db error when trying fetch groups"
                  " for principal test: (str) foo 'Sql statement' []")
                )
                )

    def test_getGroupsForPrincipal(self):
        self.assertListEqual([],
                             self.plugin.getGroupsForPrincipal(None))

        principal = mock.Mock()
        principal.getUserName.return_value = principal
        zope.interface.alsoProvides(principal, IGroupData)

        self.assertListEqual([],
                             self.plugin.getGroupsForPrincipal(principal))

    @mock.patch('nuw.types.authentication.Session')
    def test_getPropertiesForUser(self, fake_Session):
        mockuser = mock.Mock()
        mockuser.getUserName.return_value = 'test'

        query = mock.Mock()
        query.return_value = query
        query.filter.return_value = query
        query.first.return_value = None

        session = mock.Mock()
        session.query = query
        fake_Session.return_value = session

        # no user
        result = self.plugin.getPropertiesForUser(mockuser)
        self.assertListEqual([], result.propertyIds())

        # db query result with Person
        dbresult = mock.Mock()
        dbresult.Person = mock.Mock()
        dbresult.Person.firstname = u'Foo'
        dbresult.Person.lastname = u'bar'
        dbresult.Person.email = u'bar'
        query.first.return_value = dbresult
        result = self.plugin.getPropertiesForUser(mockuser)
        self.assertListEqual(['fullname', 'email'], result.propertyIds())
        self.assertListEqual(['Foo bar', 'bar'],
                             result.propertyValues())


class TestAuthentication(unittest.TestCase):

    layer = NUWTYPES_FUNCTIONAL_TESTING

    def setUp(self):
        self.portal = self.layer['portal']
        self.plugin = self.portal['acl_users'][
            nuw.types.authentication.PLUGIN_NAME]
        self.userdata = dict(name=u'Tom Cameron', password='asdfasdf')
        self.cred = dict(login=self.userdata['name'],
                         password=self.userdata['password'])
        session = Session()
        self.person = Person(str(uuid.uuid4()), firstname=u'Tom',
                        lastname=u'Cameron', webstatus=u'member')
        self.person.user = User(**self.userdata)
        session.add(self.person)

    def test_authenticateCredentials(self):
        self.assertTrue(self.plugin.authenticateCredentials(self.cred))

        self.plugin.limit_to_groups = ['Some Group']
        self.assertFalse(self.plugin.authenticateCredentials(self.cred))

    def test__query_for_user(self):
        self.assertTrue(self.plugin._query_for_auth_user(**self.cred))


class TestAuthenticationGroups(unittest.TestCase):

    layer = NUWTYPES_SQLINTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer['portal']
        self.plugin = self.portal['acl_users'][
            nuw.types.authentication.PLUGIN_NAME]
        self.userdata = dict(name=u'tomcam', password='asdfasdf')
        self.cred = dict(login=self.userdata['name'],
                         password=self.userdata['password'])
        session = Session()
        group = Group(str(uuid.uuid4()), name=u'Mooball')
        session.add(group)

        self.person = Person(str(uuid.uuid4()), firstname=u'Tom',
                        lastname=u'Cameron', webstatus=u'member')
        self.person.user = User(**self.userdata)
        session.add(self.person)
        transaction.commit()

        self.role = Role(str(uuid.uuid4()),
                         personid=self.person.personid,
                         groupid=group.groupid,
                         startdate=datetime.datetime.now(),
                        )
        session.add(self.role)
        self.supergroup = SuperGroup(str(uuid.uuid4()),
                                name=u'Developers',
                               )
        session.add(self.supergroup)

        transaction.commit()
