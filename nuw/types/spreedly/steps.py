from zope.interface import implementer
from zope.component import adapter
from Products.CMFPlone.interfaces.siteroot import IPloneSiteRoot

from pcommerce.core.interfaces import ISteps
from pcommerce.core import PCommerceMessageFactory as _

@adapter(IPloneSiteRoot)
@implementer(ISteps)
def steps(context):
    return ({'name':_('Address'), 'components':('address',)},
            {'name':_('Shipment'), 'components':('shipments',)},
            {'name':_('Shipment'), 'components':('shipment',)},
            {'name':_('Payment Method'), 'components':('payments',)},
            {'name':_('Payment Method'), 'components':('payment',)},
            {'name':_('Overview'), 'components':('overview', 'gtc',)},
            {'name':_('Process'), 'components':('process',)},
            {'name':_('Confirmation'), 'components':('confirmation',)})
