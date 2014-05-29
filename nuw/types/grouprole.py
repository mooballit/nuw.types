# Copyright (c) 2012 Mooball IT
# See also LICENSE.txt
from five import grok
from nuw.types import Base
from nuw.types.base import IMappedTable
from nuw.types.base import INUWItem
from nuw.types.base import NUWItem
from nuw.types.base import XMLBase
from nuw.types.base import apply_data
from nuw.types.base import check_references
from sqlalchemy import Column, Integer, String, Sequence, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from z3c.saconfig import named_scoped_session
import zope.schema


Session = named_scoped_session('nuw.types')


class IGroupRole(INUWItem):

    grouproleid = zope.schema.TextLine(
        title=u'Group Role GUID',
    )

    groupid = zope.schema.TextLine(
        title=u'Group GUID',
    )

    supergroupid = zope.schema.TextLine(
        title=u'Supergroup GUID',
    )

    grouprole = zope.schema.TextLine(
        title=u'Title',
        required=False,
    )


class GroupRole(Base, NUWItem):
    zope.interface.implements(IGroupRole)
    __tablename__ = 'grouprole'

    id = Column(Integer, Sequence('grouprole_id'), primary_key=True)
    grouproleid = Column(UUID, unique=True)
    groupid = Column(UUID, ForeignKey('group.groupid'), nullable=False)
    supergroupid = Column(
        UUID, ForeignKey('supergroup.supergroupid'), nullable=False)
    grouprole = Column(String)

    @check_references('grouprole', ['supergroup', 'group'])
    def __init__(self, grouproleid, **kwargs):
        self.grouproleid = grouproleid
        apply_data(self, IGroupRole, kwargs)


grouproleFactory = zope.component.factory.Factory(GroupRole)
grok.global_utility(grouproleFactory, name='grouprole', direct=True)
grok.global_utility(
    GroupRole, provides=IMappedTable, name='grouprole', direct=True)


class XML(XMLBase):
    grok.context(IGroupRole)
    grok.require('zope2.Public')
