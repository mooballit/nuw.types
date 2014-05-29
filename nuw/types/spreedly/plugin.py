import urllib, math

from zope.interface import implements, Interface
from zope.component import adapts, getMultiAdapter

from Products.CMFCore.utils import getToolByName

from pcommerce.core.interfaces import IPaymentMethod, IOrder
from pcommerce.core.currency import CurrencyAware
from pcommerce.core import PCommerceMessageFactory as _

from nuw.types.spreedly.interfaces import ISpreedlyPayment
from nuw.types.spreedly.data import SpreedlyPaymentData

class SpreedlyPayment(object):
    implements(IPaymentMethod, ISpreedlyPayment)
    adapts(Interface)
    
    title = _(u'Credit Card')
    description = _('Payment using Credit Card')
    icon = u'++resource++pcommerce_payment_spreedly_icon.gif'
    logo = u'++resource++pcommerce_payment_spreedly_logo.gif'
    
    def __init__(self, context):
        self.context = context
    
    def mailInfo(self, order, lang=None, customer=False):
        card_types = {'visa':'Visa', 'master':'MasterCard', 'american_express':'American Express', 'discover':'Discover', 'dankort':'Dankort'}
        
        data = IOrder(self.context).paymentdata or SpreedlyPaymentData()
        card_name = unicode("%s %s" % (data.method.first_name, data.method.last_name))
        card_number = unicode(data.method.number)
        card_type = unicode(card_types[data.method.card_type])
        card_cvn = u'XXX'
        card_expiry = unicode("%s/%s" % (data.method.month, data.method.year))
        
        payment = unicode("Payment processed over Credit Card\nName: " + card_name + "\nNumber: " + card_number + "\nType: " + card_type + "\nExpiry: " + card_expiry + "\nCVN: " + card_cvn)
        return _('spreedly_mailinfo', default=payment)
