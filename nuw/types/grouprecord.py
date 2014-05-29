# Copyright (c) 2012 Mooball IT
# See also LICENSE.txt
from five import grok
from nuw.types import Base
from nuw.types.base import IMappedTable
from nuw.types.base import INUWItem
from nuw.types.base import NUWItem
from nuw.types.base import XMLBase
from nuw.types.base import apply_data
from sqlalchemy import Column, Integer, Sequence, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
import zope.schema


class IGroupRecord(INUWItem):

    grouprecordid = zope.schema.TextLine(
        title=u'GUID',
        )

    groupid = zope.schema.TextLine(
        title=u'Group GUID',
        )

    recordid = zope.schema.TextLine(
        title=u'Record GUID',
        )


class GroupRecord(Base, NUWItem):
    zope.interface.implements(IGroupRecord)
    __tablename__ = 'grouprecord'

    id = Column(Integer, Sequence('grouprecord_id'), primary_key=True)
    grouprecordid = Column(UUID, unique=True)
    groupid = Column(UUID, ForeignKey('group.groupid'), nullable=False)
    recordid = Column(UUID, ForeignKey('record.recordid'), nullable=False)

    def __init__(self, grouprecordid, **kwargs):
        self.grouprecordid = grouprecordid
        apply_data(self, IGroupRecord, kwargs)


grouprecordFactory = zope.component.factory.Factory(GroupRecord)
grok.global_utility(grouprecordFactory, name='grouprecord', direct=True)
grok.global_utility(
    GroupRecord, provides=IMappedTable, name='grouprecord', direct=True)


class XML(XMLBase):
    grok.context(IGroupRecord)
    grok.require('zope2.Public')
