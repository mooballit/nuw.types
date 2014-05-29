# Copyright (c) 2012 Mooball IT
# See also LICENSE.txt
from AccessControl import ClassSecurityInfo
from AccessControl.class_init import InitializeClass
from Products.CMFCore.interfaces import ISiteRoot
from Products.CMFCore.permissions import ManagePortal
from Products.CMFCore.utils import getToolByName
from Products.CMFDefault.utils import checkEmailAddress
from Products.CMFDefault.exceptions import EmailAddressInvalid
from Products.statusmessages.interfaces import IStatusMessage
from five import grok
from nuw.types.api.change import Change
from nuw.types.api.settings import IAPISettings
from nuw.types.base import IMappedTable
from nuw.types.base import INUWItem
from nuw.types.base import MockTable
from nuw.types.member import change_person_email, email_exists
from plone.directives import form
from plone.memoize.ram import cache
from plone.registry.interfaces import IRegistry
from z3c.form import button
from sqlalchemy.sql.expression import not_
from z3c.saconfig import named_scoped_session
from zope.container.folder import Folder
from zope.lifecycleevent import ObjectAddedEvent
from zope.lifecycleevent import ObjectModifiedEvent
from zope.lifecycleevent import ObjectRemovedEvent
import OFS.SimpleItem
import Products.CMFCore.utils
import logging
import lxml.etree
import nuw.types.api.auth
import sqlalchemy.exc
import transaction
import uuid
import zope.component
import zope.interface
import zope.schema
import zope.schema.interfaces
from pprint import pprint


Session = named_scoped_session('nuw.types')
RETURNCODES = {
    0: u'Synced',
    1: u'Invalid credentials.',
    2: (u'The API is not configured. You have to set an api key in the'
        ' Plone Site Setup before you communicate to with the API.'),
    3: u'Invalid XML received.',
    4: u'Wrong or duplicate GUIDs received.',
    5: u'XML contains GUID to non-existings entities.',
}


class ISyncAPITool(zope.interface.Interface):
    """NUW API tool.

    It is used to syncronise data between the new NUW site and the NUW
    Information Hub. For most API calls, if anything goes wrong both
    ends need to do a rollback and another attempt should be made.
    """

    def api_push_changes(changes):
        """
        This is a POST call that allows the caller to push changes to
        the website database.
        """

    def api_clear_changes(change_ids):
        """
        Clear all change items given by change_ids.
        """

    def api_get_changes():
        """
        Return all IChange items found in the database.
        """


class IAPIResponse(zope.interface.Interface):
    """A response from the API.

    This should be a lxml.etree.ElementBase instance and can be
    unserialized to XML.

    All non-zero error codes lead to a **failure** status. A u'0' error
    code is **success**.
    """


class result(lxml.etree.ElementBase):
    zope.interface.implements(IAPIResponse)


class error(lxml.etree.ElementBase):
    zope.interface.implements(IAPIResponse)


def result_factory( errors ):
    ret = result( '' )

    for err in errors:
        msg = "%s: %s" % ( RETURNCODES[ err['code'] ], err.get( 'msg', '' ) )
        errel = error( msg, code = unicode( err['code'] ) )
        if 'type' in err:
            errel.set( 'type', err['type'] )
        if 'line' in err:
            errel.set( 'line', unicode( err['line'] ) )
        if 'changeid' in err:
            errel.set( 'changeid', unicode( err['changeid'] ) )

        ret.append( errel )

    return ret


class SchemaXSD(grok.View):
    grok.context(zope.interface.Interface)
    grok.name('schema.xsd')
    grok.require('zope2.View')

    def get_info(self):
        info = dict()
        for utid, klass in zope.component.getUtilitiesFor(IMappedTable):
            # hm... if the klass implements more than one we're screwed
            # :(
            info[utid] = list(zope.interface.implementedBy(klass))[0]
        return info

    def get_fields_for(self, iface):
        return zope.schema.getFields(iface)


