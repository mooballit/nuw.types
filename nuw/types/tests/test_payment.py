# Copyright (c) 2012 Mooball IT
# See also LICENSE.txt
from mooball.plone.spreedlycore.configlet import ISpreedlyLoginSettings
from nuw.types.browser.join import PaymentForm
from nuw.types.member import Person
from nuw.types.spreedly.spreedly import PaymentMethod
from nuw.types.testing import NUWTYPES_FUNCTIONAL_TESTING
from plone.registry.interfaces import IRegistry
from pyquery import PyQuery
from z3c.saconfig import named_scoped_session
import lxml.builder
import lxml.etree
import mock
import spreedlycore
import unittest
import uuid
import zope.component


Session = named_scoped_session('nuw.types')


class TestPaymentMethod(unittest.TestCase):

    layer = NUWTYPES_FUNCTIONAL_TESTING

    def test_paymentmethod_factory(self):
        method = PaymentMethod(token='asdf', first_name='Mark',
                               personid=str(uuid.uuid4()),
                               last_four_digits='ignored')
        self.assertEqual('asdf', method.token)


class TestPaymentStep(unittest.TestCase):

    layer = NUWTYPES_FUNCTIONAL_TESTING

    def setUp(self):
        self.token = 'asdf'
        self.gateway_token = 'gateway-token'

        session = Session()
        self.request = self.layer['request']
        self.portal = self.layer['portal']
        self.view = zope.component.getMultiAdapter(
            (self.portal, self.request), name='join_payment.html')
        registry = zope.component.getUtility(
            IRegistry).forInterface(ISpreedlyLoginSettings)
        registry.spreedly_login = u'asdf'
        registry.spreedly_secret = u'secret'

        self.person = Person(str(uuid.uuid4()),
                             firstname=u'Maik',
                             lastname=u'Ainsel',
                             email='maik@mooball.net',
                             homeaddress1='Rowland St',
                             homeaddress2='Coorparoo',
                             homesuburb='Coorparoo',
                            )
        session.add(self.person)

    @mock.patch('spreedlycore.APIConnection', autospec=True)
    def test_payment_view_renders(self, FakeAPIConnection):
        self.request.form['nuw.types.uuid'] = self.person.hubid
        conn = FakeAPIConnection('asdf', 'secret')
        conn.login = 'asdf'

        pq = PyQuery(self.view())
        self.assertEqual(
            self.person.email,
            pq('input[name="credit_card[email]"]').attr('value'))

    @mock.patch('spreedlycore.PaymentMethod', autospec=True)
    @mock.patch('spreedlycore.APIConnection', autospec=True)
    def test_payment_view_errors(self,
                                 FakeAPIConnection,
                                 FakePaymentMethod):
        # don't fail with a stacktrace
        pq = PyQuery(self.view())
        self.assertTrue(pq('strong.error'))

        self.request.form['nuw.types.uuid'] = str(uuid.uuid4())
        pq = PyQuery(self.view())
        self.assertTrue(pq('strong.error'))

        # so much setup ...
        self.request.form['nuw.types.uuid'] = self.person.hubid
        self.request.form['token'] = self.token
        conn = FakeAPIConnection('asdf', 'secret')
        conn.login = 'asdf'
        pay_method = FakePaymentMethod(conn, self.token)
        pay_method.data = dict(
            card_type='visa',
            first_name=self.person.firstname,
            last_name=self.person.lastname,
            data=dict(),
            errors=dict(
                error=[dict(attribute='year',
                            key='errors.expired',
                            text='Year is expired'
                           ),
                       dict(attribute='month',
                            key='errors.invalid',
                            text='Month is invalid',
                           ),
                      ]
                )
            )

        # ... so little testing
        pq = PyQuery(self.view())
        self.assertEqual(2, len(pq('.error li')))
        pay_method.load.assert_called_once_with()

    @mock.patch('nuw.types.spreedly.spreedly.charge')
    @mock.patch('nuw.types.spreedly.spreedly.get_default_gateway')
    @mock.patch('spreedlycore.PaymentGateway', autospec=True)
    @mock.patch('spreedlycore.PaymentMethod', autospec=True)
    @mock.patch.object(spreedlycore.APIConnection, 'gateways')
    def test_payment_payify_successful(self,
                                  FakeAPIConnection,
                                  FakePaymentMethod,
                                  FakeGateWay,
                                  fake_get_default_gateway,
                                  fake_charge):

        self.request.form['nuw.types.uuid'] = self.person.hubid
        self.request.form['token'] = self.token

        conn = FakeAPIConnection('asdf', 'secret')
        conn.gateways.return_value = [FakeGateWay(conn, self.token)]
        conn.gateways()

        gateway = FakeGateWay(conn, self.token)
        gateway.api = conn
        gateway.token = self.gateway_token
        gateway.data = dict(gateway_type='test')

        pay_method = FakePaymentMethod(conn, self.token)
        pay_method.token = self.token
        pay_method.data = dict(
            card_type='visa',
            data=dict(first_name=self.person.firstname,
                      last_name=self.person.lastname,
                      frequency='weekly',
                     )
            )
        fake_get_default_gateway.return_value = gateway
        fake_get_default_gateway()

        self.view.payify(self.token, 'weekly')
        self.assertEqual(302, self.request.response.status)


class TestPaymentViewUnit(unittest.TestCase):

    def test_paymentview_get_errors(self):
        view = PaymentForm(None, None)
        method = mock.Mock()
        self.assertRaises(AssertionError, view.get_errors, method)

        method.data = dict(errors='')
        self.assertTrue(isinstance(view.get_errors(method), list))

        method.data = dict(errors={})
        self.assertTrue(isinstance(view.get_errors(method), list))

        method.data = dict(errors=[])
        self.assertTrue(isinstance(view.get_errors(method), list))

    @mock.patch('nuw.types.spreedly.spreedly.charge')
    @mock.patch.object(PaymentForm, 'connection')
    @mock.patch.object(PaymentForm, 'get_person')
    @mock.patch.object(PaymentForm, 'get_payment_methods')
    @mock.patch.object(PaymentForm, 'get_payment_gateways')
    @mock.patch.object(PaymentForm, 'get_payment_amount')
    def test_payment_payify_error(self,
                                  fake_get_payment_amount,
                                  fake_get_payment_gateways,
                                  fake_get_payment_methods,
                                  fake_get_person,
                                  fake_connection,
                                  fake_charge):
        view = PaymentForm(None, None)
        token = 'asdf'

        obj = mock.Mock()
        obj.id = 1

        fake_get_person.return_value = obj
        fake_get_payment_amount.return_value = 40
        fake_get_payment_gateways.return_value = [obj, obj]
        fake_get_payment_methods.return_value = [obj, obj]

        fake_charge.side_effect = spreedlycore.APIRequest.RequestFailed(
            lxml.etree.tostring(
                lxml.builder.E.transaction(
                    lxml.builder.E.message(text=u'Some shit happened')
                    )
                )
            )
        view.payify(token, 'weekly')
        self.assertEqual(1, len(view.errors))
        self.assertTrue(fake_charge.called)

        fake_get_person.assert_called_once_with()
        fake_get_payment_methods.assert_called_once_with(obj, token)
        fake_get_payment_gateways.assert_called_once_with(token)
        fake_get_payment_amount.assert_called_once_with('weekly')
