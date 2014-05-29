# Copyright (c) 2012 Mooball IT
# See also LICENSE.txt
from Products.CMFCore.utils import getToolByName
from nuw.types.api.auth import USERNAME
from nuw.types.api.change import Change
from nuw.types.api.settings import IAPISettings
from nuw.types.api.tool import GetData
from nuw.types.api.tool import ISyncAPITool
from nuw.types.api.tool import MockTable
from nuw.types.api.tool import PushChanges
from nuw.types.api.tool import RETURNCODES
from nuw.types.api.tool import SyncAPITool
from nuw.types.api.tool import result_factory
from nuw.types.group import IGroup
from nuw.types.member import IPerson
from nuw.types.member import Person
from nuw.types.role import Role
from nuw.types.testing import NUWTYPES_FUNCTIONAL_TESTING
from nuw.types.testing import NUWTYPES_INTEGRATION_TESTING
from nuw.types.testing import NUWTYPES_SQLINTEGRATION_TESTING
from nuw.types.testing import get_testdata
from plone.app.testing import SITE_OWNER_PASSWORD, SITE_OWNER_NAME
from plone.registry.interfaces import IRegistry
from plone.testing.z2 import Browser
from z3c.saconfig import named_scoped_session
from zope.publisher.browser import TestRequest
import StringIO
import lxml.etree
import mock
import os.path
import transaction
import unittest
import urllib
import uuid
import zope.interface


Session = named_scoped_session('nuw.types')


def get_error(result, index=1):
    """Returns the n-th error item (@index) in the result XML"""
    error = result.xpath('//error[{index}]'.format(
        index=index))[0]
    return error


class TestAPIUnit(unittest.TestCase):

    def setUp(self):
        self.request = mock.Mock()
        self.request.form = {}

        self.settings = mock.Mock()
        self.settings.api_key = None
        self.settings.output_encoding = 'latin-1'

        self.registry = mock.Mock()
        self.registry.forInterface.return_value = self.settings

    def test_interfaces(self):
        self.assertTrue(
            zope.interface.verify.verifyClass(
                ISyncAPITool, SyncAPITool))

    @mock.patch.object(zope.component, 'getUtility')
    def test_push_changes_no_apikey_set(self, fake_getUtility):
        fake_getUtility.return_value = self.registry

        view = PushChanges(None, self.request)
        result = lxml.etree.XML(view.render())
        error = get_error(result)
        self.assertEqual(u'2', error.get('code'))
        self.assertIn(RETURNCODES[2], error.text)
        fake_getUtility.assert_called_once_with(IRegistry)

    @mock.patch.object(zope.component, 'getUtility')
    def test_push_changes_invalid_credentials(self, fake_getUtility):
        self.settings.api_key = 'secret'
        fake_getUtility.return_value = self.registry
        self.request.form = dict(api_key='invalid')

        view = PushChanges(None, self.request)
        result = lxml.etree.XML(view.render())
        error = get_error(result)
        self.assertEqual(u'1', error.get('code'))
        self.assertIn(RETURNCODES[1], error.text)


class TestResultUnit(unittest.TestCase):

    def test_status(self):
        success = result_factory([dict(code=0, msg='')]).xpath('//error[1]')[0]
        failure = result_factory([dict(code=1, msg='')]).xpath('//error[1]')[0]
        self.assertEqual('0', success.get('code'))
        self.assertEqual('1', failure.get('code'))


class TestAPIToolBase(unittest.TestCase):

    def setUp(self):
        self.api_key = u'asdf'
        self.portal = self.layer['portal']
        self.request = self.layer['request']
        self.tool = getToolByName(self.portal, SyncAPITool.id)
        registry = zope.component.getUtility(
            IRegistry).forInterface(IAPISettings)
        registry.api_key = self.api_key

        changes = get_testdata('person.xml')
        self.tool.api_push_changes(changes)
        transaction.commit()

    def view(self, name):
        return zope.component.getMultiAdapter(
            (self.tool, self.request), name=name)()