def dummy_cache_key(fun, context, request):
    """
    Dummy caching method which will cache the return values indefinitely.
    """
    return 'cache_key'


@cache(dummy_cache_key)
def get_xml_schema(context, request):
    """Returns XMLSchema instance for validation."""
    rendered = zope.component.getMultiAdapter(
        (context, request), name='schema.xsd')()
    doc = lxml.etree.XML(rendered.encode('utf-8'))
    xmlschema = lxml.etree.XMLSchema(doc)
    return xmlschema


def validate_xml(func):
    def decorated(*args, **kwargs):
        tool, changes = args
        message = None
        try:
            message = lxml.etree.XML(changes)
        except lxml.etree.XMLSyntaxError, e:
            return [ { 'code': 3, 'msg': e.msg } ]

        insert_mode = message.xpath('contains(@action, "insert")')
        if insert_mode:
            xmlschema = get_xml_schema(tool, tool.REQUEST)
            is_valid = xmlschema.validate(message)
            if not is_valid:
                return [ { 'code': 3, 'msg': xmlschema.error_log.last_error } ]
        return func(*args, **kwargs)
    return decorated


class SyncAPITool(Products.CMFCore.utils.UniqueObject,
                  OFS.SimpleItem.SimpleItem,
                  Folder):

    zope.interface.implements(ISyncAPITool)

    id = 'portal_syncapi'
    meta_type = 'NUW Sync API Tool'
    plone_tool = 1

    manage_options = OFS.SimpleItem.SimpleItem.manage_options
    manage_options = [opt for opt in manage_options if opt['label'] not in
                      ['View']]

    security = ClassSecurityInfo()

    security.declareProtected(ManagePortal, 'api_get_changes')
    def api_get_changes(self):
        session = Session()
        return session.query(Change).filter(
            not_(Change.principal ==
                 nuw.types.api.auth.USERNAME)).limit(10000).all()

    security.declareProtected(ManagePortal, 'api_push_changes')
    @validate_xml
    def api_push_changes(self, changes):
        message = lxml.etree.XML(changes)
        action = message.get('action')
        errors = []
        entities = message.xpath('//data/*')
        if action == 'insert':
            errors = self.create_items_from(entities)
        elif action == 'delete':
            errors = self.delete_items_from(entities)
        elif action == 'update':
            errors = self.update_items_from(entities)
        return errors

    security.declareProtected(ManagePortal, 'api_clear_changes')
    def api_clear_changes(self, change_ids):
        """ A list of change item ids.

        The ids can be integers (preferrable) or strings representations
        of the integers.
        """
        errors = []
        session = Session()
        for id in change_ids:
            obj = None
            try:
                obj = session.query(Change).filter_by(id=id).first()
            except sqlalchemy.exc.DataError, err:
                self.log(err)
                errors.append( { 'changeid': id, 'code': 4, 'msg': str( err ) } )

            if obj is None:
                errors.append( { 'changeid': id, 'code': 4 } )
                continue

            try:
                session.delete(obj)
                session.flush()
            except sqlalchemy.exc.IntegrityError, err:
                self.log(err)
                errors.append({'changeid': id, 'code': 4})
            transaction.savepoint()

        return errors

    def update_items_from(self, iterable):
        """
        Update items given by XML data.

        Issues an IObjectModifiedEvent per updated instance.
        """
        session = Session()
        errors = []

        for item in iterable:
            hubid = INUWItem(item).hubid
            table = zope.component.getUtility(IMappedTable, name=item.tag)
            try:
                obj = session.query(table).filter_by(hubid=hubid).one()
            except sqlalchemy.orm.exc.NoResultFound:
                errors.append(dict(code=4,
                                   type=item.tag,
                                   line=item.sourceline)
                             )
                continue

            if item.tag == 'person' and obj.email != item.get( 'email', obj.email ) and obj.user_id:
                # Email is going to be changed, need to update any subscriptions

                try:
                    checkEmailAddress(item.get('email'))
                except EmailAddressInvalid:
                    errors.append( { 'code': 3, 'type': item.tag, 'line': item.sourceline, 'msg': 'Activated members need a valid email address' } )

                    continue

                if email_exists( item.get( 'email' ) ):
                    errors.append( { 'code': 3, 'type': item.tag, 'line': item.sourceline, 'msg': 'New Email address already in use' } )

                    continue

                change_person_email( self, obj, item.get( 'email' ) )

            try:
                table.apply_mapped_data(obj, item)
            except zope.schema.interfaces.ConstraintNotSatisfied:
                continue

            session.flush()
            zope.event.notify(ObjectModifiedEvent(obj))

        return errors

    def delete_items_from(self, iterable):
        """
        Deletes items given by XML data.

        Issues an IObjectRemovedEvent per deleted instance.
        """
        errors = []
        session = Session()
        for item in iterable:
            hubid = INUWItem(item).hubid
            table = zope.component.getUtility(IMappedTable, name=item.tag)
            obj = session.query(table).filter_by(hubid=hubid).first()
            if obj is not None:
                try:
                    session.delete(obj)
                    session.flush()
                    zope.event.notify(
                        ObjectRemovedEvent(obj, self, obj.id))
                except sqlalchemy.exc.IntegrityError, err:
                    self.log(err)
                    errors.append({'code': 3, 'type': item.tag, 'line': item.sourceline})
        return errors

    def create_items_from(self, iterable):
        """
        Create new items from the given XML data. Issues an
        IObjectAddedEvent per added instance.
        """
        instance = None
        errors = []
        session = Session()
        duplicates = []
        transaction_size = 256
        counter = 1
        for item in iterable:
            factory = zope.component.queryUtility(
                zope.component.interfaces.IFactory,
                name=item.tag)
            if factory is None:
                continue

            sp = transaction.savepoint(True)
            try:
                instance = factory(**dict(item.items()))
                session.add(instance)
                session.flush()

                zope.event.notify(
                    ObjectAddedEvent(instance, self, instance.id))
                counter += 1
            except zope.schema.interfaces.ConstraintNotSatisfied, err:
                errormsg = ('{doc}: {message} for type: {type}'
                            ' at L:{line}'.format(
                                doc=err.doc(), message=str(err),
                                type=item.tag, line=item.sourceline)
                           )
                self.log(errormsg)
                errors.append( { 'code': 3, 'msg': str( err ), 'type': item.tag, 'line': item.sourceline } )
            except sqlalchemy.exc.IntegrityError, err:
                sp.rollback()
                self.log(err)
                errors.append( { 'code': 4, 'type': item.tag, 'line': item.sourceline } )
                duplicates.append(item)
            except sqlalchemy.exc.NoReferenceError, err:
                sp.rollback()
                self.log(err)
                errors.append( { 'code': 5, 'msg': str(err), 'type': item.tag, 'line': item.sourceline } )

            if transaction_size % counter == 0:
                transaction.commit()
        self.update_items_from(duplicates)
        return errors

    def log(self, msg, type=logging.ERROR):
        logger = logging.getLogger(self.id)
        logger.log(type, msg)


