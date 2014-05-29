from five import grok
from zope.interface import Interface
from Products.statusmessages.interfaces import IStatusMessage
from Products.CMFDefault.exceptions import EmailAddressInvalid
from Products.CMFCore.utils import getToolByName
from plone.registry.interfaces import IRegistry
from zope.component import queryUtility
from z3c.saconfig import named_scoped_session
from sqlalchemy import func
from sqlalchemy.types import Unicode
from smtplib import SMTPException
from plone.directives import form
from zope.component import getMultiAdapter
import zope.schema
import sqlalchemy
import json

from nuw.types.admin_area.admin_area import permission, LargeBatch
from nuw.types.admin_area.interfaces import IRecurringSettings, IAdminEmails
from nuw.types.EmailUpdateTool.EmailUpdateTool import send_confirmation_email
from nuw.types.member import EmailExists

from nuw.types.spreedly import spreedly
from nuw.types.member import Person, User
from nuw.types.recurpayment import RecurPayment

from datetime import datetime
from pprint import pprint

grok.templatedir( 'templates' )
SESSION_KEY = 'nuw.types.admin_area.member_search'
Session = named_scoped_session('nuw.types')


class MemberSearch(grok.View):
    grok.name('member-search')
    grok.context(Interface)
    grok.require(permission)

    pagesize = 50

    def update(self):
        '''
        Query and save the query in a batch. Will only grab 'pagesize' items at
        any one time.
        Save a session variable to store the batch index.
        Get the query as specified in 'get_items', and only append to items
        'pagesize' results from 'b_start' to 'b_start + pagesize'
        '''

        query = self.get_items(self.request.form)
        self.itemcount = int(query.count())
        self.b_start = self.request.SESSION.get(SESSION_KEY + self.b_start_str, 0)
        if self.request.get(self.b_start_str, None) is not None:
            self.b_start = int(self.request.get(self.b_start_str))
            self.request.SESSION.set(SESSION_KEY + self.b_start_str, self.b_start)


        self.items = list()
        for item in query[self.b_start:self.b_start+self.pagesize]:
            self.items.append(item)

    def get_items(self, search_filter):
        '''
        Get 'pagesize' people according to the search_filter passed through,
        can only filter by one variable at a time (makes it simpler).

        Will check to see if Person contains the attribute needed for
        the search_filter, and organise accordingly.
        String based searches in Unicode columns will search everything
        in lowercase, and for anything %like%.
        '''
        self.b_start_str = 'b_start_search'
        sess = Session()
        items = sess.query(Person)

        if search_filter.get('pending', None):
            items = items.filter(Person.user_id == None)

        items = items.order_by(Person.id.desc())
        if search_filter.get('filter', None) and search_filter.get('search', None):
            try:
                attribute = getattr(Person, search_filter['filter'])
                if type(attribute.property.columns[0].type) == Unicode:
                    attribute = func.lower(attribute)
                    items = items.filter(attribute.like(
                            '%'+search_filter['search'].lower().strip()+'%'))
                else:
                    items = items.filter(attribute == search_filter['search'])
            except AttributeError:
                return items.filter("0=1")

        return items

    @property
    def batch(self):
        quantum = (self.itemcount >= 2000) or False
        p_range = (quantum and self.b_start >= 5*self.pagesize and 5) or 10

        return LargeBatch(
                self.items, self.itemcount, self.pagesize, start=self.b_start,
                quantumleap=quantum, pagerange=p_range,
                b_start_str=self.b_start_str)


