# Copyright (c) 2012 Mooball IT
# See also LICENSE.txt
from nuw.types.base import INUWItem, IContactDetails, IMappedTable
from nuw.types.member import User
from nuw.types.testing import NUWTYPES_FUNCTIONAL_TESTING
import datetime
import lxml.etree
import unittest
import uuid
import zope.component
import zope.interface.verify


TESTDATAXML = u"""
<person nuwassistid="61911" nuwdbid="NV593855" rownumber="20001"
personid="40942A20-ACE8-E011-90F7-005056A20027" type="Member" title="Mr"
gender="Male" firstname="Jorge" preferredname="Jorge" lastname="Rodriguez"
homeaddress1="39 Chancellor Drive" homesuburb="MULGRAVE" homestate="VIC"
homepostcode="3170" postaddress1="39 Chancellor Drive"
postsuburb="MULGRAVE" poststate="VIC" postpcode="3170" postrts="0"
home="03 9561 3831" work="" fax="" status="Paying"
dob="1955-07-29T00:00:00" employeeid="085" employmenttype="casual" />
"""


class TestAdapter(unittest.TestCase):

    layer = NUWTYPES_FUNCTIONAL_TESTING

    def setUp(self):
        person_xml = lxml.etree.XML(TESTDATAXML)
        self.data = dict(person_xml.items())

    def test_person_table(self):
        table = zope.component.getUtility(IMappedTable, 'person')
        self.assertEqual('person', table.__tablename__)

    def test_person_factory(self):
        factory = zope.component.getUtility(
            zope.component.interfaces.IFactory, 'person')
        self.assertTrue(factory)

        person = factory(**self.data)
        self.assertTrue(isinstance(person.dob, datetime.datetime))
        self.assertEqual(self.data['personid'], INUWItem(person).hubid)
        self.assertEqual(person.personid, INUWItem(person).hubid)
        self.assertEqual(self.data['nuwdbid'], INUWItem(person).nuwdbid)
        self.assertEqual(self.data['postaddress1'],
                         IContactDetails(person).postaddress1)

    def test_person_has_login(self):
        factory = zope.component.getUtility(
            zope.component.interfaces.IFactory, 'person')
        person = factory(str(uuid.uuid4), firstname='Homer')

        self.assertFalse(person.has_login())

        user = User(name='foobar', password='asdf')
        person.user = user
        self.assertFalse(person.has_login())

        user = User(name='roman@mooball.net', password='asdf')
        person.user = user
        self.assertTrue(person.has_login())
