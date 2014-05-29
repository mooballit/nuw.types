# Code based on PasswordResetTool by J Cameron Cooper, Sept 2003
from OFS.SimpleItem import SimpleItem
from zope.interface import implements
from zope.component import getUtility
from zope.lifecycleevent import ObjectModifiedEvent
from App.special_dtml import DTMLFile
from AccessControl import ClassSecurityInfo
from AccessControl import ModuleSecurityInfo
from nuw.types.member import email_exists, EmailExists, change_person_email
from Products.CMFDefault.utils import checkEmailAddress
from Products.CMFCore.permissions import ManagePortal
from Products.CMFCore.utils import getToolByName
from Products.CMFCore.utils import UniqueObject
from Products.CMFCore.interfaces import ISiteRoot
from Products.CMFPlone.RegistrationTool import get_member_by_login_name
from z3c.saconfig import named_scoped_session
from email import message_from_string
import zope

try:
    from hashlib import md5
except ImportError:
    from md5 import md5

try:
    from App.class_init import InitializeClass
except ImportError:
    from Globals import InitializeClass

from nuw.types.EmailUpdateTool.interfaces import portal_email_update
from nuw.types.member import User, Person

import datetime, time, random, socket
from DateTime import DateTime

Session = named_scoped_session('nuw.types')
module_security = ModuleSecurityInfo('Products.PasswordResetTool.PasswordResetTool')

def send_confirmation_email(context, new_email, username, person):
    '''
    Send out a confirmation email request to update a users email address.
    Will check that email is valid and if it exists, throw error otherwise.
    Requests an Update with EmailUpdateTool, creates a template from
    email_update_notify, and finally sends it off to the new email address
    with an activation link.
    '''
    if new_email is None or new_email == '':
        raise EmailAddressInvalid('Email field is empty, please supply one!')
    checkEmailAddress(new_email)
    if email_exists( new_email ):
        raise EmailExists
    
    registration = getToolByName(context, 'portal_registration')
    emupd = getToolByName(context, 'portal_email_update')
    update = emupd.requestUpdate(username, person.personid, new_email)
    firstname = person.preferredname or person.firstname
    mail_text = registration.email_update_notify(
            username=username, update=update,
            email=new_email, name=firstname + " " + person.lastname)
    encoding = getUtility(ISiteRoot).getProperty('email_charset', 'utf-8')
    if isinstance(mail_text, unicode):
        mail_text = mail_text.encode(encoding)
    message_obj = message_from_string(mail_text.strip())
    subject = message_obj['Subject']
    m_to = new_email
    m_from = message_obj['From']
    host = getToolByName(context, 'MailHost')
    host.send(mail_text, m_to, m_from, subject=subject, charset=encoding,
              immediate=True)

module_security.declarePublic('InvalidRequestError')
class InvalidRequestError(Exception):
    def __init__(self, value=''):
        self.value = value
    def __str__(self):
        return repr(self.value)

module_security.declarePublic('ExpiredRequestError')
class ExpiredRequestError(Exception):
    def __init__(self, value=''):
        self.value = value
    def __str__(self):
        return repr(self.value)