class TestAPIToolInvalid(TestAPIToolBase):

    layer = NUWTYPES_SQLINTEGRATION_TESTING

    def test_push_changes_invalid_xml(self):
        xml_documents = ['person_invalid.xml',
                         'person_invalid_data.xml',
                         'person_invalid_data2.xml',
                        ]
        for doc in xml_documents:
            expected = '3'
            changes = get_testdata(doc)
            self.request.form = dict(api_key=self.api_key, changes=changes)
            result = lxml.etree.XML(self.view('push_changes'))
            error = get_error(result)
            self.assertEqual(
                expected, error.get('code'),
                'Expected code {exp} but got {result} for XML {doc}'.format(
                    exp=expected, result=error.get('code'), doc=doc)
                )

        self.request.form = dict(api_key=self.api_key,
                                 changes='<?adfasdfhurz')
        result = lxml.etree.XML(self.view('push_changes'))
        error = get_error(result)
        self.assertEqual(u'3', error.get('code'))

    def test_clear_changes_invalid_ids(self):
        self.request.form = dict(api_key=self.api_key, ids=['asdf'])
        result = lxml.etree.XML(self.view('clear_changes'))
        error = get_error(result)
        self.assertTrue(RETURNCODES[4] in error.text)

    def test_clear_changes_wrong_ids(self):
        generated = str(uuid.uuid1())
        self.request.form = dict(api_key=self.api_key, ids=[generated])
        result = lxml.etree.XML(self.view('clear_changes'))
        error = get_error(result)
        self.assertIn(RETURNCODES[4], error.text)

    def test_get_changes_invalid_credentials(self):
        self.request.form = dict(api_key='invalid')
        result = lxml.etree.XML(self.view('get_changes'))
        error = get_error(result)
        self.assertIn(RETURNCODES[1], error.text)


class TestAPIToolPushChanges(unittest.TestCase):

    layer = NUWTYPES_SQLINTEGRATION_TESTING

    def test_push_changes_insert(self):
        tool = getToolByName(self.layer['portal'], 'portal_syncapi')
        changes = get_testdata('person.xml')
        result = tool.api_push_changes(changes)
        self.assertListEqual(result, [])

    def test_push_changes_duplicates(self):
        tool = getToolByName(self.layer['portal'], 'portal_syncapi')
        changes = get_testdata('person_duplicate.xml')
        tool.api_push_changes(changes)

        session = Session()
        result = session.query(Person).all()
        person = result[0]
        self.assertEqual(1, len(result))
        self.assertEqual('Stephen', person.firstname)
        self.assertEqual('Wallan', person.homesuburb)

    def test_push_changes_broken_reference(self):
        tool = getToolByName(self.layer['portal'], 'portal_syncapi')

        # data we need to successfully import one role
        tool.api_push_changes(get_testdata('person.xml'))
        tool.api_push_changes(get_testdata('group.xml'))

        changes = get_testdata('role_broken_reference.xml')
        result = tool.api_push_changes(changes)[0]
        self.assertTrue(result['code'] == 5)

        session = Session()
        self.assertEqual(1, len(session.query(Role).all()))


