from pcommerce.core import PCommerceMessageFactory as _

def order_management_columns(self):
    """Fields for order management table. """
    field_ids = [
        'orderid',
        'userid',
        'date',
        'currency',
        'totalincl',
        'state',
        ]
    columns = [ column for column in self.order_fields() if \
        column['field_id'] in field_ids]
    return columns

def _address_converter(self, value, order):
    from persistent.mapping import PersistentMapping
    if type(value) is PersistentMapping:
        addresses = ''
        for key in value.keys():
            address = value[key].address
            if address is None:
                addresses += '<li>%s</li><pre>Same as Invoice</pre>' % key
            else:
                addresses += '<li>%s</li><pre>%s</pre>' % (key, address.mailInfo(self.request))

        return addresses

    return '<pre>%s</pre>' % value.mailInfo(self.request)

def order_fields(self):
    """Fields and fieldnames to show in tables (order overviews / details).

        {   'field_id': '',
            'field_name': _("label_", default=""),
            'sortable': True
            },
    """
    fields = [
        {   'field_id': 'orderid',
            'field_name': _("label_order_id", default="Order id"),
            'sortable': True
            },
        {   'field_id': 'userid',
            'field_name': _("label_user_id", default="User id"),
            'sortable': True
            },
        {   'field_id': 'date',
            'field_name': _("label_date", default="Date"),
            'sortable': True
            },
        {   'field_id': 'currency',
            'field_name': _("label_currency", default="Currency"),
            'sortable': True
            },
        {   'field_id': 'totalincl',
            'field_name': _("label_price_total", default="Price total"),
            'field_converter': self._totalincl_converter,
            'sortable': True
            },
        {   'field_id': 'state',
            'field_name': _("label_order_state", default="Order status"),
            'sortable': True
            },
        {   'field_id': 'zone',
            'field_name': _("label_zone", default="Zone"),
            'field_converter': self._zone_converter,
            'sortable': True
            },
        {   'field_id': 'address',
            'field_name': _("label_address", default="Invoice Address"),
            'field_converter': self._address_converter,
            'sortable': True
            },
        {   'field_id': 'shipmentdata',
            'field_name': _("label_shipping_address", default="Shipping Address"),
            'field_converter': self._address_converter,
            'sortable': True
            },
        {   'field_id': 'products',
            'field_name': _("label_products", default="Products"),
            'field_converter': self._products_converter,
            'sortable': False
            },
        ]
    return fields