InitializeClass(SyncAPITool)


class XMLElementNUWItem(grok.Adapter):
    grok.provides(INUWItem)
    grok.context(lxml.etree._Element)

    format = '%Y-%m-%dT%H:%M:%S'

    @property
    def hubid(self):
        name = '{entityname}id'.format(entityname=self.context.tag)
        return self.context.get(name)

    @property
    def nuwdbid(self):
        return self.context.get('nuwdbid')

    @property
    def nuwassistid(self):
        return self.context.get('nuwassistid')

    @property
    def metatype(self):
        return self.context.tag


def check_apikey(func):
    """View Decorator which enforces constraints on the APITool.

    The decorator only executes the decorated method if the APITool is
    configured and the provided apikey matches.

        * The API key is not configured -> status: failure
        * The API key is configured, but invalid -> status: failure

    In case of a failure a serialized `IAPIResponse` as XML is returned.
    """

    def replacement(*args, **kwargs):
        request = args[0].request
        apikey = request.form.get('api_key', None)
        registry = zope.component.getUtility(
            IRegistry).forInterface(IAPISettings)

        type = 'text/xml; charset={}'.format(registry.output_encoding)
        request.response.setHeader('Content-Type', type)

        if not registry.api_key:
            return lxml.etree.tostring( result_factory( [ { 'code': 2 } ] ) )
        elif registry.api_key != apikey:
            return lxml.etree.tostring( result_factory( [ { 'code': 1 } ] ) )
        if registry.api_key == apikey:
            return func(*args, **kwargs)
    return replacement


