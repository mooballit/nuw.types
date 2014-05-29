# Copyright (c) 2012 Mooball IT
# See also LICENSE.txt
from nuw.types.base import INUWItem
from nuw.types.group import Group, IGroup
from nuw.types.member import Person, IPerson
from nuw.types.role import Role, RoleType
from nuw.types.role import get_roletype_from_person
from nuw.types.testing import NUWTYPES_FUNCTIONAL_TESTING
from z3c.saconfig import named_scoped_session
import lxml.etree
import unittest
import uuid
import zope.component
import zope.interface.verify


TESTDATAXML = u"""
<role nuwassistid="2001215" nuwdbid="NC00042NC000063"
roleid="219E3F23-ACE8-E011-90F7-005056A20027"
personid="40942A20-ACB8-E011-90F7-005056A20027"
groupid="AB40C0D7-52EB-E111-B6A4-005056A2000A" role="Employee"
startdate="1991-05-20T00:00:00"/>
"""
Session = named_scoped_session('nuw.types')


class TestRole(unittest.TestCase):

    layer = NUWTYPES_FUNCTIONAL_TESTING

    def setUp(self):
        session = Session()
        self.person = Person(personid='40942A20-ACB8-E011-90F7-005056A20027',
                        firstname='Gregory',
                        lastname='Winton')
        self.group = Group(groupid='AB40C0D7-52EB-E111-B6A4-005056A2000A',
                      name='Foobar Group')
        session.add_all([self.person, self.group])

    def test_role_factory(self):
        xml = lxml.etree.XML(TESTDATAXML)
        data = dict(xml.items())

        factory = zope.component.getUtility(
            zope.component.interfaces.IFactory, 'role')
        self.assertTrue(factory)

        session = Session()
        session.add(factory(**data))

        role = session.query(Role).filter(Role.hubid == data['roleid']).one()
        self.assertEqual(uuid.UUID(data['roleid']),
                         uuid.UUID(INUWItem(role).hubid))
        self.assertEqual(data['nuwdbid'], INUWItem(role).nuwdbid)
        self.assertTrue(IGroup.providedBy(role.group))
        self.assertTrue(IPerson.providedBy(role.person))

    def test_get_roletype_from_person(self):
        xml = lxml.etree.XML(TESTDATAXML)
        data = dict(xml.items())

        factory = zope.component.getUtility(
            zope.component.interfaces.IFactory, 'role')
        session = Session()
        session.add(factory(**data))

        expected = session.query(RoleType).one()
        self.assertEqual([expected],
                         get_roletype_from_person(self.person))

        session.add(RoleType(token=u'foo', name=u'AnotherRole'))
        self.assertEqual([expected],
                         get_roletype_from_person(self.person))

