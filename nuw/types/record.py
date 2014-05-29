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
from sqlalchemy import Column, Integer, String, Sequence, UnicodeText,\
        Unicode, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, backref
import zope.schema


class IRecord(INUWItem):
    """A record is any piece of communication or documentation about a
       member, potential member or work-site.
    """
    recordid = zope.schema.TextLine(
        title=u'GUID',
        )

    notes = zope.schema.TextLine(
        title=u'Body of the message',
        required=False,
        )

    type = zope.schema.Choice(
        title=u'Type',
        vocabulary='recordtypes',
        )

    tags = zope.schema.TextLine(
        title=u'Keywords for the Message',
        required=False,
        )

    startdate = zope.schema.Datetime(
        title=u'Agreement Date',
        required=False,
        )

    enddate = zope.schema.Datetime(
        title=u'Agreement Expiry Date',
        required=False,
        )

    referencenumber = zope.schema.TextLine(
        title=u'Reference # of Agreement',
        required=False,
        )


class RecordType(Base, VocabMixin):
    __tablename__ = 'recordtype'

    id = Column(Integer, Sequence('recordtype_id'), primary_key=True)


def add_or_get_recordtype(token, name=None):
    return create_or_get_typehelper(token, RecordType, name)

recordTypeFactory = zope.component.factory.Factory(add_or_get_recordtype)
grok.global_utility(recordTypeFactory, name='record.type', direct=True)


def recordtype_vocabulary(context):
    return vocabulary_factory(RecordType)

grok.global_utility(recordtype_vocabulary,
                    provides=zope.schema.interfaces.IVocabularyFactory,
                    name='recordtypes', direct=True)


class Record(Base, NUWItem):
    zope.interface.implements(IRecord)
    __tablename__ = 'record'

    id = Column(Integer, Sequence('record_id'), primary_key=True)
    recordid = Column(UUID, unique=True)
    recordtype_id = Column(Integer, ForeignKey('recordtype.id'))
    notes = Column(UnicodeText)
    tags = Column(Unicode)
    startdate = Column(DateTime)
    enddate = Column(DateTime)
    referencenumber = Column(String)

    type = relationship(RecordType, backref=backref('recordtype_id'))

    def __init__(self, recordid, **kwargs):
        self.recordid = recordid
        apply_data(self, IRecord, kwargs)


recordFactory = zope.component.factory.Factory(Record)
grok.global_utility(recordFactory, name='record', direct=True)
grok.global_utility(Record, provides=IMappedTable, name='record', direct=True)


class XML(XMLBase):
    grok.context(IRecord)
    grok.require('zope2.Public')