class TestAPIToolPushChangesUpdate(TestAPIToolBase):

    layer = NUWTYPES_SQLINTEGRATION_TESTING

    def test_push_changes_update(self):
        session = Session()
        result = session.query(Person).filter_by(
            hubid='40942A20-ACE8-E011-90F7-005056A20027').first()
        self.assertEqual('Rodriguez', result.lastname)
        self.assertEqual('Member', result.type.token)

        changes = get_testdata('person_update.xml')
        result = self.tool.api_push_changes(changes)
        self.assertListEqual(result, [])

        session = Session()
        result = session.query(Person).filter_by(
            hubid='40942A20-ACE8-E011-90F7-005056A20027').first()
        self.assertEqual('Martin', result.lastname)
        self.assertEqual('Contact', result.type.token)

        changes = session.query(Change).filter_by(action='update').all()
        self.assertEqual(1, len(changes))

    def test_push_changes_update_norecord(self):
        changes = get_testdata('person_update_norecord.xml')
        result = self.tool.api_push_changes(changes)
        self.assertEqual(4, result[0]['code'])

    def test_push_changes_delete(self):
        changes = get_testdata('person_delete.xml')
        result = self.tool.api_push_changes(changes)
        self.assertListEqual(result, [])

        session = Session()
        result = session.query(Person).filter_by(
            hubid='40942A20-ACE8-E011-90F7-005056A20027').all()
        self.assertListEqual([], result)

        changes = session.query(Change).filter_by(action='delete').all()
        self.assertEqual(1, len(changes))

    def test_push_changes_update_error(self):
        session = Session()
        result = session.query(Person).filter_by(
            hubid='40942A20-ACE8-E011-90F7-005056A20027').one()
        employeeid = result.employeeid

        changes = get_testdata('person_invalid_data3.xml')
        self.request.form = dict(api_key=self.api_key, changes=changes)
        lxml.etree.XML(self.view('push_changes'))

        updated = session.query(Person).filter_by(
            hubid='40942A20-ACE8-E011-90F7-005056A20027').one()
        self.assertNotEqual(employeeid, updated.employeeid)
        self.assertEqual(u'2074', updated.employeeid)


class TestAPIToolClearChanges(TestAPIToolBase):

    viewname = 'clear_changes'
    layer = NUWTYPES_SQLINTEGRATION_TESTING

    def test_clear_changes(self):
        session = Session()
        change_oids = [x.id for x in session.query(Change).all()]
        result = self.tool.api_clear_changes(change_oids)
        self.assertListEqual([], result)
        self.assertEqual([], session.query(Change).all())
        self.assertEqual(4, session.query(Person).count())


class TestAPIToolGetChanges(TestAPIToolBase):

    viewname = 'get_changes'
    layer = NUWTYPES_SQLINTEGRATION_TESTING

    def test_get_changes(self):
        self.request.form = dict(api_key=self.api_key)
        result = lxml.etree.XML(self.view('get_changes'))
        self.assertEqual(4, len(result.getchildren()))


class TestAPIToolBrowser(unittest.TestCase):

    layer = NUWTYPES_SQLINTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer['portal']
        portal_url = self.portal.absolute_url()
        self.browser = Browser(self.layer['app'])
        self.browser.open(portal_url + '/login_form')
        self.browser.getControl(name='__ac_name').value = SITE_OWNER_NAME
        self.browser.getControl(name='__ac_password').value = SITE_OWNER_PASSWORD
        self.browser.getControl(name='submit').click()

    def test_controlpanelform(self):
        self.browser.getLink('Site Setup').click()
        self.browser.getLink('API Settings').click()
        self.browser.getControl('API Key').value = 'asdf'
        self.browser.getControl('Save').click()

        registry = zope.component.getUtility(
            IRegistry).forInterface(IAPISettings)
        self.assertEqual('asdf', registry.api_key)

    def test_xmlimport(self):
        self.browser.getLink('Site Setup').click()
        self.browser.getLink('API XML Import').click()
        docpath = os.path.join(os.path.dirname(__file__),
                               'testdata', 'person.xml')
        docfile = StringIO.StringIO(open(docpath, 'r').read())
        control = self.browser.getControl(name='form.widgets.xml')
        fileControl = control.mech_control
        fileControl.add_file(docfile, filename=docpath)

        self.browser.getControl('Import').click()
        self.assertTrue('successfully imported' in self.browser.contents)
        tool = getToolByName(self.portal, 'portal_syncapi')
        result = tool.api_get_changes()
        self.assertEqual(4, len(result))