class EmailUpdateTool (UniqueObject, SimpleItem):
    implements(portal_email_update)
    
    id = 'portal_email_update'
    meta_type = 'Email Update Tool'
    plone_tool = 1

    _user_check = 1
    _timedelta = 168

    security = ClassSecurityInfo()

    # Core of Tool
    def __init__(self):
        self._requests = {}

    security.declarePublic(ManagePortal, 'requestUpdate')
    def requestUpdate(self, userid, personid, email):
        """Ask the system to start the email update procedure for
        user 'userid'.

        Returns a dictionary with the random string that must be
        used to reset the password in 'randomstring', the expiration date
        as a DateTime in 'expires', and the userid (for convenience) in
        'userid'. Returns None if no such user.
        """
        randomstring = self.uniqueString(userid)
        expiry = self.expirationDate()
        self._requests[randomstring] = (userid, personid, expiry, email)

        self.clearExpired(10)   # clear out untouched records more than 10 days old
                                # this is a cheap sort of "automatic" clearing
        self._p_changed = 1

        retval = {}
        retval['randomstring'] = randomstring
        retval['expires'] = expiry
        retval['userid'] = userid
        retval['personid'] = personid
        retval['email'] = email
        return retval

    security.declarePublic('updateEmail')
    def updateEmail(self, randomstring):
        """Set the password (in 'password') for the user who maps to
        the string in 'randomstring' iff the entered 'userid' is equal
        to the mapped userid. (This can be turned off with the
        'toggleUserCheck' method.)

        Note that this method will *not* check password validity: this
        must be done by the caller.

        Throws an 'ExpiredRequestError' if request is expired.
        Throws an 'InvalidRequestError' if no such record exists,
        or 'userid' is not in the record.
        """
        try:
            stored_user, personid, expiry, email = self._requests[randomstring]
        except KeyError:
            raise InvalidRequestError
            
        if email_exists( email ):
            raise EmailExists

        if self.expired(expiry):
            del self._requests[randomstring]
            self._p_changed = 1
            raise ExpiredRequestError

        # actually change email
        sess = Session()
        person = sess.query(Person).filter(Person.personid == personid).first()

        if not person:
            raise InvalidRequestError

        # Update any subscriptions and change email
        change_person_email( self, person, email )
        person.email = email

        # notify the API
        zope.event.notify(ObjectModifiedEvent(person))

        # clean out the request
        del self._requests[randomstring]
        self._p_changed = 1

    security.declareProtected(ManagePortal, 'setExpirationTimeout')
    def setExpirationTimeout(self, timedelta):
        """Set the length of time a reset request will be valid.

        Takes a 'datetime.timedelta' object (if available, since it's
        new in Python 2.3) or a number of hours, possibly
        fractional. Since a negative delta makes no sense, the
        timedelta's absolute value will be used."""
        self._timedelta = abs(timedelta)

    security.declarePublic('getExpirationTimeout')
    def getExpirationTimeout(self):
        """Get the length of time a reset request will be valid.

        In hours, possibly fractional. Ignores seconds and shorter."""
        try:
            if isinstance(self._timedelta, datetime.timedelta):
                return self._timedelta.days * 24
        except NameError:
            pass  # that's okay, it must be a number of hours...
        return self._timedelta

    security.declarePublic('verifyKey')
    def verifyKey(self, key):
        """Verify a key. Raises an exception if the key is invalid or expired.
        """
        try:
            u, personid, expiry, email = self._requests[key]
        except KeyError:
            raise InvalidRequestError

        if self.expired(expiry):
            raise ExpiredRequestError

    security.declarePrivate('clearExpired')
    def clearExpired(self, days=0):
        """Destroys all expired reset request records.
        Parameter controls how many days past expired it must be to disappear.
        """
        for key, record in self._requests.items():
            stored_user, personid, expiry, email = record
            if self.expired(expiry, DateTime()-days):
                del self._requests[key]
                self._p_changed = 1

    # customization points

    security.declarePrivate('uniqueString')
    def uniqueString(self, userid):
        """Returns a string that is random and unguessable, or at
        least as close as possible.

        This is used by 'requestReset' to generate the auth
        string. Override if you wish different format.

        This implementation ignores userid and simply generates a
        UUID. That parameter is for convenience of extenders, and
        will be passed properly in the default implementation."""
        # this is the informal UUID algorithm of
        # http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/213761
        # by Carl Free Jr
        t = long( time.time() * 1000 )
        r = long( random.random()*100000000000000000L )
        try:
            a = socket.gethostbyname( socket.gethostname() )
        except:
            # if we can't get a network address, just imagine one
            a = random.random()*100000000000000000L
        data = str(t)+' '+str(r)+' '+str(a)#+' '+str(args)
        data = md5(data).hexdigest()
        return str(data)

    security.declarePrivate('expirationDate')
    def expirationDate(self):
        """Returns a DateTime for exipiry of a request from the
        current time.

        This is used by housekeeping methods (like clearEpired)
        and stored in reset request records."""
        if not hasattr(self, '_timedelta'):
            self._timedelta = 168
        if isinstance(self._timedelta,datetime.timedelta):
            expire = datetime.datetime.utcnow() + self._timedelta
            return DateTime(expire.year,
                            expire.month,
                            expire.day,
                            expire.hour,
                            expire.minute,
                            expire.second,
                            'UTC')
        expire = time.time() + self._timedelta*3600  # 60 min/hr * 60 sec/min
        return DateTime(expire)

    # internal

    security.declarePrivate('expired')
    def expired(self, datetime, now=None):
        """Tells whether a DateTime or timestamp 'datetime' is expired
        with regards to either 'now', if provided, or the current
        time."""
        if not now:
            now = DateTime()
        return now.greaterThanEqualTo(datetime)

InitializeClass(EmailUpdateTool)
