from zope.interface import implements
from zope.component import getMultiAdapter
from Products.CMFCore.utils import getToolByName

from Products.Five.browser import BrowserView
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile

from pcommerce.core.interfaces import IPaymentView, IOrder

from nuw.types.spreedly.data import SpreedlyPaymentData
from nuw.types.spreedly import spreedly
from nuw.types import member


class SpreedlyPayment(BrowserView):
    template = ViewPageTemplateFile('payment.pt')
    implements(IPaymentView)

    methods = None

    def __call__(self):
        return self.template()

    def __init__(self, payment, request):
        self.payment = payment
        self.context = payment.context
        self.request = request

        self.order = IOrder(self.context)
        self.data = self.order.paymentdata or SpreedlyPaymentData()

        if not isinstance(self.data.errors, dict):
            self.data.errors = dict()

        # Minimise DB requests by only doing once.
        if not isinstance(self.methods, list):
            user = member.get_user_person(self.context)
            if user != None:
                self.data.person_id = user.personid
            else:
                self.data.person_id = None

            # Acquire retained methods from database
            self.methods = spreedly.db_get_user_payment_methods(self.data.person_id, only_retained = True)
            self.data.methods_count = self.methods.count()

    def validate(self):
        """
        Check to see which credit card was chosen, if 'null', set up payment
        to process a custom credit card in the Spreedly form. Else, set it
        up to skip the Spreedly form and just process the card.
        """
        token = self.request.form.get('token', 0)
        if self.data.person_id and self.data.methods_count != 0 and token and token != 'null':
            new_method = None

            for method in self.methods:
                if method.token == token:
                    new_method = method

            if new_method is None:
                return False

            self.data.method = new_method
            self.data.token = token
            self.data.needprocessform = False
        else:
            self.data.method = None
            self.data.token = None
            self.data.needprocessform = True

        return True

    def process(self):
        """
        Save step position for future redirects if an error occurs, and
        calculate new shipping price according to custom algorithm.
        """
        self.data.errors = dict()
        self.data.paymentstepid = int(self.request.form.get('checkout.stepid', 0))

        props = getToolByName(self.context, 'portal_properties').pcommerce_properties
        min_charge = props.getProperty('parcel_mincharge', 0.0)
        max_charge = props.getProperty('parcel_maxcharge', 0.0)
        item_charge = props.getProperty('parcel_itemcharge', 0.0)

        posttaxcharge = 0.0

        for item in self.order.products:
            posttaxcharge += item_charge * float(item[3]) # Charge per item

        if posttaxcharge > max_charge:
            posttaxcharge = max_charge
        if posttaxcharge < min_charge:
            posttaxcharge = min_charge

        shipments = self.order.shipmentdata.data.values()
        for i in range(0, len(shipments)):
            if shipments[i].id == 'pcommerce.shipment.parcel':
                self.order.shipmentdata.data.values()[i].posttaxcharge = posttaxcharge
                break

        return self.data

    def renders(self):
        """
        Only render this page if a user is logged in.
        """
        portal_state = getMultiAdapter((self.context, self.request),
                        name="plone_portal_state")

        if portal_state.anonymous() or self.data.methods_count == 0:
            return False
        else:
            return True

    def get_methods(self):
        """
        Return retained cards from the database query in __init__
        """
        output = []
        set_default = False
        for method in self.methods:
            details = method.first_name+" "+method.last_name+", "+self.data.card_types[method.card_type]+", "+method.number+", Expires "+str(method.month)+"/"+str(method.year)
            output.append({'default':method.default, 'token': method.token, 'details':details})

        return output
