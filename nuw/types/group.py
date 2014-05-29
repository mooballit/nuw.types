# Copyright (c) 2012 Mooball IT
# See also LICENSE.txt
from five import grok
from nuw.types import Base
from nuw.types.base import ContactDetailsMixin
from nuw.types.base import IContactDetails
from nuw.types.base import IMappedTable
from nuw.types.base import INUWItem
from nuw.types.base import NUWItem
from nuw.types.base import VocabMixin
from nuw.types.base import XMLBase
from nuw.types.base import apply_data
from nuw.types.base import create_or_get_typehelper
from nuw.types.base import vocabulary_factory
from sqlalchemy import Column, Integer, String, Sequence, UnicodeText,\
        Unicode, ForeignKey, text, bindparam
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql.expression import case
from sqlalchemy.orm import relationship, backref, column_property
from z3c.formwidget.query.interfaces import IQuerySource
from z3c.saconfig import named_scoped_session
from zope.schema.interfaces import IContextSourceBinder, IVocabularyTokenized
from zope.schema.vocabulary import SimpleVocabulary
import zope.schema
from pprint import pprint


Session = named_scoped_session('nuw.types')


class IGroup(INUWItem, IContactDetails):
    """A describes a collection of people, typically a work site."""

    groupid = zope.schema.TextLine(
        title=u'GUID',
    )

    name = zope.schema.TextLine(
        title=u'Name'
    )

    type = zope.schema.Choice(
        title=u'Type',
        vocabulary='grouptypes',
    )

    siteaddress1 = zope.schema.TextLine(
        title=u'Site Addressline 1',
        required=False,
    )

    siteaddress2 = zope.schema.TextLine(
        title=u'Site Addressline 2',
        required=False,
    )

    sitesuburb = zope.schema.TextLine(
        title=u'Suburb',
        required=False,
    )

    sitestate = zope.schema.TextLine(
        title=u'State',
        required=False,
    )

    sitepcode = zope.schema.TextLine(
        title=u'Postcode',
        required=False,
    )

    reception = zope.schema.TextLine(
        title=u'Reception phone number',
        required=False,
    )

    www = zope.schema.TextLine(
        title=u'Web site',
        required=False,
    )

    abn = zope.schema.TextLine(
        title=u'ABN',
        required=False,
    )


class GroupType(Base, VocabMixin):
    __tablename__ = 'grouptype'

    id = Column(Integer, Sequence('grouptype_id'), primary_key=True)


def add_or_get_grouptype(token, name=None):
    return create_or_get_typehelper(token, GroupType, name)

groupTypeFactory = zope.component.factory.Factory(add_or_get_grouptype)
grok.global_utility(groupTypeFactory, name='group.type', direct=True)


def grouptype_vocabulary(context):
    return vocabulary_factory(GroupType)

grok.global_utility(grouptype_vocabulary,
                    provides=zope.schema.interfaces.IVocabularyFactory,
                    name='grouptypes', direct=True)


class Group(Base, ContactDetailsMixin, NUWItem):
    zope.interface.implements(IGroup)
    __tablename__ = 'group'

    id = Column(Integer, Sequence('group_id'), primary_key=True)
    groupid = Column(UUID, unique=True)
    grouptype_id = Column(Integer, ForeignKey('grouptype.id'))
    name = Column(Unicode)
    siteaddress1 = Column(UnicodeText)
    siteaddress2 = Column(UnicodeText)
    sitesuburb = Column(Unicode)
    sitestate = Column(Unicode)
    sitepcode = Column(String)
    reception = Column(String)
    www = Column(Unicode)
    abn = Column(String)

    type = relationship(GroupType, backref=backref('grouptype_id'))

    long_name = column_property( name + ' (' + \
            case([(sitesuburb==None, 'NULL')], else_=sitesuburb) + ' - ' + \
            case([(sitestate==None, 'NULL')], else_=sitestate) + ')' \
        )

    def __init__(self, groupid, **kwargs):
        self.groupid = groupid
        apply_data(self, IGroup, kwargs)


groupFactory = zope.component.factory.Factory(Group)
grok.global_utility(groupFactory, name='group', direct=True)
grok.global_utility(Group, provides=IMappedTable, name='group', direct=True)


class XML(XMLBase):
    grok.context(IGroup)
    grok.require('zope2.Public')


def get_groups_by_type( type_token, name_filter = None ):
    sess = Session()
    result = sess.query( Group ).filter( Group.grouptype_id == GroupType.id, GroupType.token == type_token )

    if name_filter:
        result = result.filter( Group.long_name.ilike( '%%%s%%' % name_filter ) )

    result = result.order_by( Group.long_name )

    return result

def is_group_market_research(group, hubid=False):
    sess = Session()
    query = text("""select groupid from grouprole where supergroupid in
                    (select supergroupid from supergroup where name ilike '%market%' and type_id = 4)
                """);
    result = sess.execute(query)
    groups = [group_id[0] for group_id in result]
    if hubid:
        if group in groups:
            return True
        else:
            return False

    if group.groupid in groups:
        return True
    else:
        return False

