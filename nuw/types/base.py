# Copyright (c) 2012 Mooball IT
# See also LICENSE.txt
from Products.CMFCore.utils import getToolByName
from five import grok
from nuw.types.api.settings import IAPISettings
from plone.directives import form
from plone.registry.interfaces import IRegistry
from Products.CMFCore.interfaces import ISiteRoot
from sqlalchemy import Column, String, Integer, Boolean, Unicode, UnicodeText
from sqlalchemy.ext.hybrid import hybrid_property
from z3c.saconfig import named_scoped_session
from zope.schema.interfaces import IDatetime
from zope.schema.interfaces import IFromUnicode
from zope.schema.vocabulary import SimpleVocabulary
import email
import logging
import lxml.builder
import lxml.etree
import sqlalchemy.exc
import sqlalchemy.orm.exc
import uuid
import zope.component


Session = named_scoped_session('nuw.types')


class IMappedTable(zope.interface.Interface):
    """Marker interface to lookup declared tables."""


class IVocabularyTable(zope.interface.Interface):
    """Table which provides a vocabulary like schema."""


class INUWItem(zope.interface.Interface):
    """A persistent item stored in a database."""

    hubid = zope.schema.TextLine(
        title=u'GUID',
        required=False,
    )

    webadaptorid = zope.schema.TextLine(
        title=u'GUID',
        required=False,
    )

    nuwdbid = zope.schema.TextLine(
        title=u'Member ID',
        required=False,
    )

    nuwassistid = zope.schema.Int(
        title=u'NUW Assist ID',
        required=False,
    )

    metatype = zope.schema.TextLine(
        title=u'Meta Type',
        readonly=True,
    )

    def apply_mapped_data(obj, data):
        """ Classmethod: Helper method to apply given data to the given
            object. The data is first mapped to the interface schema the
            context implements, before it is applied.
        """


class NUWItem(object):
    """Base object to provie INUWItem."""

    nuwdbid = Column(String)
    nuwassistid = Column(Integer)

    @property
    def metatype(self):
        return self.__tablename__

    @hybrid_property
    def hubid(self):
        return getattr(self, '{name}id'.format(name=self.__tablename__))

    @property
    def __name__(self):
        return self.hubid

    @classmethod
    def apply_mapped_data(klass, obj, data):
        interface = list(zope.interface.implementedBy(klass))[0]
        return apply_data(obj, interface, data)


# TODO: Good candidate for Memoize
def get_parent_content_type(context, interface):
    '''
        Traverses up the context's aq-chain until either an industry object is
        encountered (returning the industry object) or the site root is
        reached (returning None).
    '''
    cur_item = context.aq_inner

    while cur_item is not None:
        if ISiteRoot.providedBy(cur_item):
            # Site Root has been reached = Context not under Industry Content Type
            return None
        elif interface.providedBy(cur_item):
            return cur_item
        if not hasattr(cur_item, "aq_parent"):
            raise RuntimeError(
                    "Parent traversing interrupted by object: " + str(cur_item))

        cur_item = cur_item.aq_parent


def apply_data(context, interface, data):
    """ Helper method to apply given data to the context, by using the
        schema information given by the interface.
    """
    registry = zope.component.getUtility(
        IRegistry).forInterface(IAPISettings)
    encoding = registry.output_encoding
    for fid, field in zope.schema.getFieldsInOrder(interface):
        field = field.bind(context)
        converter = IFromUnicode(field)
        value = data.get(fid)
        if value is not None:
            factory = zope.component.queryUtility(
                zope.component.interfaces.IFactory,
                name='{0}.{1}'.format(context.__tablename__, field.__name__))
            # XXX the encoding should be declared somewhere not
            # hard-coded. I derived the encoding from speaking to
            # Lucas.
            if isinstance(value, str) or isinstance(value, unicode):
                decoded = value if (
                    isinstance(value, unicode)) else value.decode(encoding)
                value = converter.fromUnicode(decoded)
            if factory is not None:
                value = factory(value)
            field.set(context, value)


class IContactDetails(form.Schema):

    postaddress1 = zope.schema.Text(
        title=u'Post Address Line 1',
        required=False,
    )

    postaddress2 = zope.schema.Text(
        title=u'Post Address Line 2',
        required=False,
    )

    postsuburb = zope.schema.TextLine(
        title=u'Post Suburb',
        required=False,
    )

    poststate = zope.schema.TextLine(
        title=u'Post State',
        required=False,
    )

    postpcode = zope.schema.TextLine(
        title=u'Postcode',
        required=False,
    )

    postrts = zope.schema.Bool(
        title=u'Return to Sender',
        required=False,
    )

    fax = zope.schema.TextLine(
        title=u'Fax',
        required=False,
    )


