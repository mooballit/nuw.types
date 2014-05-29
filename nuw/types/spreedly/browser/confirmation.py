from zope.interface import implements
from zope.i18n import translate
from zope.component import getMultiAdapter

from Products.Five.browser import BrowserView
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile

from pcommerce.core.interfaces import IPaymentView, IOrder
from pcommerce.core import PCommerceMessageFactory as _

from nuw.types.spreedly.data import SpreedlyPaymentData

class SpreedlyConfirmation(BrowserView):
    template = ViewPageTemplateFile('confirmation.pt')
    implements(IPaymentView)
    
    def __init__(self, payment, request):
        self.payment = payment
        self.context = payment.context
        self.request = request

        self.order = IOrder(self.context)
        self.data = self.order.paymentdata or SpreedlyPaymentData()
        
    def __call__(self):
        return self.template()

    def card_type(self):
        return self.data.card_types[self.data.method.card_type]
