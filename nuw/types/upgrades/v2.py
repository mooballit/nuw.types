# Copyright (c) 2012 Mooball IT
# See also LICENSE.txt
from migrate.changeset.schema import rename_table, alter_column
from nuw.types import Base
from nuw.types.wall import Post
from nuw.types.file import File
from nuw.types.member import Person
from sqlalchemy import Integer, Column, String, Boolean
from sqlalchemy import MetaData
from z3c.saconfig import named_scoped_session
import nuw.types.setuphandlers as setuphandlers


Session = named_scoped_session("nuw.types")


def upgrade_01_to_2(setuptool):
    session = Session()
    rename_table('members', 'member', session.bind)
    rename_table('posts', 'post', session.bind)


def upgrade_2_to_201( context ):
    session = Session()

    # Rename the member table to user along with some columns etc.
    metadata = MetaData()

    rename_table('member', 'user', session.bind)
    alter_column( 'id', table = 'user', metadata = metadata, engine = session.bind )
    alter_column( 'group', table = 'user', metadata = metadata, engine = session.bind )

    # Remove old Pas plugin as its class has been renamed
    portal = context.aq_parent

    pas = context.acl_users
    pas.manage_delObjects( [ setuphandlers.plugin_name ] )

    # Add the new one
    setuphandlers.install_pas_plugin( portal )


def upgrade_201_to_203(context):
    session = Session()

    Base.metadata.bind = session.bind

    File.__table__.c.sizebytes.drop()
    File.__table__.create_column(Column('sizebytes', Integer))
    File.__table__.create_column(Column('type', String))


def upgrade_201_to_203_column_rename(context):
    session = Session()
    Base.metadata.bind = session.bind

    alter_column('filename', name='name',
                 table='file', metadata=MetaData(),
                 engine=session.bind)


def upgrade_203_to_204(context):
    session = Session()
    Base.metadata.bind = session.bind

    Post.__table__.create_column(Column('private', Boolean))

def upgrade_204_to_205(context):
    session = Session()
    Base.metadata.bind = session.bind

    alter_column('lote', name='languagemain',
                 table='person', metadata=MetaData(),
                 engine=session.bind)

    Person.__table__.create_column(Column('languagetranslate', String))
    Person.__table__.create_column(Column('languageneed', String))
    Person.__table__.drop_column('cantranslate')

def upgrade_205_to_206(context):
    session = Session()
    Base.metadata.bind = session.bind

    alter_column('languagetranslate', name='languagetranslator',
                 table='person', metadata=MetaData(),
                 engine=session.bind)
