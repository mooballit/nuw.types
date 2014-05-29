from five import grok
from zope.interface import Interface
from nuw.types import Base
from nuw.types.spreedly import spreedly
from nuw.types.spreedly.spreedly import PaymentMethod
from nuw.types.admin_area.interfaces import IAdminEmails
from nuw.types.member import Person
from sqlalchemy import Column, Integer, String, Sequence, DateTime,\
        ForeignKey, Float, Boolean
from sqlalchemy.dialects.postgresql import UUID
from z3c.saconfig import named_scoped_session
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from Products.CMFCore.utils import getToolByName
from plone.registry.interfaces import IRegistry
from zope.component import queryUtility

from datetime import date, datetime
from dateutil.relativedelta import relativedelta
import spreedlycore
import logging


logger = logging.getLogger(__name__)
Session = named_scoped_session('nuw.types')


class RecurPayment(Base):
    __tablename__ = 'recurpayment'

    id = Column(Integer, Sequence('recurpaymentid'), primary_key = True)
    personid = Column(UUID, ForeignKey('person.personid'))
    amount = Column(Float)
    frequency = Column(String)
    last_success = Column(DateTime)
    next_due = Column(DateTime)
    deleted = Column(Boolean)


class CRONJobChargePayments(grok.View):
    grok.name('cronjob-charge')
    grok.context(Interface)

    erroneous_payment_tpl = ViewPageTemplateFile('templates/recurerrorpayment.pt')

    def render(self):
        sess = Session()
        recurring_payments = sess.query(RecurPayment, PaymentMethod).filter(
                RecurPayment.next_due <= date.today(),
                RecurPayment.deleted == False,
                PaymentMethod.personid == RecurPayment.personid,
                PaymentMethod.defaulted == True,
                PaymentMethod.retained == True)

        connection = spreedly.get_connection()
        gateway = spreedly.get_default_gateway(connection)
        db_gateway = spreedly.db_add_gateway(gateway)

        for payment in recurring_payments:
            recur = payment.RecurPayment
            method = payment.PaymentMethod
            spdly_meth = spreedlycore.PaymentMethod(connection, method.token)

            try:
                transaction = spreedly.charge(
                    pm=spdly_meth, db_method_id=method.id,
                    pg=gateway, db_gateway_id=db_gateway.id,
                    person_id=method.personid, amount=recur.amount,
                    component='Membership Fees')
            except spreedlycore.APIRequest.RequestFailed, e:
                errors = ' | '.join(
                        err.get('text', None) for err in e.field_errors)
                logger.exception(
                        "RecurPayment: Failed Charge %s %s (%s), $%s at %s, Error: '%s'"
                        % (method.first_name, method.last_name,
                        method.personid, recur.amount, datetime.today(),
                        errors))

                registry = queryUtility(IRegistry)
                settings = registry.forInterface(IAdminEmails)
                if settings and hasattr(settings, 'fees_email'):
                    mhost = getToolByName(self, 'MailHost')
                    email = settings.fees_email
                    mail_content = self.erroneous_payment_tpl(
                        to_email = email,
                        name = method.first_name + ' ' + method.last_name,
                        email = method.email,
                        errors = errors,
                        frequency = recur.frequency, amount = recur.amount,
                        personid = method.personid, portal_url = self.context.portal_url,
                        recurid = recur.id,
                    )
                    mhost.send( mail_content )

                continue

            recur.last_success = datetime.today()
            recur.next_due = _next_due_date(recur.next_due, recur.frequency)
            logger.info(
                    "RecurPayment: Charged %s %s (%s), $%s at %s"
                    % (method.first_name, method.last_name,
                    method.personid, recur.amount, datetime.today()))


def _next_due_date(next_due, frequency):
    if frequency == 'recur_week':
        return next_due + relativedelta(weeks=1)

    if frequency == 'recur_month':
        return next_due + relativedelta(months=1)

    if frequency == 'recur_quarter':
        return next_due + relativedelta(months=3)

    if frequency == 'recur_year':
        return next_due + relativedelta(years=1)

    if frequency == 'recur_week_market_research':
        return next_due + relativedelta(weeks=1)

    if frequency == 'recur_month_market_research':
        return next_due + relativedelta(months=1)

    if frequency == 'recur_quarter_market_research':
        return next_due + relativedelta(months=3)

    if frequency == 'recur_year_market_research':
        return next_due + relativedelta(years=1)

    if frequency == 'recur_week_community':
        return next_due + relativedelta(weeks=1)

    if frequency == 'recur_quarter_community':
        return next_due + relativedelta(months=3)

    if frequency == 'recur_year_community':
        return next_due + relativedelta(years=1)

def check_existing_recurring_payment(person):
    sess = Session()
    count = sess.query(RecurPayment).filter(
            RecurPayment.personid == person.personid).count()
    return count > 0

def add_recurring_payment(person, frequency, amount):
    sess = Session()
    today = date.today()
    due = _next_due_date(today, frequency)

    recurring = RecurPayment(
            personid=person.personid, amount=amount,
            frequency=frequency, last_success=today,
            next_due=due, deleted=False)
    sess.add(recurring)

    logger.info(
            "RecurPayment: Added %s %s (%s), %s, $%s at %s"
            % (person.firstname, person.lastname,
            person.personid, frequency,
            amount, today))