class MemberEmailUpdate(grok.View):
    grok.name('member-emailupdate')
    grok.context(Interface)
    grok.require(permission)

    def update(self):
        '''
        View that handles json from the member-search and sends out a
        confirmation email to the newly specified email.
        Check if person exists, check for valid email address, check to see
        if mailhost is defined. If all well, send off confirmation email to
        new email address.
        '''
        self.errors = str()
        self.success = False
        sess = Session()
        user = None

        person = sess.query(Person).filter(
                Person.personid == self.request.form.get(
                'emailupdate.personid', None)).first()

        if person:
            user = sess.query(User).filter(
                    User.id == person.user_id).first()
        else:
            self.errors = u'Person not found within DB'
            return

        self.email = self.request.form.get('emailupdate.new_email', None)
        if not self.email or self.email == '':
            self.errors += u'Please provide an email address '
            return
        if self.context.unrestrictedTraverse('@@overview-controlpanel').mailhost_warning():
            self.errors += u'No mailhost defined. Unable to update email. '
            return

        username = self.email
        if user:
            username = user.name or username

        try:
            send_confirmation_email(self, self.email, username, person)
        except EmailAddressInvalid as e:
            self.errors += e.args[0] + " "
            return
        except EmailExists as e:
            self.errors += e.args[0] + " "
            return

        self.success = True

    def render(self):
        '''
        Return success or not in Json
        '''
        self.request.response.setHeader("Content-type", "application/json")
        if self.success:
            return json.dumps({"success": True, 'sent': (
                    self.email and (
                    '<br>Sent to: %s' % self.email) or '')})
        else:
            return json.dumps({'error': self.errors})


class MemberPasswordReset(MemberEmailUpdate):
    grok.name('member-passwordreset')

    def update(self):
        '''
        View that handles json from the member-search and sends out a
        password reset email users email.
        Check if person exists, check to see if mailhost is defined. If all
        well, send off password reset email to users email address.
        '''
        self.errors = str()
        self.success = False
        regtool = getToolByName(self.context, 'portal_registration')

        sess = Session()
        person, user = sess.query(Person, User).filter(
                Person.personid == self.request.form.get(
                'passwordreset.personid', None),
                User.id == Person.user_id).first()

        if not person or not user:
            self.errors = u'Person not found within DB'
            return

        self.email = person.email
        if not self.email or self.email == '':
            self.errors += 'User does not have an email address!'
            return

        if self.context.unrestrictedTraverse('@@overview-controlpanel').mailhost_warning():
            self.errors += u'No mailhost defined. Unable to reset password. '
            return

        try:
            regtool.mailPassword(user.name, self.context.REQUEST)
        except SMTPException as e:
            self.errors += e.args[0] + " "
            return
        self.success = True


class Transactions(MemberSearch):
    grok.name('member-trans')

    def get_items(self, search_filter):
        '''
        Get 'pagesize' transactions according to the search_filter passed
        through, can only filter by one variable at a time (makes it simpler).

        Will check to see if Transaction or Payment Method contains the
        attribute needed for the search_filter, and organise accordingly.
        String based searches in Unicode columns will search everything
        in lowercase, and for anything %like%.
        '''
        self.b_start_str = 'b_start_transaction'
        sess = Session()
        items = sess.query(spreedly.Transaction).join(
                'paymentmethod').order_by(spreedly.Transaction.id.desc())

        if search_filter.get('filter', None) and search_filter.get('search', None):
            try:
                if hasattr(spreedly.Transaction, search_filter['filter']):
                    attribute = getattr(spreedly.Transaction, search_filter['filter'])
                else:
                    attribute = getattr(spreedly.PaymentMethod, search_filter['filter'])

                if type(attribute.property.columns[0].type) == Unicode:
                    attribute = func.lower(attribute)
                    items = items.filter(attribute.like(
                            '%'+search_filter['search'].lower().strip()+'%'))
                else:
                    items = items.filter(attribute == search_filter['search'])
            except AttributeError:
                return items.filter("0=1")
        return items


