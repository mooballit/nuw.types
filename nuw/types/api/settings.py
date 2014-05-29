# Copyright (c) 2012 Mooball IT
# See also LICENSE.txt
from plone.app.registry.browser.controlpanel import ControlPanelFormWrapper
from plone.app.registry.browser.controlpanel import RegistryEditForm
from plone.z3cform import layout
import zope.interface
import zope.schema


class IAPISettings(zope.interface.Interface):
    """Control panel settings for the ISyncAPITool."""

    api_key = zope.schema.TextLine(
        title=u'API Key',
        description=(u'Set a secret api key the Information Hub uses to'
                     ' communicate with this site.'),
    )

    output_encoding = zope.schema.TextLine(
        title=u'XML Output Encoding',
        description=u'The output encoding of the XML.',
        default=u'iso-8859-1',
        )

    # Twitter fields
    consumer_key = zope.schema.TextLine(
            title=u'Twitter Consumer Key',
            description=(u'Consumer key in OAuth settings'),
        )

    consumer_secret = zope.schema.TextLine(
            title=u'Twitter Consumer Secret',
            description=u'Consumer secret in OAuth settings',
        )

    token_key = zope.schema.TextLine(
            title=u'Twitter Access Token',
            description=(u'Access token in Your access token'),
        )

    token_secret = zope.schema.TextLine(
            title=u'Twitter Access Token Secret',
            description=u'Access token secret in Your access token',
        )

class APIToolControlPanelForm(RegistryEditForm):
    schema = IAPISettings

    label = u'APITool Settings'
    description = u'APITool related settings.'

APIToolControlView = layout.wrap_form(APIToolControlPanelForm,
                                      ControlPanelFormWrapper)
