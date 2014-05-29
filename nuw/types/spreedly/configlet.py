from Products.statusmessages.interfaces import IStatusMessage
from Products.Five.browser import BrowserView
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from Products.CMFCore.utils import getToolByName
from Products.CMFPlone import PloneMessageFactory as _p

from pcommerce.core import PCommerceMessageFactory as _

class ShippingConfiglet(BrowserView):
    """Shipping configlet
    """

    template = ViewPageTemplateFile('configlet.pt')
    properties = ('parcel_itemcharge','parcel_mincharge','parcel_maxcharge',)
    values = {}

    def __call__(self):
        self.request.set('disable_border', True)
        self.errors = {}
        
        props = getToolByName(self.context, 'portal_properties').pcommerce_properties
        if self.request.form.has_key('pcommerce_save'):
            for prop in self.properties:
                try:
                    new_prop = self.request.form.get(prop, '')
                    if new_prop == '' or new_prop is None:
                        self.errors[prop] = _(u'Please fill out this field.')
                    else:
                        self.values[prop] = float(new_prop)
                except:
                    self.errors[prop] = _(u'Please enter a floating point number (e.g. 7.6)')
            
            if not self.errors:
                IStatusMessage(self.request).addStatusMessage(_p('Shipping charges saved.'), 'info')
                for prop in self.properties:
                    props._setPropValue(prop, self.values[prop])
            else:
                IStatusMessage(self.request).addStatusMessage(_p(u'Please correct the indicated errors!'), 'error')

        for prop in self.properties:
            self.values[prop] = props.getProperty(prop, '')
        
        return self.template()
