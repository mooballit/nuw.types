# coding=utf-8
# Copyright (c) 2012 Mooball IT
# See also LICENSE.txt
from nuw.types.browser.activation import VerifyMember, PasswordReset
from nuw.types.browser.activation import check_password_strength
from nuw.types.interfaces import IActivationContext
from nuw.types.member import User, Person
from nuw.types.testing import NUWTYPES_INTEGRATION_TESTING
from nuw.types.testing import NUWTYPES_SQLINTEGRATION_TESTING
from plone.testing.z2 import Browser
from z3c.saconfig import named_scoped_session
from zope.publisher.browser import TestRequest
import Products.CMFDefault.exceptions
import datetime
import mock
import plone.app.z3cform.interfaces
import transaction
import unittest
import uuid
import zope.interface


Session = named_scoped_session('nuw.types')


class TestMemberHasLogin(unittest.TestCase):

    layer = NUWTYPES_SQLINTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer['portal']
        zope.interface.alsoProvides(self.portal, IActivationContext)
        session = Session()
        self.personid = str(uuid.uuid4())
        user = User(name='foo@bar.com', password='asdf')
        person = Person(self.personid, firstname=u'Tom',
                        email=user.name, lastname='Cameron')
        person.user = user
        session.add(person)
        transaction.commit()

    def test_member_has_login(self):
        portal_url = self.portal.absolute_url()
        browser = Browser(self.layer['app'])
        url = '/'.join([portal_url, self.personid, 'verifymember.html'])
        browser.open(url)

        self.assertTrue(VerifyMember.memberHasLoginErrorLabel
                        in browser.contents)
        self.assertTrue(browser.getLink('I would like to'))


class TestMember(unittest.TestCase):

    layer = NUWTYPES_INTEGRATION_TESTING

    def setUp(self):
        self.request = self.layer['request']
        self.portal = self.layer['portal']

    def test_verifymember_invalid_email(self):
        self.request.form['form.widgets.email'] = u'foobar'
        zope.interface.alsoProvides(
            self.request,
            plone.app.z3cform.interfaces.IPloneFormLayer)

        view = VerifyMember(self.portal, self.request)
        view.updateWidgets()
        data, errors = view.extractData()
        self.assertIsInstance(
            errors[-1].error,
            Products.CMFDefault.exceptions.EmailAddressInvalid
            )


class TestVerifyMemberUnit(unittest.TestCase):

    @mock.patch.object(VerifyMember, '_is_same_person')
    def test_verifymember_verify(self, fake_is_same_person):
        today = datetime.datetime.today()
        data = dict(dob=today, lastname='Foo',
                    homepostcode='1233', email='foo@bar.com')
        context = mock.Mock()
        person = mock.Mock(spec=Person)
        person.lastname = data['lastname']
        person.homepostcode = data['homepostcode']
        person.dob = None
        person.email = u''
        person.webstatus = u'foobar'
        context.table = person

        fake_is_same_person.return_value = False

        # no dob set
        view = VerifyMember(context, object)
        self.assertIsNone(view.verify(data))

        # duplicate member
        person.dob = data['dob']
        data.update(dob=today.date())
        self.assertIsNone(view.verify(data))
        self.assertFalse(person.email)

        # wrong webstatus
        fake_is_same_person.return_value = True
        self.assertIsNone(view.verify(data))
        self.assertFalse(person.email)

        # everything correct
        person.webstatus = u'member'
        self.assertIsNotNone(view.verify(data))
        self.assertTrue(person.email)

    def test_passwordreset_update(self):
        request = TestRequest()
        context = mock.Mock()
        person = mock.Mock(spec=Person)
        person.user = None
        context.table = person

        view = PasswordReset(context, request)
        try:
            view.update()
        except zope.component.ComponentLookupError:
            # the view class calls it's super and throws a
            # ComponentLookupError. But we're only concerned what
            # happens before in this test
            pass
        self.assertFalse(view.verified)

    def test_check_password_strength(self):
        self.assertRaises(
            zope.interface.Invalid,
            check_password_strength,
            u'foo')
        self.assertRaises(
            zope.interface.Invalid,
            check_password_strength,
            u'foobar')
        self.assertRaises(
            zope.interface.Invalid,
            check_password_strength,
            u'1foobar')
        self.assertRaises(
            zope.interface.Invalid,
            check_password_strength,
            u'Áóóóó1')
        self.assertTrue(check_password_strength(u'1Foobar'))
        self.assertTrue(check_password_strength(u'oobarF1'))
        self.assertTrue(check_password_strength(u'oobF1a'))
        self.assertTrue(check_password_strength(u'FOOBaR1'))
