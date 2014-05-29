from five import grok
from zope import schema
from z3c.saconfig import named_scoped_session
from sqlalchemy import Column, Integer, DateTime, String, Sequence, sql
from sqlalchemy.orm import relationship
from nuw.types import Base
import logging

grok.templatedir('templates')
Session = named_scoped_session("nuw.types")
logger = logging.getLogger("nuw.types.login_tracking")

class LoginRecord(Base):
    __tablename__ = 'logins_registry'

    id = Column(Integer, Sequence("login_id"), primary_key=True)
    user_id = Column(Integer)
    user_name = Column(String)
    timestamp = Column(DateTime, nullable=False, default=sql.functions.now())
    
class PrintRecord(Base):
    __tablename__ = 'prints_registry'
    
    id = Column(Integer, Sequence("print_id"), primary_key=True)
    user_id = Column(Integer)
    user_name = Column(String)
    timestamp = Column(DateTime, nullable=False, default=sql.functions.now())