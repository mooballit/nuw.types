# Copyright (c) 2012 Mooball IT
# See also LICENSE.txt
from nuw.types.base import IMappedTable
from nuw.types.base import INUWItem
from nuw.types.file import IFile, File
from nuw.types.group import IGroup, Group
from nuw.types.grouprecord import IGroupRecord, GroupRecord
from nuw.types.grouprole import IGroupRole, GroupRole
from nuw.types.member import IPerson, Person
from nuw.types.record import IRecord, Record
from nuw.types.role import IRole, Role
from nuw.types.supergroup import ISuperGroup, SuperGroup
from nuw.types.superrole import ISuperRole, SuperRole
from nuw.types.testing import NUWTYPES_FUNCTIONAL_TESTING
from nuw.types.testing import NUWTYPES_SQLINTEGRATION_TESTING
from nuw.types.testing import get_testdata
from z3c.saconfig import named_scoped_session
import lxml.etree
import sqlalchemy.exc
import transaction
import unittest
import uuid
import zope.component


Session = named_scoped_session('nuw.types')


class TestModelsUnit(unittest.TestCase):

    ifaces = [(IGroup, Group),
              (ISuperGroup, SuperGroup),
              (IGroupRole, GroupRole),
              (IRole, Role),
              (IPerson, Person),
              (IRecord, Record),
              (IFile, File),
              (ISuperRole, SuperRole),
              (IGroupRecord, GroupRecord),
             ]

    def test_interfaces(self):
        for iface, klass in self.ifaces:
            self.assertTrue(
                zope.interface.verify.verifyClass(
                    INUWItem, klass))
            self.assertTrue(
                zope.interface.verify.verifyClass(
                    iface, klass))


class DataMock(object):

    def __init__(self, name):
        self.__tablename__ = name


class TestMapperBase(unittest.TestCase):

    # !!! Don't change the order. That's a cheap way to get references
    # right for e.g. role, which needs to link between person and group
    mapped = [('person', ['dob']),
              ('group', []),
              ('role', []),
              ('supergroup', []),
              ('grouprole', []),
              ('record', []),
              ('file', []),
              ('superrole', ['superrole']),
              ('grouprecord', []),
             ]


class TestMapperLookup(TestMapperBase):

    layer = NUWTYPES_FUNCTIONAL_TESTING

    def test_mapper_lookup(self):
        for name, attributes in self.mapped:
            table = zope.component.getUtility(IMappedTable, name)
            self.assertTrue(hasattr(table, '__tablename__'))

    def test_mapper_create_instance(self):
        for name, attributes in self.mapped:
            xml = lxml.etree.XML(
                get_testdata('{name}.xml'.format(name=name)))
            data = dict(xml.xpath('//{name}[1]'.format(name=name))[0].items())

            factory = zope.component.getUtility(
                zope.component.interfaces.IFactory, name)
            self.assertTrue(factory)
            obj = factory(**data)
            guidattribute = '{name}id'.format(name=name)
            self.assertEqual(data[guidattribute], INUWItem(obj).hubid)
            self.assertEqual(data['nuwdbid'], INUWItem(obj).nuwdbid)

    def test_mapper_datamapper(self):
        for name, attributes in self.mapped:
            xml = lxml.etree.XML(
                get_testdata('{name}.xml'.format(name=name)))
            data = dict(xml.xpath('//{name}[1]'.format(name=name))[0].items())

            table = zope.component.getUtility(IMappedTable, name)
            obj = DataMock(name)
            table.apply_mapped_data(obj, data)


class TestMapperLookup(TestMapperBase):

    layer = NUWTYPES_SQLINTEGRATION_TESTING

    def test_mapper_export_xml(self):
        session = Session()
        for name, attributes in self.mapped:
            xml = lxml.etree.XML(
                get_testdata('{name}.xml'.format(name=name)))
            data = dict(xml.xpath('//{name}[1]'.format(name=name))[0].items())

            factory = zope.component.getUtility(
                zope.component.interfaces.IFactory, name)
            obj = factory(**data)
            session.add(obj)
            transaction.commit()

            table = zope.component.getUtility(IMappedTable, name=name)
            obj = session.query(table).one()
            view = zope.component.getMultiAdapter(
                (obj, self.layer['request']), name='xml')
            exported = lxml.etree.XML(view())
            self.assertListEqual(sorted(exported.keys()),
                                 self._get_expected_data_keys(data))
            self.assertListEqual(
                sorted([exported.get(k) for k in exported.keys()
                        if k in attributes]),
                sorted([data.get(k) for k in data.keys()
                       if k in attributes])
                )
            self.assertEqual(name, exported.tag)

    def _get_expected_data_keys(self, data, ignored=None):
        if ignored is None:
            ignored = ['rownumber', 'webadaptorid', 'filenumber']
        return sorted([x for x in data.keys() if x not in ignored])


class TestMapperBrokenReferences(unittest.TestCase):

    layer = NUWTYPES_FUNCTIONAL_TESTING
    mapped = [('role', ['person', 'group']),
              ('file', ['record']),
              ('grouprole', ['supergroup', 'grouprole']),
              ('superrole', ['supergroup', 'person']),
             ]

    def test_mapper_broken_reference(self):
        for tname, references in self.mapped:
            attr_fields = references + [tname]
            attrs = [('{ref}id'.format(ref=x), str(uuid.uuid4()))
                     for x in attr_fields]
            factory = zope.component.getUtility(
                zope.component.interfaces.IFactory, tname)
            self.assertRaises(sqlalchemy.exc.NoReferenceError, factory,
                              **dict(attrs))
