# Copyright (c) 2012 Mooball IT
# See also LICENSE.txt
from nuw.types.browser.join import AutoWizardWidgetTraversal
from nuw.types.browser.join import JoinFormWizard
from nuw.types.group import Group
from nuw.types.member import Person, IPerson
from nuw.types.role import Role
from nuw.types.testing import NUWTYPES_FUNCTIONAL_TESTING
from nuw.types.testing import NUWTYPES_SQLINTEGRATION_TESTING
from plone.testing.z2 import Browser
from pyquery import PyQuery
from z3c.saconfig import named_scoped_session
from zope.traversing.interfaces import TraversalError
import re
import transaction
import unittest
import uuid
import z3c.form.interfaces
import zope.component


Session = named_scoped_session('nuw.types')


class TestJoinForm(unittest.TestCase):

    layer = NUWTYPES_FUNCTIONAL_TESTING

    def test_join_form(self):
        portal = self.layer['portal']
        portal_url = portal.absolute_url()
        self.browser = Browser(self.layer['app'])
        self.browser.handleErrors = False
        self.browser.open(portal_url + '/joinwizard.html')

        pq = PyQuery(self.browser.contents)
        self.assertEqual(JoinFormWizard.label,
                         pq('h1.documentFirstHeading').text())
        self.assertEqual(JoinFormWizard.description,
                         pq('div.description').text())
        self.assertFalse(pq('#personalinfo-widgets-agency'))
        self.assertFalse(pq('#personalinfo-widgets-hubid'))
        self.assertFalse(pq('#personalinfo-widgets-nuwdbid'))
        self.assertFalse(pq('#personalinfo-widgets-nuwassistid'))
        self.assertFalse(pq('#personalinfo-widgets-metatype'))
        self.assert_widget_position(self.browser,
                                    'personalinfo-widgets-firstname',
                                    'personalinfo-widgets-homeaddress1')

    def assert_widget_position(self, browser, widget1, widget2):
        """
        Assert the position of widgets. We'd like to see the widget1
        to be rendered before the widget2 parameter.

        :param widget1: fieldid of the widget
        :type widget1: string
        """
        pq = PyQuery(browser.contents)
        widgetid = re.compile('\w+.\w+.(?P<name>.*)')
        fields = []
        for x in pq('#collectdetails .field *:last-child'):
            if x.get('name') is None:
                continue
            fields.append(
                widgetid.match(x.get('name')).groupdict()['name']
                )
        widget1 = pq('#{0}'.format(widget1))[0].get('name')
        widget2 = pq('#{0}'.format(widget2))[0].get('name')
        widget1_pos = fields.index(
            widgetid.match(widget1).groupdict()['name'])
        widget2_pos = fields.index(
            widgetid.match(widget2).groupdict()['name'])
        self.assertLessEqual(widget1_pos, widget2_pos)


