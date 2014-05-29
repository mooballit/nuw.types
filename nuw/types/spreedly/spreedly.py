from nuw.types import Base
from sqlalchemy import Column, Integer, String, Sequence, DateTime,\
        ForeignKey, Unicode, Float, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from nuw.types.base import apply_data
from z3c.saconfig import named_scoped_session
import zope.schema
import datetime
import spreedlycore
from mooball.plone.spreedlycore.configlet import SiteSpreedlyCredentials, ISpreedlyLoginSettings

Session = named_scoped_session('nuw.types')

# DB Tables

class PaymentGateway( Base ):
    __tablename__ = 'gateway'

    id = Column( Integer, Sequence( 'gatewayid' ), primary_key = True )
    token = Column( String )
    type = Column( String )


class IPaymentMethod(zope.interface.Interface):

    token = zope.schema.TextLine(
        title=u'Spreedly Token'
        )

    personid = zope.schema.TextLine(
        title=u'Person UUID'
        )

    first_name = zope.schema.TextLine(
        title=u'First Name'
        )

    last_name = zope.schema.TextLine(
        title=u'Last Name',
        )

    number = zope.schema.TextLine(
        title=u'CC Number',
        )

    card_type = zope.schema.TextLine(
        title=u'Card Type'
        )

    month = zope.schema.Int(
        title=u'Month'
        )

    year = zope.schema.Int(
        title=u'Year'
        )

    email = zope.schema.TextLine(
        title=u'Email',
        )

    address1 = zope.schema.TextLine(
        title=u'Address 1',

        )
    address2 = zope.schema.TextLine(
        title=u'Address 2',
        )

    city = zope.schema.TextLine(
        title=u'City',

        )
    state = zope.schema.TextLine(
        title=u'State',
        )

    zip = zope.schema.TextLine(
        title=u'Zip',
        )

    country = zope.schema.TextLine(
        title=u'Country',
        )

    phone = zope.schema.TextLine(
        title=u'Phone Number',
        )

    defaulted = zope.schema.Bool(
        title=u'Default?',
        )

    retained = zope.schema.Bool(
        title=u'Retained?',
        )


class PaymentMethod( Base ):
    __tablename__ = 'paymentmethod'
    zope.interface.implements(IPaymentMethod)

    id = Column( Integer, Sequence( 'paymentmethodid' ), primary_key = True )
    token = Column( String )
    personid = Column( UUID, ForeignKey( 'person.personid' ) )

    first_name = Column( Unicode )
    last_name = Column( Unicode )

    number = Column( String )
    card_type = Column( String )
    month = Column( Integer )
    year = Column( Integer )

    email = Column( String )
    address1 = Column( String )
    address2 = Column( String )
    city = Column( String )
    state = Column( String )
    zip = Column( String )
    country = Column( String )
    phone = Column( String )

    defaulted = Column( Boolean, default = False )
    retained = Column( Boolean, default = False )

    def __init__(self, **kwargs):
        apply_data(self, IPaymentMethod, kwargs)


class Transaction( Base ):
    __tablename__ = 'transaction'

    id = Column( Integer, Sequence( 'transactionid' ), primary_key = True )
    token = Column( String )
    gatewayid = Column( Integer, ForeignKey( 'gateway.id' ) )
    paymentmethodid = Column( Integer, ForeignKey( 'paymentmethod.id' ) )
    amount = Column( Float )
    created = Column( DateTime, default = datetime.datetime.now )
    status = Column( String )
    component = Column( String )
    orderid = Column( String )

    paymentmethod = relationship(PaymentMethod, primaryjoin=paymentmethodid == PaymentMethod.id)
# Helper functions

def get_connection():
    '''
    Returns an spreedlycore.APIConnection that uses the configured credentials
    '''
    credentials = SiteSpreedlyCredentials()
    login = credentials.getLogin()
    secret = credentials.getSecret()

    if not login or not secret:
        raise Warning("Admin has incomplete Credit Card API credentials. Please warn the Admin.")

    return spreedlycore.APIConnection(login, secret)

def get_default_gateway(connection):
    '''
    Returns the configured default payment gateway as a spreedlycore.PaymentGateway object
    '''
    credentials = SiteSpreedlyCredentials()
    default_gateway = credentials.getGateway()

    if not default_gateway:
        raise Warning("Admin has no default Credit Card API gateway chosen. Please warn the Admin.")

    return spreedlycore.PaymentGateway(connection, default_gateway)

