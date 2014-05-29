# Copyright (c) 2012 Mooball IT
# See also LICENSE.txt
from nuw.types.testing import NUWTYPES_INTEGRATION_TESTING
from nuw.types.testing import get_testdata
import lxml.etree
import unittest
import zope.component


class SchemaValidationTest(unittest.TestCase):

    layer = NUWTYPES_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer['portal']
        self.request = self.layer['request']
        doc = zope.component.getMultiAdapter(
            (self.portal, self.request), name='schema.xsd')
        rendered = doc().encode('utf-8')
        self.xmlschema = lxml.etree.XMLSchema(
            lxml.etree.XML(rendered))

    def test_valid(self):
        test_xml = ['person.xml',
                    'group.xml',
                    'supergroup.xml',
                    'role.xml',
                    'grouprole.xml',
                    'record.xml',
                    'file.xml',
                    'superrole.xml',
                   ]
        for filename in test_xml:
            person_xml = lxml.etree.XML(get_testdata(filename))
            self.assertTrue(
              self.xmlschema.validate(person_xml),
              'XML from {filename} failed to validate. {errors}'.format(
                filename=filename, errors=self.xmlschema.error_log)
              )
