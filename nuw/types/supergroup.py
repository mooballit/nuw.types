# Copyright (c) 2012 Mooball IT
# See also LICENSE.txt
from five import grok
from nuw.types import Base
from nuw.types.base import IMappedTable
from nuw.types.base import INUWItem
from nuw.types.base import NUWItem
from nuw.types.base import VocabMixin
from nuw.types.base import XMLBase
from nuw.types.base import apply_data
from nuw.types.base import create_or_get_typehelper
from nuw.types.base import vocabulary_factory
from plone.directives import form
from sqlalchemy import Column, Integer, Sequence, Unicode, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, backref
import zope.schema


class ISuperGroup(INUWItem, form.Schema):

    supergroupid = zope.schema.TextLine(
        title=u'GUID',
    )

    name = zope.schema.TextLine(
        title=u'Title',
        )

    type = zope.schema.Choice(
        title=u'Super Group Type',
        vocabulary='supergrouptypes',
        )


class SuperGroupType(Base, VocabMixin):
    __tablename__ = 'supergrouptype'

    id = Column(Integer, Sequence('supergrouptype_id'), primary_key=True)


def add_or_get_supergrouptype(token, name=None):
    return create_or_get_typehelper(token, SuperGroupType, name)

superGroupTypeFactory = zope.component.factory.Factory(
    add_or_get_supergrouptype)
grok.global_utility(superGroupTypeFactory, name='supergroup.type', direct=True)


def supergrouptype_vocabulary(context):
    return vocabulary_factory(SuperGroupType)

grok.global_utility(supergrouptype_vocabulary,
                    provides=zope.schema.interfaces.IVocabularyFactory,
                    name='supergrouptypes', direct=True)


class SuperGroup(Base, NUWItem):
    zope.interface.implements(ISuperGroup)
    __tablename__ = 'supergroup'

    id = Column(Integer, Sequence('supergroup_id'), primary_key=True)
    supergroupid = Column(UUID, unique=True)
    type_id = Column(Integer, ForeignKey('supergrouptype.id'))
    name = Column(Unicode)

    type = relationship(SuperGroupType, backref=backref('type_id'))

    def __init__(self, supergroupid, **kwargs):
        self.supergroupid = supergroupid
        apply_data(self, ISuperGroup, kwargs)


groupFactory = zope.component.factory.Factory(SuperGroup)
grok.global_utility(groupFactory, name='supergroup', direct=True)
grok.global_utility(
    SuperGroup, provides=IMappedTable, name='supergroup', direct=True)


class XML(XMLBase):
    grok.context(ISuperGroup)
    grok.require('zope2.Public')
