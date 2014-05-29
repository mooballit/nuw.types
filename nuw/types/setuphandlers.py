from Products.CMFCore.utils import getToolByName
from Products.PluggableAuthService.interfaces.plugins import IPropertiesPlugin
from Products.TinyMCE.interfaces.utility import ITinyMCE
from nuw.types import Base
from nuw.types import authentication
from z3c.saconfig import named_scoped_session
from zope.component import getUtility

import nuw.types.api.auth
import transaction
import zope.component.interfaces


Session = named_scoped_session("nuw.types")


def bootstrap_data():
    session = Session()
    data = {
        'person.type': [
            (u'Potential Member',),
            (u'Member',),
            (u'Ex-Member',),
            (u'Contact',),
            (u'Supporter',),
            (u'Non-Union Worker',),
        ],
        'group.type': [
            (u'Union Site',),
            (u'Closed Site',),
            (u'Employment Agency',),
            (u'Closed Agency',),
            (u'Subscription',),
            (u'Campaign',),
        ],
        'supergroup.type': [
            (u'Ownership Group',),
            (u'Union Branch',),
            (u'Organiser Area',),
            (u'Industry Group',),
        ],
        'record.type': [
            (u'SMS',),
            (u'Email',),
            (u'Agreement',),
        ],
        'superrole.superrole': [
            (u'Organiser',),
            (u'Area Admin',),
            (u'Industrial Officer',),
            (u'Industry MSO',),
            (u'Lead Organiser',),
        ],
    }
    for factory_name in data:
        factory = zope.component.queryUtility(
            zope.component.interfaces.IFactory,
            name=factory_name)
        for values in data[factory_name]:
            session.add(factory(*values))
    transaction.commit()


def install_pas_plugin(self, plugin_name, providedIfaces, factory, *args):
    """ Install and activate a PAS plugin given by it's factory.

    :param plugin_name: The plugin id the plugin is set in the PAS
                        folder.
    :param providedIfaces: The interfaces this plugin provides, as a
                           list of strings.
    :param factory: The factory to instantiate the plugin.
    :param *args: Arguments which are passed on to the plugin factory.
    """

    pas = self.acl_users

    if not plugin_name in pas.objectIds():
        manager = factory(plugin_name, *args)
        pas._setObject(plugin_name, manager)
        provider = pas[plugin_name]
        provider.manage_activateInterfaces(providedIfaces)
        # Make it the top plugin for member properties (otherwise the
        # other ones will overwrite props)
        if authentication.INUWAuthPlugin.providedBy(provider):
            _move_pas_plugin_to_top(pas, provider, plugin_name)

            # Add property to enable limiting access to site based on what
            # group(s) a user has.
            provider.manage_addProperty('limit_to_groups', [], 'lines')
            provider.manage_addProperty('webstatus', [], 'lines')


def _move_pas_plugin_to_top(pas, provider, plugin_name):
    plugin_pos = 0
    for plugin in pas.plugins.listPlugins( IPropertiesPlugin ):
        if plugin[0] == plugin_name:
            break
        
        plugin_pos += 1
    
    # There is no way to tell it to just move the plugin to the top so
    # just do enough move ups to get it there
    while plugin_pos > 0:
        pas.plugins.movePluginsUp( IPropertiesPlugin, [ plugin_name ] )
        plugin_pos -= 1


def install( context ):
    if context.readDataFile('marker.txt') is None:
        return

    session = Session()
    Base.metadata.create_all( session.bind )

    portal = context.getSite()
    install_pas_plugin(
        portal,
        nuw.types.api.auth.PLUGIN_NAME,
        ['IAuthenticationPlugin',
         'IExtractionPlugin',
        ],
        nuw.types.api.auth.APIAuthHelper,
        'NUW SyncAPI Authentication')
    install_pas_plugin(
        portal,
        authentication.PLUGIN_NAME,
        ['IAuthenticationPlugin',
         'IUserEnumerationPlugin',
         'IGroupsPlugin',
         'IPropertiesPlugin',
         'IUserManagement'
        ],
        authentication.NUWAuthPlugin,
        'NUW Member Store')
    bootstrap_data()
    
    # Make sure all custom content types are able to be linked to via TinyMCE
    cts = [ 'nuw.types.industry', 'nuw.types.campaign', 'nuw.types.campaignevent', 'nuw.types.wall', 'nuw.types.petition' ]
    tinymce = getUtility( ITinyMCE )
    
    linkable = tinymce.linkable.split( '\n' )
    
    linkable += [ ct for ct in cts if ct not in linkable ]
    tinymce.linkable = '\n'.join( linkable )
    
    # Setup catalog indexes if not present
    catalog = getToolByName( portal, 'portal_catalog' )

    needed_indexes = [ ( 'campaign_type', 'FieldIndex' ), ( 'parent_industry', 'FieldIndex' ), ( 'parent_campaign', 'FieldIndex' ) ]
    current_indexes = catalog.indexes()
    new_indexes = []
    
    for name, idxtype in needed_indexes:
        if name not in current_indexes:
            catalog.addIndex( name, idxtype )
            new_indexes.append( name )
            
    if len( new_indexes ):
        catalog.manage_reindexIndex( ids = new_indexes )
    
    