class GroupQuerySourceBase( object ):
    zope.interface.implements( IQuerySource, IVocabularyTokenized )
    filter_token = u''  # token to filter when querying the database

    def __init__(self, context):
        self.context = context
        self.terms = None
        self.by_id = None

    def _create_terms( self, name_filter = None ):
        self.terms = []
        self.by_id = {}
        sess = Session()

        if self.filter_token == 'Employment Agency':
            query = text("""
                        with first_group_for_each_parent as (
                            SELECT min(g.nuwassistid) nuwassistid,
                                CASE WHEN sg.name is null THEN g.name ElSE sg.name END
                            FROM "group" g
                            LEFT JOIN (
                                SELECT gr.groupid, sg.supergroupid, sg.name
                                FROM grouprole gr
                                INNER JOIN supergroup sg on gr.supergroupid = sg.supergroupid
                                WHERE
                                    sg.type_id IN (SELECT id FROM supergrouptype WHERE token = 'Ownership Group')
                                )    sg on g.groupid = sg.groupid
                                WHERE
                                    grouptype_id IN (SELECT id FROM grouptype WHERE token = 'Employment Agency')
                                GROUP BY
                                    CASE WHEN sg.name is null THEN g.name ELSE sg.name END
                        )
                        SELECT g.groupid, p.name
                        FROM first_group_for_each_parent p
                        INNER JOIN "group" g on p.nuwassistid = g.nuwassistid
                        WHERE p.name ilike :name_filter
                        ORDER BY p.name;
                                    """, bindparams=[bindparam('name_filter', ('%%%s%%' % name_filter))])
        else:
            query = text("""
                    with results as (
                        SELECT g.groupid, g.name, g.sitesuburb,
                            CASE WHEN parent.name is null THEN
                            regexp_replace(g.name, coalesce(g.sitesuburb, ''), '', 'i') ELSE parent.name end || upper(coalesce(' ' || g.sitesuburb, '')) proposed_name
                        FROM "group" g
                        LEFT JOIN (
                            SELECT gr.groupid groupid, regexp_replace(regexp_replace(sg.name, 'pay centre', '', 'i'), 'payin', 'i') AS name
                            FROM grouprole gr
                            INNER JOIN supergroup sg on gr.supergroupid = sg.supergroupid
                            WHERE sg.type_id IN (SELECT id FROM supergrouptype WHERE token = 'Ownership Group')
                            AND not sg.name ilike '%debit%'
                            ) parent ON g.groupid = parent.groupid
                        WHERE g.grouptype_id IN (SELECT id FROM grouptype WHERE token = 'Union Site')
                        AND coalesce(g.sitesuburb, '') <> ''
                        ORDER BY
                            CASE WHEN parent.name is null THEN
                            regexp_replace(g.name, g.sitesuburb, '', 'i') ELSE parent.name end || upper(coalesce(' ' || g.sitesuburb, ''))
                    )
                    SELECT r.groupid, r.proposed_name
                    FROM results r
                    WHERE r.proposed_name ilike :name_filter
                    ORDER BY r.proposed_name;
                                    """, bindparams=[bindparam('name_filter', ('%%%s%%' % name_filter))])

        result = sess.execute(query)
        for place in result:
            term = SimpleVocabulary.createTerm(
                place[0], place[0], place[1])
            self.terms.append(term)
            self.by_id[place[0]] = term
        return self.terms

    def __contains__( self, value ):
        """See zope.schema.interfaces.IBaseVocabulary"""
        if self.terms is None:
            self._create_terms()

        try:
            return value in self.by_id
        except TypeError:
            # sometimes values are not hashable
            return False

    def getTerm( self, value ):
        """See zope.schema.interfaces.IBaseVocabulary"""
        if self.terms is None:
            self._create_terms()

        try:
            return self.by_id[value]
        except KeyError:
            raise LookupError(value)

    def getTermByToken( self, token ):
        """See zope.schema.interfaces.IVocabularyTokenized"""
        return self.getTerm( token )

    def __iter__( self ):
        """See zope.schema.interfaces.IIterableVocabulary"""
        if self.terms is None:
            self._create_terms()

        return iter( self.terms )

    def __len__( self ):
        """See zope.schema.interfaces.IIterableVocabulary"""
        if self.terms is None:
            self._create_terms()

        return len( self.terms )


    def search( self, query_string ):
        """See z3c.formwidget.query.interfaces.IQuerySource"""
        self._create_terms( query_string )

        return self.terms


class WorkSiteSource(GroupQuerySourceBase):
    filter_token = u'Union Site'


@grok.provider(IContextSourceBinder)
def worksites_source_binder(context):
    return WorkSiteSource(context)


class AgencySource(GroupQuerySourceBase):
    filter_token = u'Employment Agency'


@grok.provider(IContextSourceBinder)
def agency_source_binder(context):
    return AgencySource(context)