class Methods(MemberSearch):
    grok.name('member-methods')

    def get_items(self, search_filter):
        '''
        Get 'pagesize' payment methods according to the search_filter passed
        through, can only filter by one variable at a time (makes it simpler).

        Will check to see if Payment Method contains the attribute needed for
        the search_filter, and organise accordingly.
        String based searches in Unicode columns will search everything
        in lowercase, and for anything %like%.
        '''
        self.b_start_str = 'b_start_method'
        sess = Session()
        items = sess.query(spreedly.PaymentMethod).order_by(
                spreedly.PaymentMethod.id.desc())

        if search_filter.get('filter', None) and search_filter.get('search', None):
            try:
                attribute = getattr(spreedly.PaymentMethod, search_filter['filter'])

                if type(attribute.property.columns[0].type) == Unicode:
                    attribute = func.lower(attribute)
                    items = items.filter(attribute.like(
                            '%'+search_filter['search'].lower().strip()+'%'))
                else:
                    items = items.filter(attribute == search_filter['search'])
            except AttributeError:
                return items.filter("0=1")
        return items


class RecurringPayments(MemberSearch):
    grok.name('recurring-payments')

    def get_items(self, search_filter):
        self.b_start_str = 'b_start_recur'
        sess = Session()

        items = sess.query(RecurPayment, Person, spreedly.PaymentMethod).filter(
                spreedly.PaymentMethod.personid == RecurPayment.personid,
                Person.personid == RecurPayment.personid,
                spreedly.PaymentMethod.defaulted == True,
                spreedly.PaymentMethod.retained == True).order_by(RecurPayment.next_due)

        if search_filter.get('filter', None) and search_filter.get('search', None):
            try:
                if hasattr(RecurPayment, search_filter['filter']):
                    attribute = getattr(RecurPayment, search_filter['filter'])
                elif hasattr(spreedly.PaymentMethod, search_filter['filter']):
                    attribute = getattr(
                            spreedly.PaymentMethod, search_filter['filter'])
                else:
                    attribute = getattr(Person, search_filter['filter'])

                if type(attribute.property.columns[0].type) == Unicode:
                    attribute = func.lower(attribute)
                    items = items.filter(attribute.like(
                            '%'+search_filter['search'].lower().strip()+'%'))
                else:
                    items = items.filter(attribute == search_filter['search'])
            except AttributeError:
                return items.filter("0=1")
        return items


class RecurringPaymentsDue(grok.View):
    grok.name('recurring-due')
    grok.context(Interface)
    grok.require(permission)

    def update(self):
        '''
        JSON view that allows the admin to set the next due date of a payment.
        '''
        self.errors = str()
        self.success = False
        sess = Session()

        self.payment = sess.query(RecurPayment).filter(
                RecurPayment.id == self.request.form.get(
                'recurdue.id', None).split('-')[1]).first()

        next_due = datetime(int(self.request.form.get('recurdue.year')),
                int(self.request.form.get('recurdue.month')),
                int(self.request.form.get('recurdue.day')))

        if self.payment:
            self.payment.next_due = next_due
        else:
            self.success = False
            self.errors += 'Could not find recurring payment. '
            return

        self.success = True

    def render(self):
        '''
        Return success or not in Json
        '''
        self.request.response.setHeader("Content-type", "application/json")
        if self.success:
            plone = getMultiAdapter((self.context, self.request), name="plone")
            result = plone.toLocalizedTime(self.payment.next_due)
            return json.dumps({"success": True, "result": result,
                    "id": self.request.form.get('recurdue.id', None)})
        else:
            return json.dumps({'error': self.errors})


class RecurringPaymentsToggle(grok.View):
    grok.name('recurring-toggle')
    grok.context(Interface)
    grok.require(permission)

    def update(self):
        '''
        JSON view that toggles the 'deleted' flag on a recurring payment. This
        will cease recurring payments on the card.
        '''
        self.errors = str()
        self.success = False
        sess = Session()

        self.payment = sess.query(RecurPayment).filter(
                RecurPayment.id == self.request.form.get(
                'recurtoggle.id', None).split('-')[1]).first()

        if self.payment:
            if self.payment.deleted:
                self.payment.deleted = False
            else:
                self.payment.deleted = True
        else:
            self.success = False
            self.errors += 'Could not find recurring payment. '
            return

        self.success = True

    def render(self):
        '''
        Return success or not in Json
        '''
        self.request.response.setHeader("Content-type", "application/json")
        if self.success:
            return json.dumps({"success": True, "result": self.payment.deleted,
                    "id": self.request.form.get('recurtoggle.id', None)})
        else:
            return json.dumps({'error': self.errors})

