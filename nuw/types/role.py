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
from nuw.types.base import check_references
from nuw.types.base import create_or_get_typehelper
from nuw.types.base import vocabulary_factory
from nuw.types.group import Group
from nuw.types.supergroup import SuperGroup
from nuw.types.grouprole import GroupRole
from nuw.types.member import Person
from plone.directives import form
from sqlalchemy import Column, Integer, Sequence, ForeignKey, DateTime, or_
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, backref
from z3c.saconfig import named_scoped_session
from datetime import datetime
import zope.schema

Session = named_scoped_session('nuw.types')


def _get_groups_from_person_by_roletype(personid, roletype_token):
    """Return a persons groups based on specified roletype.

    Searches through the Role table for the logged in users, and their given
    roles, return a list of 'nuw.types.group.Group' objects.

    Filter out these roles by using 'roletype_token' to select a roletype,
    for example: roletype_token = "Employee" or "Delegate", etc
        -> Person
        -> Query Role(current personid, no enddate, Roletype(roletype_token))
        -> Iterate through Roles, return list of Group objects (from Role.group)

    :param personid: Member/Persons personid from NUW DB
    :type personid: UUID
    :param roletype_token: The RoleType that has to be searched for;
                           'Labour Hire', 'Delegate', etc
    :type roletype_token: str
    """

    groups = []
    sess = Session()
    roles = sess.query(Role).join('role').filter(
        Role.personid == personid,
        or_(Role.enddate <= datetime.now(), Role.enddate == None),
        RoleType.token == roletype_token).order_by(Role.groupid.asc())
    for role in roles:
        groups.append(role.group)

    return groups


def _get_reps_from_groupid( groupid ):
    """Return a list of reps from a specific worksite/group.
    
    :param groupid: Group/Worksite groupid from NUW DB
    :type groupid: UUID
    """
    reps = []
    
    sess = Session()
    group_reps = sess.query( Role ).join( 'role' ).filter(
            Role.groupid == groupid,
            or_(Role.enddate <= datetime.now(), Role.enddate == None),
            RoleType.token == 'Web Rep' )
    
    for rep in group_reps:
        reps.append(rep.person)
    
    return reps

def _get_person_from_id( personid ):
    sess = Session()
    person = sess.query( Person ).filter( Person.personid == personid ).first()
    return person

# Helper Functions


def get_roletype_from_person(person):
    """Returns a RoleType instance for the given person.

    :param person: a person instance
    :rtype: RoleType instance or [] if person is not given a role.
    """
    session = Session()
    types = session.query(RoleType).filter(
        Role.personid == person.personid, Role.type_id ==
        RoleType.id).all()
    return types


def get_person_nuw_member_number( personid ):
    person = _get_person_from_id(personid)
    if person:
        return person.nuwdbid

def get_person_nuw_assist_number( personid ):
    person = _get_person_from_id(personid)
    if person:
        return person.nuwassistid

def get_person_nuw_member_type( personid ):
    person = _get_person_from_id(personid)
    if person:
        if hasattr(person.type, 'name'):
            return person.type.name

def get_person_nuw_member_status( personid ):
    person = _get_person_from_id(personid)
    if person:
        return person.status

def get_person_nuw_activity_level( personid ):
    person = _get_person_from_id(personid)
    if person:
        if hasattr(person.activity, 'title'):
            return person.activity.title()

def is_person_labourhire( personid ):
    """Check to see if Person is Labour Hire.
    
    :param personid: Member/Persons personid from NUW DB
    :type personid: UUID
    """
    if _get_groups_from_person_by_roletype(personid, 'Labour Hire'):
        return True
    return False

def is_person_delegate( personid ):
    """Check to see if Person is Delegate.
    
    :param personid: Member/Persons personid from NUW DB
    :type personid: UUID
    """
    if _get_groups_from_person_by_roletype(personid, 'Delegate'):
        return True
    return False

def is_person_hsr( personid ):
    """Check to see if Person is HSR.
    
    :param personid: Member/Persons personid from NUW DB
    :type personid: UUID
    """
    if _get_groups_from_person_by_roletype(personid, 'HSR'):
        return True
    return False

def get_person_agencies( personid ):
    """Retrieve all agencies attributed to given Person
    
    Will return a list of 'group' objects, each of which are agencies.
    
    :param personid: Member/Persons personid from NUW DB
    :type personid: UUID
    """
    if is_person_labourhire(personid):
        agency = _get_groups_from_person_by_roletype(personid, 'Employee')
        return agency

