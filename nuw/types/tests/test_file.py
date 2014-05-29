# Copyright (c) 2012 Mooball IT
# See also LICENSE.txt
from nuw.types.testing import NUWTYPES_FUNCTIONAL_TESTING
import lxml.etree
import sqlalchemy.exc
import unittest
import zope.component
import zope.interface.verify


class TestFile(unittest.TestCase):

    layer = NUWTYPES_FUNCTIONAL_TESTING

    def test_file_broken_reference(self):
        broken_reference = u"""
        <file
        fileid="129E3F23-ACE8-E011-90F7-005056A20027"
        recordid="23942A20-ACE8-E011-90F7-005056A20027"
        />
        """
        xml = lxml.etree.XML(broken_reference)
        data = dict(xml.items())

        factory = zope.component.getUtility(
            zope.component.interfaces.IFactory, 'file')
        self.assertRaises(sqlalchemy.exc.NoReferenceError, factory, **data)