class PushChanges(grok.View):
    grok.name('push_changes')
    grok.context(ISyncAPITool)
    grok.require('zope2.Public')

    @check_apikey
    def render(self):
        tool = getToolByName(self.context, 'portal_syncapi')
        if 'changes' not in self.request.form:
            errors = [ { 'code': 3, 'msg': 'changes POST variable is missing!' } ]
        elif self.request.form['changes'] == '':
            errors = [ { 'code': 3, 'msg': 'changes POST variable is empty!' } ]
        else:
            errors = tool.api_push_changes(
                self.request.form.get('changes', ''))
        return lxml.etree.tostring( result_factory( errors ) )


class GetChanges(grok.View):
    """Returns all relevant data modifications from the website.

    This is a GET call that fetches a maxiumum of 10000 change records
    that have happened since the last :ref:`clear_changes`. To ensure
    the same records do not get returned twise the caller needs to call
    :ref:`clear_changes` once the changes have been applied.

    Example call:

        http://api.nuw.info/get_changes?api_key=asdf

    .. highlight:: xml

    Will return the following XML::

        <?xml version="1.0" encoding="iso-8859-1" ?>
        <changes>
          <change action="add" otype="person" changed="2012-10-30T16:49:26.823837" oid="0c3f2320-ace8-e011-90f7-005056a20027" id="1" principal="admin">
            <person fax="" personid="0c3f2320-ace8-e011-90f7-005056a20027" lastname="dbo" work="" postrts="False" mobile="" home=""/>
          </change>
        </changes>

    :param api_key: Configured API key for authentication
    :type api_key: str
    """

    grok.name('get_changes')
    grok.context(ISyncAPITool)
    grok.require('zope2.Public')

    @check_apikey
    def __call__(self):
        return super(GetChanges, self).__call__()

    def get_changeitems(self):
        tool = getToolByName(self.context, 'portal_syncapi')
        # render takes care of the transformation into XML
        return tool.api_get_changes()


class ClearChanges(grok.View):
    """ This is a POST call that removes all change items matching the
        given ids from the changes table.

    This call should only be called after a get_changes call to let the
    system know that the change items returned from that call have been
    applied.

    .. note::
        If one provided GUID is wrong, the API call will result in a
        failure. This is to make sure, that no random change items are
        cleared by accident.

    The caller has to specify the datatype of the ids:

        * as a list by postfixing ``:list``
        * as an integer by postfixing ``:int``

    .. note:: Postfixing order is important.

    Example:

        http://api.domain.com/clear_changes?api_key=asdfasdf&ids:list:int=1&ids:list:int=2'

    :param id: A list of change ids (plain integers, not GUIDs)
    :param api_key: Configured API key for authentication
    :type api_key: str
    """
    grok.name('clear_changes')
    grok.require('zope2.View')
    grok.context(ISyncAPITool)

    @check_apikey
    def render(self):
        change_ids = self.request.form.get('ids', [])
        if not change_ids:
            errors = dict(code=3,
                          msg=u'ids POST variable is empty or missing!')
        else:
            tool = getToolByName(self.context, 'portal_syncapi')
            errors = tool.api_clear_changes(change_ids)
        return lxml.etree.tostring(result_factory(errors))


class IXMLImport(form.Schema):

    xml = zope.schema.Bytes(
        title=u'XML Data'
    )


