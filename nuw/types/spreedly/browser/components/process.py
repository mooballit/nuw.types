from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from Products.statusmessages.interfaces import IStatusMessage

from pcommerce.core.browser.components.base import BaseComponent
from pcommerce.core import PCommerceMessageFactory as _
from pcommerce.core import interfaces

from nuw.types.spreedly.data import SpreedlyPaymentData
from nuw.types.spreedly import spreedly
import spreedlycore

import datetime, string

class ProcessComponent(BaseComponent):
    index = ViewPageTemplateFile('process.pt')

    def __init__(self, context, request):
        self.context = context
        self.request = request
        self.order = interfaces.IOrder(self.context)
        self.cart = interfaces.IShoppingCart(self.context)
        self.data = self.order.paymentdata or SpreedlyPaymentData()

        if 'errors' in dir(self.data):
            if not isinstance(self.data.errors, dict):
                self.data.errors = dict()

    def __call__(self):
        """
        If retained card chosen, and ends up here, this means that an error
        has occured, redirect with an error status message to payment page.
        """
        if not self.data.needprocessform:
            IStatusMessage(self.request).addStatusMessage(_(self.data.errors[self.data.token]), "error")
            self.request.response.redirect("@@checkout?checkout.stepid=%s" % str(int(self.data.paymentstepid)))
        else:
            return self.index()

    def validate(self):
        """
        Check page to see if Token in query, do processing and error checks.
        Form will initially redirect to Spreedly to send payment details,
        therefore this validation happens only on the return from Spreedly.
        """
        if 'token' in self.request["QUERY_STRING"]:
            self.data.processingtoken = True
            for param in self.request["QUERY_STRING"].split('&'):
                if 'token' in param:
                    self.data.token = param.split('=')[1]
        
        self.data.errors = dict()
        
        try:
            self.data.connection = spreedly.get_connection()
        except Warning, e:
            IStatusMessage(self.request).addStatusMessage(_(unicode(e)), "error")
            self.data.processingtoken = False
            return False
        
        try:
            self.data.gateway = spreedly.get_default_gateway(self.data.connection)
        except Warning, e:
            IStatusMessage(self.request).addStatusMessage(_(unicode(e)), "error")
            self.data.processingtoken = False
            return False
        
        # Check to see if payment method in database, if not, add it.
        try:
            method = spreedlycore.PaymentMethod(self.data.connection, self.data.token)
            db_method = spreedly.db_add_method(method, self.data.person_id)
            db_method_id = db_method.id
        except spreedlycore.APIRequest.RequestFailed, e:
            self.error_checking(e)

        # Check to see if gateway method in database, if not, add it.
        try:
            db_gateway = spreedly.db_add_gateway(self.data.gateway)
            db_gateway_id = db_gateway.id
        except spreedlycore.APIRequest.RequestFailed, e:
            self.error_checking(e)
        
        # Acquire method, charge the card, and retrieve returned data about the transaction
        if len(self.data.errors) == 0:
            try:
                self.data.transaction = spreedly.charge(method, db_method_id,
                        self.data.gateway, db_gateway_id, self.data.person_id,
                        self.order.totalincl, 'Shop - '+str(self.order.orderid),
                        self.order.orderid)
            except spreedlycore.APIRequest.RequestFailed, e:
                self.error_checking(e)

        return len(self.data.errors) == 0
    
    def process(self):
        if self.data.needprocessform:
            self.data.method = spreedly.db_get_payment_method(self.data.token)
        
        return self.data
    
    def renders(self):
        """
        Render page, only if the user is anonymous or the user has chosen to
        use a custom credit card.
        This view will only render the first time (if applicable) to take 
        form details and then set itself to not render for the second round
        when returned back from Spreedly.
        If a retained card is chosen, and has errors, pass off to __call__
        so that a redirect can happen.
        """
        if not self.data.needprocessform and self.data.errors.has_key(self.data.token):
            return True
        return self.data.needprocessform and not self.data.processingtoken

    def error_checking(self, e):
        for error in e.field_errors:
            if error.has_key('attribute'):
                self.data.errors[error['attribute']] = error['text']
        if len(e.errors):
            self.data.errors[self.data.token] = ''
            for error in e.errors:
                self.data.errors[self.data.token] += error['text'] + ' '
            IStatusMessage(self.request).addStatusMessage(_(self.data.errors[self.data.token]), "error")
        self.data.processingtoken = False

# ------------------------v Template Specific Functions v--------------------- #

    def api_login(self):
        try:
            self.data.connection = spreedly.get_connection()
        except Warning, e:
            IStatusMessage(self.request).addStatusMessage(_(unicode(e)), "error")
            return False
        return self.data.connection.login

    def redirect(self):
        """
        Tell the Spreedly form in checkout template to redirect back to this view.
        checkout.next is a cue card for pcommerce to update its processed steps.
        """
        if self.data.processstepid is None:
            self.data.processstepid = int(self.request.form.get('checkout.stepid', 0)) + 1
        return "%s/@@checkout?checkout.stepid=%s&checkout.next=1" % (self.context.absolute_url(), self.data.processstepid)

    def data(self):
        return self.data

    def firstname(self):
        return self.order.address.firstname

    def lastname(self):
        return self.order.address.lastname

    def valid_years(self):
        now = datetime.date.today()
        return [str(year) for year in range(now.year, now.year + 20)]

# ------------------------^ Template Specific Functions ^--------------------- #
