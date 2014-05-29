# Copyright (c) 2012 Mooball IT
# See also LICENSE.txt
from AccessControl.SecurityInfo import ClassSecurityInfo
from AccessControl.class_init import InitializeClass
from Products.PluggableAuthService.interfaces.plugins import \
        IExtractionPlugin, IAuthenticationPlugin
from Products.PluggableAuthService.plugins.BasePlugin import BasePlugin
from Products.PluggableAuthService.utils import classImplements
from nuw.types.api.settings import IAPISettings
from plone.registry.interfaces import IRegistry
from zope.interface import Interface
import zope.component


PLUGIN_NAME = 'portal_syncapi_authentication'
USERNAME = '__API_USER__'


class IAPIAuthHelper(Interface):
    """ Authentication plugin to authenticate API calls
    """


class APIAuthHelper(BasePlugin):
    meta_type = 'SyncAPI Auth Helper'
    security = ClassSecurityInfo()

    def __init__(self, id, title=None):
        self.id = id
        self.title = title

    security.declarePrivate('extractCredentials')
    def extractCredentials(self, request):
        """ Extract credentials from 'request'. """
        creds = {}
        creds['login'] = USERNAME
        creds['password'] = request.form.get('api_key', '')
        return creds

    security.declarePrivate('authenticateCredentials')
    def authenticateCredentials(self, credentials):
        login = credentials.get('login', '')
        password = credentials.get('password', '')
        registry = zope.component.getUtility(
            IRegistry).forInterface(IAPISettings)
        if registry.api_key == password and USERNAME == login:
            return (login, login)
        return (None, None)


classImplements(APIAuthHelper,
                IAPIAuthHelper,
                IExtractionPlugin,
                IAuthenticationPlugin,
               )

InitializeClass(APIAuthHelper)