class ContactDetailsMixin(object):
    """
    SQLAlchemy mix-in class for storing contact details.
    """

    postaddress1 = Column(UnicodeText)
    postaddress2 = Column(UnicodeText)
    postsuburb = Column(Unicode)
    poststate = Column(Unicode)
    postpcode = Column(String)
    postrts = Column(Boolean)
    fax = Column(String)


class VocabMixin(object):
    """
    Mixin to provide vocabulary compatible items.
    """
    zope.interface.implements(IVocabularyTable)

    token = Column(String)
    name = Column(Unicode)


class IToUnicode(zope.interface.Interface):
    """Parse data to unicode value."""

    def toUnicode(self, field):
        """Return the formatted unicode value retrieved by given field
           from context.
        """


class BaseToUnicodeMultiAdapter(grok.MultiAdapter):
    grok.baseclass()

    def __init__(self, context, field):
        self.context = context
        self.field = field


class EverythingToUnicode(BaseToUnicodeMultiAdapter):
    grok.provides(IToUnicode)
    grok.adapts(INUWItem, zope.interface.Interface)

    def toUnicode(self):
        value = self.field.bind(self.context).query(self.context)
        if IVocabularyTable.providedBy(value):
            value = value.token
        if value is not None:
            return unicode(value)


class DateTimeToUnicode(BaseToUnicodeMultiAdapter):
    grok.provides(IToUnicode)
    grok.adapts(INUWItem, IDatetime)

    def toUnicode(self):
        value = self.field.bind(self.context).query(self.context)
        if value is not None:
            return value.isoformat()


def create_or_get_typehelper(token, tableclass, name):
    """
    Instead of creating a new row, return an existing type if it matches
    the given ``token``.
    """
    session = Session()
    type = session.query(tableclass).filter(
        tableclass.token == token).first()
    name = name if name is not None else token
    return type if type is not None else tableclass(token=token, name=name)


def vocabulary_factory(tableclass):
    session = Session()
    result = []
    for type in session.query(tableclass).all():
        term = SimpleVocabulary.createTerm(type.token, type.token, type.name)
        result.append(term)
    return SimpleVocabulary(result)


class XMLBase(grok.View):
    grok.baseclass()
    ignored_attributes = []

    def render(self):
        result = []
        fields = self.get_filtered_fields()
        for fid, field in fields:
            value = zope.component.getMultiAdapter(
                (self.context, field)).toUnicode()
            if value is None:
                continue
            result.append((fid, unicode(value)))

        factory = getattr(lxml.builder.E,
                          INUWItem(self.context).metatype)
        tag = factory(**dict(result))
        return lxml.etree.tostring(tag)

    def get_filtered_fields(self):
        """Filters the contexts interface fields by self.ignored_attributes.

        ..  note: Furthermore fields are filtered by INUWItem fields, as
            these are considered internal fields. Exception:
            nuwassistid, nuwdbid
        """
        ignored_attributes = INUWItem.names()
        ignored_attributes += self.ignored_attributes
        # exception - NUW needs nuwassistid and the nuwdbid - check
        # #40@NUW
        ignored_attributes.remove('nuwassistid')
        ignored_attributes.remove('nuwdbid')
        interface = getattr(self, 'grokcore.component.directive.context')
        fields = zope.schema.getFieldsInOrder(interface)
        fields = [(x, y) for x, y in fields
                  if x not in ignored_attributes]
        return fields


def check_references(table, references_tables):
    """Basic decorator function for factories.

    Use them to decorate the factory methods (e.g. __init__) in order to
    check first if the given referenced tables holds the data which is
    needed to construct the instance.

    You can declare a reference by decorating the factory method:

    >>> from nuw.types.base import check_references
    >>> class Foobar(object):
    ...     __tablename__ = 'mytable'
    ...
    ...     @check_references('mytable', ['othertable'])
    ...     def __init__(self, **kwargs):
    ...         pass

    This example says: Check if the given data can construct an instance
    of 'mytable' which references a row with an id of 'othertable'.

    :param table: table which holds references
    :type table: str
    :param references_tables: Iterable to referenced tables
    :type references_tables: list
    """

    def check_references_inner(func):
        def decorated(*args, **kwargs):
            session = Session()
            tableid = kwargs.get('{table}id'.format(table=table), '')

            if table in references_tables:
                raise AssertionError(
                    'Circular references declared for {table}'.format(
                        table=table))

            for ref_table in references_tables:
                refid = kwargs.get('{ref}id'.format(ref=ref_table), '')
                mapper = zope.component.getUtility(IMappedTable, ref_table)
                try:
                    session.query(mapper).filter_by(hubid=refid).one()
                except sqlalchemy.orm.exc.NoResultFound:
                    message = ('{table} {tableid} references invalid'
                               ' {ref_table}: {items}'.format(
                                   table=table, tableid=tableid,
                                   ref_table=ref_table, items=kwargs))
                    raise sqlalchemy.exc.NoReferenceError(message)

            return func(*args, **kwargs)
        return decorated
    return check_references_inner