def delete_method(pm, person_id):
    sess = Session()
    db_method = db_get_payment_method(pm.token)
    if db_method.defaulted:
        # TODO Check to see whether a recurring payer, if not, delete.
        return ("Please change to another default card before deleting.", "info")
    if db_method.personid == person_id:
        pm.redact()
        sess.delete(db_method)
        return None
    else:
        return ("You are not authorised to delete this!", "error")

def db_get_payment_method(token):
    sess = Session()
    return sess.query(PaymentMethod).filter(PaymentMethod.token == unicode(token)).first()

def db_get_gateway(token):
    sess = Session()
    return sess.query(PaymentGateway).filter(PaymentGateway.token == unicode(token)).first()

def db_add_method(pm, person_id, default = False, retain = False):
    pm.load()
    data = pm.data

    db_payment = db_get_payment_method(pm.token)
    if not db_payment:
        sess = Session()
        # TODO: It would be better to use an apply method which can iterate
        # the fields based on an interface.
        payment_method = PaymentMethod(token=pm.token,
                                       personid=person_id,
                                       defaulted=default,
                                       retained=retain,
                                       phone=data.get('phone_number', None),
                                       **data)
        sess.add(payment_method)
        db_payment = db_get_payment_method(pm.token)

    return db_payment

def db_add_gateway(pg):
    gateway_type = None

    for gateway in pg.api.gateways():
        if pg.token == gateway.token:
            gateway_type = unicode(gateway.data['gateway_type'])
    if gateway_type is None:
        return None

    db_gateway = db_get_gateway(pg.token)
    if not db_gateway:
        sess = Session()
        payment_gateway = PaymentGateway(token = unicode(pg.token), type = gateway_type)
        sess.add(payment_gateway)
        db_gateway = db_get_payment_method(pg.token)

    return db_gateway

def charge( pm, db_method_id, pg, db_gateway_id, person_id, amount, component, order_id=None):
    '''
    Will charge the payment method the amount in AUD against the default payment gateway
    '''
    sess = Session()
    try:
        transaction = pg.transaction(pm, int(amount * 100), 'AUD', description = component)
    except spreedlycore.APIRequest.RequestFailed, e:
        transaction_token = spreedlycore.search_dict(e.xml, 'token')
        if len(transaction_token):
            transaction_token = transaction_token[0]

        transaction_state = spreedlycore.search_dict(e.xml, 'state')
        if len(transaction_state):
            transaction_state = transaction_state[0]

        sess.add(Transaction(token = transaction_token, gatewayid = db_gateway_id, paymentmethodid = db_method_id, amount = amount, status = transaction_state, component = component, orderid = order_id))
        raise

    sess.add(Transaction(token = transaction.token, gatewayid = db_gateway_id, paymentmethodid = db_method_id, amount = amount, status = transaction.data['state'], component = component, orderid = order_id))

    return transaction

def db_get_user_payment_methods( person_id, only_default = False, only_retained = False ):
    '''
    Returns the stored payment methods for a user. If only_default is True, it will only return the default payment method.
    '''
    sess = Session()
    if only_default:
        return sess.query(PaymentMethod).filter(PaymentMethod.personid == person_id, PaymentMethod.defaulted == True).order_by(PaymentMethod.defaulted.desc())
    elif only_retained:
        return sess.query(PaymentMethod).filter(PaymentMethod.personid == person_id, PaymentMethod.retained == True).order_by(PaymentMethod.defaulted.desc())
    else:
        return sess.query(PaymentMethod).filter(PaymentMethod.personid == person_id).order_by(PaymentMethod.defaulted.desc())

def set_user_payment_method( connection, token, person_id, retain = False, default = False):
    method = spreedlycore.PaymentMethod(connection, token)

    if retain:
        try:
            method.retain()
        except spreedlycore.APIRequest.RequestFailed, e:
            raise

    db_add_method(method, person_id, default, retain)

    return method

def db_get_user_transactions( person_id, limit = 20 ):
    '''
    Will return the latest transactions made using one of the users payment methods limited by limit
    '''
    sess = Session()

    methods = db_get_user_payment_methods(person_id)
    if methods.count() == long(0):
        return None

    transactions = []
    count = long(0)
    for method in methods:
        method_transaction = sess.query(Transaction).filter(Transaction.paymentmethodid == method.id).order_by(Transaction.created.desc()).limit(limit)
        for transaction in method_transaction:
            transactions += [transaction]
            count += long(1)
            if count >= long(limit):
                break
    if count < limit:
        limit = count
    return transactions[:limit]
