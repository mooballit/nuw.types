# coding: utf-8
# Copyright (c) 2012 Mooball IT
# See also LICENSE.txt
from nuw.types.api.change import Change
from nuw.types.api.change import IChange
from nuw.types.member import IPerson
from nuw.types.member import Person
from nuw.types.testing import NUWTYPES_FUNCTIONAL_TESTING
from z3c.saconfig import named_scoped_session
import datetime
import lxml.etree
import transaction
import unittest
import zope.interface


Session = named_scoped_session('nuw.types')


class TestChangeUnit(unittest.TestCase):

    def test_interfaces(self):
        self.assertTrue(
            zope.interface.verify.verifyClass(
                IChange, Change))


class TestChangeView(unittest.TestCase):

    layer = NUWTYPES_FUNCTIONAL_TESTING

    def setUp(self):
        transaction.begin()
        session = Session()
        person = Person(title='Mr', firstname=u'Róman'.encode('latin-1'),
                        lastname='Joost',
                        email=u'roman@mooball.com',
                        nuwdbid=u'123123',
                        nuwassistid=u'666',
                        type='Member',
                        personid='50922A20-ACE8-E011-90F7-005056A20027')
        change = Change(action='add',
                        modified=datetime.datetime.today(),
                        principal=person.email,
                        oid=person.hubid, otype=person.metatype)
        session.add(person)
        session.add(change)
        self.change = change

    def test_referenced_obj(self):
        self.assertTrue(IPerson.providedBy(self.change.referenced_obj))

    def test_change_view(self):
        self.change.id = 255
        view = zope.component.getMultiAdapter(
            (self.change, self.layer['request']), name='index')
        result = lxml.etree.XML(view())
        self.assertEqual('add', result.get('action'))
        self.assertEqual(str(self.change.id), result.get('id'))
        self.assertEqual(str(self.change.oid), result.get('oid'))
        self.assertEqual(self.change.principal, result.get('principal'))
        person = result.xpath('//person')[0]
        self.assertEqual(u'Róman',
                         person.get('firstname'))
        self.assertEqual(u'Joost'.encode('latin-1'),
                         person.get('lastname'))
        self.assertEqual(u'Member', person.get('type'))
        self.assertEqual(u'123123', person.get('nuwdbid'))
        self.assertEqual(u'666', person.get('nuwassistid'))