class MockTable(grok.Model):
    """Tablewrapper for SQLAlchemy tables.

    Because we can only register adapters for objects, we need a small
    wrapper around an SQLAlchemy table for the export views.
    """

    def __init__(self, table):
        self.table = table

    @property
    def _id(self):
        return self.table.__tablename__
    __name__ = _id


class PersonUUIDTraverser(object):
    """ Simple traverser which returns wrapped person instances in case
        it can be found by the given UUID.

    If the name is not a uuid, the default traversal is used:

    >>> from nuw.types.base import PersonUUIDTraverser
    >>> traverser = PersonUUIDTraverser(object, object)
    >>> traverser.publishTraverse(object, 'hurz')
    Traceback (most recent call last):
    NotFound: Object: <type 'object'>, name: 'hurz'

    A UUID is passed in and the DB is queried for a person with this UUID
    (personid).

    ..  note:: This throws a ComponentLookupError which means the code
        block which looks up the person table is executed. That's all we
        currently need to know.

    >>> import uuid
    >>> traverser.publishTraverse(object, str(uuid.uuid4()))
    Traceback (most recent call last):
    ComponentLookupError:...
    """

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def publishDefault(self, request, name):
        view = zope.component.queryMultiAdapter(
            (self.context, self.request), name=name)
        if view is not None:
            return view
        elif hasattr(self.context, name):
            return getattr(self.context, name)
        else:
            raise zope.publisher.interfaces.NotFound(
                self.context, name, self.request)

    def publishTraverse(self, request, name):
        try:
            uuid.UUID('urn:uuid:{}'.format(name))
        except ValueError:
            # ok name is not a UUID, why bother doing anything else
            return self.publishDefault(request, name)

        table = zope.component.queryUtility(
            IMappedTable, name='person')
        session = Session()
        person = session.query(table).filter_by(personid=name).first()
        if person is None:
            raise zope.publisher.interfaces.NotFound(
                self.context, name, self.request)
        return MockTable(person).__of__(self.context)


class MailForm(grok.View):
    """Form which can send out mail with given data."""
    grok.context(zope.interface.Interface)
    grok.name('mail')

    def render(self):
        return u'Go away'

    def prepare_and_send(self, mailtemplate, subject_templ, to_address, data):
        """ Sends an e-mail to the administrator. Set the @mailtemplate
            and the @subject_templ to customize the e-mail which is
            being send out and how the subject is formatted. The
            @subject_templ is a python string which can be formatted
            with the Python mini formatting language.
        """
        mailhost = self.context.MailHost
        portal = getToolByName(self.context,
                                'portal_url').getPortalObject()
        encoding = portal.getProperty('email_charset')
        subject = subject_templ.format(self=self)
        envelope_from = self.get_sendfrom_address(data)

        mail = email.MIMEMultipart.MIMEMultipart()
        mail_template = self.context.restrictedTraverse(mailtemplate)
        data.update(
            contextname=self.context.Title(),
            contexturl=self.context.absolute_url(),
            encoding=encoding)
        mail_template = mail_template()
        mail.attach(email.MIMEText.MIMEText(
            mail_template.encode(encoding), 'html', encoding))

        self.log(to_address, envelope_from, subject, data)
        mailhost.send(mail, to_address, envelope_from,
                               subject=subject, charset=encoding)

    def log(self, send_to_address, envelope_from, subject, data):
        logger = logging.getLogger(__name__)
        msg = 'Sending email {0} from {1} - "{2}": {3}'.format(
            send_to_address, envelope_from, subject, data)
        logger.info(msg)

    def get_sendfrom_address(self, data=None):
        portal = getToolByName(self.context,
                                'portal_url').getPortalObject()
        return data.get('fromemail',
                        portal.getProperty('email_from_address'))