class TestAPIToolBrowserHeaders(unittest.TestCase):

    layer = NUWTYPES_FUNCTIONAL_TESTING

    def setUp(self):
        self.portal = self.layer['portal']
        self.browser = Browser(self.layer['app'])
        self.registry = zope.component.getUtility(
            IRegistry).forInterface(IAPISettings)
        self.registry.api_key = u'asdf'
        transaction.commit()

    @property
    def expected_ct(self):
        return 'text/xml; charset={}'.format(self.registry.output_encoding)

    def test_headers_not_configured(self):
        self.registry.api_key = None
        transaction.commit()

        self.browser.open(
            self.portal.absolute_url() + '/portal_syncapi/get_changes')
        self.assertEqual(self.expected_ct,
                         self.browser.headers.get('Content-Type'))

    def test_headers_configured(self):
        self.browser.open(
            self.portal.absolute_url() +
            '/portal_syncapi/get_changes?api_key={}'.format('asdf'))
        self.assertEqual(self.expected_ct,
                         self.browser.headers.get('Content-Type'))

    def test_headers_invalid_credentials(self):
        self.browser.open(
            self.portal.absolute_url() +
            '/portal_syncapi/get_changes?api_key=foo')
        self.assertEqual(self.expected_ct,
                         self.browser.headers.get('Content-Type'))


class TestAPIToolBrowserPushChanges(TestAPIToolBase):

    layer = NUWTYPES_INTEGRATION_TESTING

    def test_browser_push_changes_authenticated(self):
        browser = Browser(self.layer['app'])
        changes = get_testdata('group.xml')
        url = '{base}/portal_syncapi/push_changes?{data}'.format(
            base=self.portal.absolute_url(),
            data=urllib.urlencode(
                dict(api_key=self.api_key, changes=changes)
                )
            )
        browser.open(url)

        # We can now filter changes which have been pushed by the via
        # the API, rather then imported or changed by the user via the
        # UI
        session = Session()
        change = session.query(Change).filter_by(principal=USERNAME).first()
        self.assertTrue(IGroup.providedBy(change.referenced_obj))

        change = self.tool.api_get_changes()[0]
        self.assertTrue(IPerson.providedBy(change.referenced_obj))


class TestAPIGetData(unittest.TestCase):

    layer = NUWTYPES_FUNCTIONAL_TESTING

    def setUp(self):
        self.api_key = u'asdf'
        self.portal = self.layer['portal']
        self.request = self.layer['request']
        self.tool = getToolByName(self.portal, SyncAPITool.id)
        self.registry = zope.component.getUtility(
            IRegistry).forInterface(IAPISettings)
        self.registry.api_key = self.api_key
        self.obj = MockTable(Person).__of__(self.tool)
        transaction.commit()

        self.view = zope.component.getMultiAdapter(
            (self.obj, self.request), name='get_data')

    def test_api_get_data_person_check_key(self):
        result = self.view()
        self.assertIn(u'Invalid credentials', result)

    def test_api_get_data_person(self):
        self.request.form = dict(api_key=self.api_key)
        changes = get_testdata('person.xml')
        self.tool.api_push_changes(changes)
        exported = lxml.etree.XML(self.view())
        self.assertEqual(4, len(exported.xpath('//person')))

    def test_api_get_data_person_filter_guid(self):
        changes = get_testdata('person.xml')
        person = lxml.etree.XML(changes).xpath('//person[1]')[0]
        self.request.form = dict(api_key=self.api_key,
                                 guid=person.get('personid'))
        self.tool.api_push_changes(changes)
        exported = lxml.etree.XML(self.view())
        self.assertEqual(1, len(exported.xpath('//person')))


class TestGetDataUnit(unittest.TestCase):

    def test_getdata__get_guid_filter(self):
        request = TestRequest()
        request.form['guid'] = 'foobar'

        dummy = mock.Mock()
        view = GetData(dummy, request)
        self.assertIsNone(view._get_guid_filter())

        request.form['guid'] = object
        self.assertIsNone(view._get_guid_filter())
