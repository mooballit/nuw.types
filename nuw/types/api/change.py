# Copyright (c) 2012 Mooball IT
# See also LICENSE.txt
from five import grok
from nuw.types import Base
from nuw.types.base import IMappedTable
from nuw.types.member import INUWItem
from sqlalchemy import Column, Integer, Enum, DateTime, Sequence,\
        String
from sqlalchemy.dialects.postgresql import UUID
from z3c.saconfig import named_scoped_session
from zope.lifecycleevent.interfaces import IObjectAddedEvent
from zope.lifecycleevent.interfaces import IObjectModifiedEvent
from zope.lifecycleevent.interfaces import IObjectRemovedEvent
import AccessControl
import datetime
import sqlalchemy.exc
import zope.interface
import zope.schema


Session = named_scoped_session('nuw.types')


class IChange(zope.interface.Interface):
    """This stores the data of the changed objects.

    Change objects are automatically created based on
    zope.lifecycleevent subscription. The API listens to the following
    events:

        * zope.lifecycleevent.interfaces.IObjectRemovedEvent
        * zope.lifecycleevent.interfaces.IObjectModifiedEvent
        * zope.lifecycleevent.interfaces.IObjectAddedEvent

    .. note:: Change items will only be created for objs which provide
              nuw.types.base.INUWItem.

    Change events can be triggered manually by issuing the event with
    the instance which has been updated/added/deleted, e.g.:

    >>> zope.event.notify(zope.lifecycleevent.ObjectModifiedEvent(obj))

    For newly added items you need to provide the parent. Provide your
    current context, the parent is not used by the subscription, e.g.:

    >>> zope.event.notify(
    ...     zope.lifecycleevent.ObjectAddedEvent(obj, parent, obj.id))

    """

    id = zope.schema.Int(
        title=u'Change ID',
        )

    changed = zope.schema.Datetime(
        title=u'Change Created',
        )

    action = zope.schema.Choice(
        title=u'Action',
        values=[u'add', u'update', u'delete']
        )

    oid = zope.schema.TextLine(
        title=u'Object ID',
        )

    otype = zope.schema.TextLine(
        title=u'Object Type',
        )

    principal = zope.schema.TextLine(
        title=u'User issuing the change',
        )


class Change(Base):
    __tablename__ = 'change'
    zope.interface.implements(IChange)

    id = Column(Integer, Sequence('change_id'), primary_key=True)
    modified = Column(DateTime)
    oid = Column(UUID, nullable=False)
    otype = Column(String)
    principal = Column(String)
    action = Column(Enum(
        'add', 'update', 'delete', name='change_action')
    )

    @property
    def referenced_obj(self):
        """ Returns the referenced object by this change item."""
        obj = None
        session = Session()
        table = zope.component.getUtility(IMappedTable, name=self.otype)
        try:
            obj = session.query(table).filter_by(hubid=self.oid).first()
        except sqlalchemy.exc.InvalidRequestError:
            pass
        return obj


@grok.subscribe(INUWItem, IObjectAddedEvent)
def track_insert(obj, event):
    create_change_item(obj, 'add')


@grok.subscribe(INUWItem, IObjectModifiedEvent)
def track_modification(obj, event):
    create_change_item(obj, 'update')


@grok.subscribe(INUWItem, IObjectRemovedEvent)
def track_deletion(obj, event):
    create_change_item(obj, 'delete')


def create_change_item(obj, mode):
    session = Session()
    principal = AccessControl.getSecurityManager().getUser()
    item = INUWItem(obj)
    _change = Change(action=mode,
                     modified=datetime.datetime.now(),
                     oid=item.hubid,
                     otype=item.metatype,
                     principal=principal.getUserName())
    session.add(_change)


class Index(grok.View):
    grok.context(Change)
    grok.require('zope2.Public')