class TestJoinIntegration(unittest.TestCase):

    layer = NUWTYPES_SQLINTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer['portal']
        portal_url = self.portal.absolute_url()
        self.browser = Browser(self.layer['app'])
        self.browser.handleErrors = False
        self.browser.open(portal_url + '/joinwizard.html')

        session = Session()
        self.union_site = Group(
            groupid=str(uuid.uuid4()),
            name=u'Mc Donalds',
            sitesuburb=u'Paddington',
            type=u'Union Site', sitestate='VIC')
        session.add(self.union_site)
        self.agency = Group(groupid=str(uuid.uuid4()),
                  name=u'Mooball',
                  sitesuburb=u'Parkville',
                  type=u'Employment Agency',
                  sitestate='QLD')
        session.add(self.agency)

        transaction.commit()

    def test_join_process(self):
        self.browser.getControl('First Name').value = 'Maik'
        self.browser.getControl('Last Name').value = 'Ainsel'
        self.browser.getControl('Unit/Street No').value = 'Lakeside View'
        self.browser.getControl('Street Address').value = 'Rowland Promenade'
        self.browser.getControl('Suburb', index=0).value = 'Lakeside'
        self.browser.getControl('State', index=0).displayValue = ['QLD']
        self.browser.getControl('Postcode', index=0).value = '5231'
        self.browser.getControl('Home Number').value = '23423'
        self.browser.getControl('E-mail').value = 'foo@mooball.net'
        self.browser.getControl(
            name='personalinfo.widgets.dob-day').value = '10'
        self.browser.getControl(
            name='personalinfo.widgets.dob-year').value = '2000'
        self.browser.getControl('Permanent').selected = True

        wp_widget_queryid = (
            'workinformation.widgets.worksite_id.widgets.query')
        wp_button_id = (
            'workinformation.widgets.worksite_id.buttons.search')
        self.browser.getControl(name=wp_widget_queryid).value = 'Mc'
        self.browser.getControl(name=wp_button_id).click()
        self.browser.getControl('Mc Donalds', index=0).selected = True

        self.browser.getControl('Continue').click()

        control = self.browser.getControl('Continue')
        self.assertRaises(AssertionError, control.click)

    def test_join_process_labour_hire(self):
        # 1. step - collection of details
        self.browser.getControl('First Name').value = 'Maik'
        self.browser.getControl('Last Name').value = 'Ainsel'
        self.browser.getControl('Unit/Street No').value = 'Lakeside View'
        self.browser.getControl('Street Address').value = 'Rowland Promenade'
        self.browser.getControl('Suburb', index=0).value = 'Lakeside'
        self.browser.getControl('State', index=0).displayValue = ['QLD']
        self.browser.getControl('Postcode', index=0).value = '5231'
        self.browser.getControl('Home Number').value = '23423'
        self.browser.getControl('E-mail').value = 'foo@mooball.net'
        self.browser.getControl(
            name='personalinfo.widgets.dob-day').value = '10'
        self.browser.getControl(
            name='personalinfo.widgets.dob-year').value = '2000'
        self.browser.getControl('Permanent').selected = True

        wp_widget_queryid = (
            'workinformation.widgets.worksite_id.widgets.query')
        wp_button_id = (
            'workinformation.widgets.worksite_id.buttons.search')
        self.browser.getControl(name=wp_widget_queryid).value = 'Mc'
        self.browser.getControl(name=wp_button_id).click()
        self.browser.getControl('Mc Donalds', index=0).selected = True

        ag_widget_queryid = (
            'workinformation.widgets.agency.widgets.query')
        ag_button_id = (
            'workinformation.widgets.agency.buttons.search')
        self.browser.getControl(name=ag_widget_queryid).value = 'Mo'
        self.browser.getControl(name=ag_button_id).click()
        self.browser.getControl('Mooball', index=0).selected = True
        self.browser.getControl('Continue').click()

        # 2. step - confirmation
        worksitelabel = (
            u'{site.name} ({site.sitesuburb} - {site.sitestate})'.format(
                site=self.union_site))
        pq = PyQuery(self.browser.contents)
        self.assertEqual(
            'Maik', pq('#personalinfo-widgets-firstname').text())
        self.assertEqual(
            worksitelabel, pq('#workinformation-widgets-worksite_id').text())

        self.assertRaises(LookupError,
                          self.browser.getControl, 'Clear')
        self.assertTrue(self.browser.getControl('Cancel'))
        control = self.browser.getControl('Continue')
        # will raise an AssertionError due to an unsuccessful connection
        # to spreedly in the payment form
        self.assertRaises(AssertionError, control.click)

        # 4. verify created data
        session = Session()
        result = session.query(Person).one()
        self.assertTrue(IPerson.providedBy(result))
        self.assertEqual(u'Maik', result.firstname)
        self.assertEqual(u'Ainsel', result.lastname)

        # we expect two roles to be created
        # Agency employed members will have the employee role at the
        # labour hire agency and the labour hire role at the work site.
        ws_role = session.query(Role).filter_by(
            personid=result.hubid, groupid=self.union_site.groupid).one()
        self.assertEqual('Labour Hire', ws_role.role.token)

        ag_role = session.query(Role).filter_by(
            personid=result.hubid, groupid=self.agency.groupid).one()
        self.assertEqual('Employee', ag_role.role.token)

        # two roles and a person should be created. That's what we
        # expect as changes coming through from the API
        self.assertEqual(3,
                         len(self.portal.portal_syncapi.api_get_changes()))


class FakeSession(dict):
    p_changed = False


class TestWizardWidgetTraversal(unittest.TestCase):

    layer = NUWTYPES_FUNCTIONAL_TESTING

    def setUp(self):
        self.request = self.layer['request']
        self.portal = self.layer['portal']
        self.request.SESSION = FakeSession()
        self.wizard = zope.component.getMultiAdapter(
            (self.portal, self.request), name='joinwizard.html')
        self.wizard.update()
        self.traverser = AutoWizardWidgetTraversal(self.wizard, self.request)

    def test_traverse_wizard_widget(self):
        result = self.traverser._form_traverse(
            self.wizard.form_instance, 'worksite_id')
        self.assertTrue(result)
        self.assertTrue(z3c.form.interfaces.IWidget.providedBy(result))

    def test_traverse_wizard(self):
        self.assertRaises(
            TraversalError, self.traverser.traverse, 'not_found', None)
        result = self.traverser.traverse('firstname', None)
        self.assertTrue(result)
        self.assertTrue(z3c.form.interfaces.IWidget.providedBy(result))