class JoinFormRecurring(form.SchemaEditForm):
    """
    Configuration panel for charges of each period of member fees.
    """
    zope.interface.implements(IRecurringSettings)

    grok.name('recur-charges')
    grok.context(Interface)
    grok.require(permission)

    schema = IRecurringSettings

    label = "Join Form Recurring Charges"
    description = """
            The recurring charge that is applied to each period.
            Leave field blank if the period should not be used.
            Changing values on this form will only affect new applications.
            """

    def getContent(self):
        registry = queryUtility(IRegistry)
        return registry.forInterface(IRecurringSettings)

    def applyChanges(self, data):
        registry = queryUtility(IRegistry)
        settings = registry.forInterface(IRecurringSettings)

        settings.recur_week = data.get('recur_week', None)
        settings.recur_month = data.get('recur_month', None)
        settings.recur_quarter = data.get('recur_quarter', None)
        settings.recur_year = data.get('recur_year', None)
        settings.recur_week_market_research = data.get('recur_week_market_research', None)
        settings.recur_month_market_research = data.get('recur_month_market_research', None)
        settings.recur_quarter_market_research = data.get('recur_quarter_market_research', None)
        settings.recur_year_market_research = data.get('recur_year_market_research', None)
        settings.recur_week_community = data.get('recur_week_community', None)
        settings.recur_quarter_community = data.get('recur_quarter_community', None)
        settings.recur_year_community = data.get('recur_year_community', None)

    def update(self):
        self.request.set('disable_border', True)
        self.request.set('disable_plone.leftcolumn', True)
        self.request.set('disable_plone.rightcolumn', True)
        super(JoinFormRecurring, self).update()


class AdminEmails(form.SchemaEditForm):
    """
    Configuration panel for admin email address recipients.
    """
    zope.interface.implements(IRecurringSettings)

    grok.name('admin-emails')
    grok.context(Interface)
    grok.require(permission)

    schema = IAdminEmails

    label = "Administrator Emails"
    description = """
            The following emails will be used for notifications from the
            associated sections of the site.
            """

    def getContent(self):
        registry = queryUtility(IRegistry)
        return registry.forInterface(IAdminEmails)

    def applyChanges(self, data):
        registry = queryUtility(IRegistry)
        settings = registry.forInterface(IAdminEmails)

        settings.join_email = data.get('join_email', None)
        settings.fail_email = data.get('fail_email', None)
        settings.general_email = data.get('general_email', None)
        self.context.email_from_address = data.get('general_email', None)
        settings.fees_email = data.get('fees_email', None)

    def update(self):
        self.request.set('disable_border', True)
        self.request.set('disable_plone.leftcolumn', True)
        self.request.set('disable_plone.rightcolumn', True)
        super(AdminEmails, self).update()


def get_join_admin_email():
    registry = queryUtility(IRegistry)
    settings = registry.forInterface(IAdminEmails)
    if settings and hasattr(settings, 'join_email'):
        return settings.join_email

def get_fail_admin_email():
    registry = queryUtility(IRegistry)
    settings = registry.forInterface(IAdminEmails)
    if settings and hasattr(settings, 'fail_email'):
        return settings.fail_email

def get_general_admin_email():
    registry = queryUtility(IRegistry)
    settings = registry.forInterface(IAdminEmails)
    if settings and hasattr(settings, 'general_email'):
        return settings.general_email

def get_fees_admin_email():
    registry = queryUtility(IRegistry)
    settings = registry.forInterface(IAdminEmails)
    if settings and hasattr(settings, 'fees_email'):
        return settings.fees_email

def get_debug_email():
    registry = queryUtility(IRegistry)
    settings = registry.forInterface(IAdminEmails)
    if settings and hasattr(settings, 'debug_email'):
        return settings.debug_email