class IAPIXMLImport(form.SchemaForm):
    grok.name('apixmlimport.html')
    grok.require('zope2.View')
    grok.context(ISiteRoot)
    schema = IXMLImport
    ignoreContext = True

    label = u'XML Import'

    def update(self):
        self.request.set('disable_border', True)
        super(IAPIXMLImport, self).update()

    @button.buttonAndHandler(u'Import')
    def handleImport(self, action):
        data, errors = self.extractData()
        if errors:
            self.status = self.formErrorMessage
            return
        tool = getToolByName(self.context, 'portal_syncapi')

        errors = tool.api_push_changes(data['xml'])
        if errors:
            self.status = "Errors occurred:"

            for error in errors:
                self.status += ' \n'

                if "line" in error:
                    self.status += 'Line %s: ' % error['line']

                self.status += RETURNCODES[ error['code'] ]

                if 'msg' in error:
                    self.status += ': %s' % error['msg']

            return
        else:
            IStatusMessage(self.request).addStatusMessage(
                u'XML successfully imported.', 'info')
            self.request.response.redirect(self.context.absolute_url() +
                                           '/@@overview-controlpanel')


class GetData(grok.View):
    """get_data api call which returns all data of a given type.

    This view returns all data of a given type. The type can be given as
    a segment in the URL, e.g.:

        http://api.nuw.info/person/get_data?api_key=asdf

    This will retrieve up to 10000 rows if no other size and limit is
    given.

    ..  rubric::Changing the Batch Size

    The batches can be customized by two parameters:

        * b_size:int (10000)
        * b_start:int (0)

    Keep in mind that you keep the value identifier (int) for each
    parameter, e.g.:

        http://api.nuw.info/person/get_data?api_key=asdf&b_size:int=20&b_start:int=10

    Will retrieve 20 items and starts after the first 10 rows.

    ..  rubric::Filtering

    The data can be filtered by a ``guid`` key, e.g.:

        http://api.nuw.info/person/get_data?guid:string=40942A20-ACE8-E011-90F7-005056A20027

    which will result in one result, if any matches the given UUID.

    :param api_key: Configured API key for authentication
    :type api_key: str
    """
    grok.context(MockTable)
    grok.require('zope2.View')
    grok.name('get_data')

    @check_apikey
    def __call__(self):
        return super(GetData, self).__call__()

    def update(self):
        self.request.response.setHeader(
            'Content-Type', 'application/xml;; encoding=utf-8')

    @property
    def entity(self):
        return self.context.getId()

    def get_data_iterator(self):
        guid = self._get_guid_filter()
        b_size = self.request.form.get('b_size', 10000)
        b_start = self.request.form.get('b_start', 0)
        b_size = b_size if not isinstance(b_size, str) else 10000
        b_start = b_start if not isinstance(b_start, str) else 0
        session = Session()

        query = session.query(self.context.table)
        query = query.order_by(self.context.table.__mapper__.primary_key[0].name)
        query = query.slice(b_start, b_start + b_size)
        pprint([x.__str__() for x in self.context.table.__table__.columns])

        if guid:
            query = query.from_self().filter_by(hubid=guid)
        return query

    def _get_guid_filter(self):
        """Returns a valid hubid to filter the dataset on if set in the
           request.

           :rtype: valid UUID or None
        """
        guid = self.request.form.get('guid')
        try:
            uuid.UUID('urn:uuid:{}'.format(guid))
        except ValueError:
            guid = None
        return guid


class MapperTraverser(object):

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def publishTraverse(self, request, name):
        view = zope.component.queryMultiAdapter(
            (self.context, self.request), name=name)
        if view is not None:
            return view
        elif hasattr(self.context, name):
            return getattr(self.context, name)
        else:
            table = zope.component.queryUtility(
                IMappedTable, name=name)
            if table is None:
                raise zope.publisher.interfaces.NotFound(
                    self.context, name, self.request)
            return MockTable(table).__of__(self.context)
