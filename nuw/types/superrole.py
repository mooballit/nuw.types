# copyright (c) 2012 mooball it
# See also LICENSE.txt
from five import grok
from nuw.types import Base
from nuw.types.base import IMappedTable
from nuw.types.base import INUWItem
from nuw.types.base import NUWItem
from nuw.types.base import VocabMixin
from nuw.types.base import XMLBase
from nuw.types.base import apply_data
from nuw.types.base import check_references
from nuw.types.base import create_or_get_typehelper
from nuw.types.base import vocabulary_factory
from plone.directives import form
from sqlalchemy import Column, Integer, Sequence, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, backref
from z3c.saconfig import named_scoped_session
import zope.schema


Session = named_scoped_session('nuw.types')


class ISuperRole(INUWItem, form.Schema):

    superroleid = zope.schema.TextLine(
        title=u'GUID',
    )

    supergroupid = zope.schema.TextLine(
        title=u'Supergroup GUID',
        )

    personid = zope.schema.TextLine(
        title=u'Person GUID',
        )

    superrole = zope.schema.Choice(
        title=u'Type',
        vocabulary='superroletypes',
    )


class SuperRoleType(Base, VocabMixin):
    __tablename__ = 'superroletype'

    id = Column(Integer, Sequence('superroletype_id'), primary_key=True)


def add_or_get_superroletype(token, name=None):
    return create_or_get_typehelper(token, SuperRoleType, name)

superroleTypeFactory = zope.component.factory.Factory(add_or_get_superroletype)
grok.global_utility(
    superroleTypeFactory, name='superrole.superrole', direct=True)


def superroletype_vocabulary(context):
    return vocabulary_factory(SuperRoleType)

grok.global_utility(superroletype_vocabulary,
                    provides=zope.schema.interfaces.IVocabularyFactory,
                    name='superroletypes', direct=True)


class SuperRole(Base, NUWItem):
    zope.interface.implements(ISuperRole)
    __tablename__ = 'superrole'

    id = Column(Integer, Sequence('role_id'), primary_key=True)
    superroleid = Column(UUID, unique=True)
    type_id = Column(Integer, ForeignKey('superroletype.id'))
    supergroupid = Column(
        UUID, ForeignKey('supergroup.supergroupid'), nullable=False)
    personid = Column(UUID, ForeignKey('person.personid'), nullable=False)

    superrole = relationship(SuperRoleType,
                             backref=backref('superroletype_id'))

    @check_references('superrole', ['supergroup', 'person'])
    def __init__(self, superroleid, **kwargs):
        self.superroleid = superroleid
        apply_data(self, ISuperRole, kwargs)


superroleFactory = zope.component.factory.Factory(SuperRole)
grok.global_utility(superroleFactory, name='superrole', direct=True)
grok.global_utility(
    SuperRole, provides=IMappedTable, name='superrole', direct=True)


class XML(XMLBase):
    grok.context(ISuperRole)
    grok.require('zope2.Public')
