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
from nuw.types.record import Record
from nuw.types.group import Group
from nuw.types.grouprecord import GroupRecord
from sqlalchemy import Column, Integer, String, Sequence, Unicode, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from z3c.saconfig import named_scoped_session
import zope.schema


Session = named_scoped_session('nuw.types')

def _find_groupid_with_many_files():
    sess = Session()
    for record in sess.query(GroupRecord):
        file_query = sess.query(File).filter(File.recordid == record.recordid)
        if file_query.count() > long(1):
            print record.groupid
            return record.groupid

def get_group_files(groupid):
    sess = Session()
    files = list()

    for group_record in sess.query(GroupRecord).filter(GroupRecord.groupid == groupid):
        file_dict = {'files':list()}
        for file in sess.query(File).filter(File.recordid == group_record.recordid):
            file_dict['files'].append(file)
        file_dict['record'] = sess.query(Record).filter(Record.recordid == group_record.recordid).first()
        file_dict['group'] = sess.query(Group).filter(Group.groupid == groupid).first()
        files.append(file_dict)

    return files

class IFile(INUWItem):
    """A file is a reference to any disk file that record might hold.
    """
    fileid = zope.schema.TextLine(
        title=u'GUID',
        )

    name = zope.schema.TextLine(
        title=u'The name of the file',
        required=False,
        )

    path = zope.schema.TextLine(
        title=u'Path',
        required=False,
        )

    extension = zope.schema.TextLine(
        title=u'File extension',
        required=False,
        )

    type = zope.schema.TextLine(
        title=u'File Type',
        required=False,
        )

    # ignored - #1892
    filenumber = zope.schema.TextLine(
        title=u'File Number',
        required=False,
        )

    sizebytes = zope.schema.Int(
        title=u'Filesize',
        required=False,
        )

    recordid = zope.schema.TextLine(
        title=u'The foreign key of the record',
        )


class File(Base, NUWItem):
    zope.interface.implements(IFile)
    __tablename__ = 'file'

    id = Column(Integer, Sequence('file_id'), primary_key=True)
    fileid = Column(UUID, unique=True)
    recordid = Column(UUID, ForeignKey('record.recordid'))
    name = Column(Unicode)
    path = Column(Unicode)
    extension = Column(String)
    sizebytes = Column(Integer)
    type = Column(String)

    record = relationship(Record, primaryjoin=recordid == Record.recordid)

    @check_references('file', ['record'])
    def __init__(self, fileid, **kwargs):
        self.fileid = fileid
        apply_data(self, IFile, kwargs)


fileFactory = zope.component.factory.Factory(File)
grok.global_utility(fileFactory, name='file', direct=True)
grok.global_utility(File, provides=IMappedTable, name='file', direct=True)


class XML(XMLBase):
    grok.context(IFile)
    grok.require('zope2.Public')