def get_person_worksites( personid ):
    """Retrieve all worksites attributed to given Person
    
    Will return a list of 'group' objects, each of which are worksites.
    
    :param personid: Member/Persons personid from NUW DB
    :type personid: UUID
    """
    worksites = _get_groups_from_person_by_roletype(personid, 'Labour Hire')
    if not is_person_labourhire(personid):
        worksites = _get_groups_from_person_by_roletype(personid, 'Employee')
    return worksites

def get_person_employers( personid ):
    """Retrieve all employers attributed to given Person
    
    Will return a list of 'group' objects, each of which are employers.
    If an employer is found, will check for supergroups, and acquire the
    supergroup that is attributed to the person.
    
    :param personid: Member/Persons personid from NUW DB
    :type personid: UUID
    """
    sess = Session()
    supergroup_employers = list()
    for employer in _get_groups_from_person_by_roletype(personid, 'Employee'):
        for grouprole in sess.query(GroupRole).filter(
                GroupRole.groupid == employer.groupid):
            if grouprole.grouprole == "Child Site":
                for supergroup in sess.query(SuperGroup).filter(
                        SuperGroup.supergroupid == grouprole.supergroupid):
                    supergroup_employers.append(supergroup)

    if len(supergroup_employers):
        return supergroup_employers

    # if no ownership
    return get_person_worksites(personid)

def get_person_reps( personid ):
    """Retrieve all reps from each worksite attributed to given Person 
    
    Will return a list of lists. The sub-list being populated of 'person' objects,
    each 'person' object being a rep. Each sub-list is generated from the persons worksites.
    For example:
                / worksite1_reps \  / worksite2_reps \
    rep_list = [[person1, person2], [person4, person9]]
    
    :param personid: Member/Persons personid from NUW DB
    :type personid: UUID
    """
    rep_list = []
    for worksite in get_person_worksites(personid):
        rep_list.append({'worksite':worksite, 'reps':_get_reps_from_groupid(worksite.groupid)})
    return rep_list


class IRole(INUWItem, form.Schema):

    roleid = zope.schema.TextLine(
        title=u'GUID',
    )

    personid = zope.schema.TextLine(
        title=u'Person ID',
        )

    groupid = zope.schema.TextLine(
        title=u'Group ID',
        )

    role = zope.schema.TextLine(
        title=u'Type',
        )

    startdate = zope.schema.Datetime(
        title=u'Assignment Date',
        )

    enddate = zope.schema.Datetime(
        title=u'Expiry Date',
        required=False,
        )


class RoleType(Base, VocabMixin):
    __tablename__ = 'roletype'

    id = Column(Integer, Sequence('roletype_id'), primary_key=True)


def add_or_get_roletype(token, name=None):
    return create_or_get_typehelper(token, RoleType, name)

roleTypeFactory = zope.component.factory.Factory(add_or_get_roletype)
grok.global_utility(roleTypeFactory, name='role.role', direct=True)


def roletype_vocabulary(context):
    return vocabulary_factory(RoleType)

grok.global_utility(roletype_vocabulary,
                    provides=zope.schema.interfaces.IVocabularyFactory,
                    name='roletypes', direct=True)


class Role(Base, NUWItem):
    zope.interface.implements(IRole)
    __tablename__ = 'role'

    id = Column(Integer, Sequence('role_id'), primary_key=True)
    roleid = Column(UUID, unique=True)
    type_id = Column(Integer, ForeignKey('roletype.id'))
    groupid = Column(UUID, ForeignKey('group.groupid'), nullable=False)
    personid = Column(UUID, ForeignKey('person.personid'), nullable=False)
    startdate = Column(DateTime, nullable=False)
    enddate = Column(DateTime)

    role = relationship(RoleType, backref=backref('roletype_id'))
    group = relationship(Group, primaryjoin=groupid == Group.groupid)
    person = relationship(Person, primaryjoin=personid == Person.personid)

    @check_references('role', ['group', 'person'])
    def __init__(self, roleid, **kwargs):
        self.roleid = roleid
        apply_data(self, IRole, kwargs)


roleFactory = zope.component.factory.Factory(Role)
grok.global_utility(roleFactory, name='role', direct=True)
grok.global_utility(Role, provides=IMappedTable, name='role', direct=True)


class XML(XMLBase):
    grok.context(IRole)
    grok.require('zope2.Public')
