# Copyright (c) 2012 Mooball IT
# See also LICENSE.txt
"""
Activation
----------
This form is for existing NUW members.
"""
from Products.statusmessages.interfaces import IStatusMessage
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from Products.CMFCore.utils import getToolByName
from five import grok
from zope import event
from zope.interface import Interface
from zope.lifecycleevent import ObjectModifiedEvent
from nuw.types.browser.join import ISignupPerson
from nuw.types.member import Person, IPerson
from nuw.types.member import User
from plone.directives import form
from plone.app.layout.viewlets.interfaces import IBelowContent, IAboveContent
from sqlalchemy import func
from z3c.saconfig import named_scoped_session
import datetime
import nuw.types.base
import Products.CMFDefault.utils
import random
import string
import z3c.form.button
import z3c.form.field
import zope.interface
import zope.schema

from nuw.types.admin_area.admin_views import get_join_admin_email
from nuw.types.authentication import PLUGIN_NAME

grok.templatedir( 'activation_templates' )
Session = named_scoped_session('nuw.types')

class IActivationJoinViews(Interface):
    """ Marker interface for all views within the activation process.
    """
    pass

class CheckNUWMemberNumber(form.Form):
    """ First step in the activation process.

    The step collects the NUW Member Number and checks if the person is
    a member by querying the database.

    >>> from plone.testing.z2 import Browser
    >>> setup_activation_folder(layer['portal'])
    >>> portal_url = layer['portal'].absolute_url()
    >>> browser = Browser(layer['app'])
    >>> browser.open(portal_url + '/activation.html')

    People can not activate non-existing members:

    >>> browser.getControl('Member ID').value = 'foo'
    >>> browser.getControl('Lookup membership').click()
    >>> 'Unable to find member' in browser.contents
    True

    We will create a member now in order to allow him to continue to the
    next step:

    >>> import uuid
    >>> from nuw.types.member import Person
    >>> import transaction
    >>> memberid = u'NNMAYN00217925'
    >>> session = Session()
    >>> session.add(
    ...     Person(str(uuid.uuid4()), firstname=u'Tom',
    ...         lastname=u'Cameron', nuwdbid=memberid)
    ... )
    >>> transaction.commit()

    We try again:

    >>> browser.getControl('Member ID').value = memberid
    >>> browser.getControl('Lookup membership').click()

    and are forwarded to the next step:

    >>> from nuw.types.browser.activation import VerifyMember
    >>> VerifyMember.label in browser.contents
    True
    """
    grok.name('activation.html')
    grok.implements(IActivationJoinViews)
    grok.require('zope2.View')
    grok.context(zope.interface.Interface)

    ignoreContext = True

    label = u'Already an NUW member?'
    description = (u'For existing NUW members. Use this form to'
                   ' retrieve your login/password details or to activate'
                   ' your login if you have not already done so.')
    fields = z3c.form.field.Fields(IPerson).select('nuwdbid')

    def update(self):
        super(CheckNUWMemberNumber, self).update()
        self.request.set('disable_plone.leftcolumn', 1)
        self.request.set('disable_plone.rightcolumn', 1)
        self.request.set('disable_border', 1)

    def find_nuwmember(self, data):
        session = Session()

        nuwdbid = data.pop( 'nuwdbid', '' )

        query = session.query(Person)

        if nuwdbid:
            query = query.filter(
                func.upper( Person.nuwdbid ) == nuwdbid.upper().strip() )

        query = query.filter_by(**data)

        data['nuwdbid'] = nuwdbid

        return query.first()

    @z3c.form.button.buttonAndHandler(u'Submit >')
    def apply(self, action):
        data, errors = self.extractData()
        if errors:
            self.status = self.formErrorsMessage
            return
        person = self.find_nuwmember(data)
        if person is None:
            self.status = (
                u'Unable to find member with given number: {nuwdbid}'.format(
                    **data))
            return
        url = '/'.join([self.context.absolute_url(),
                        person.personid,
                        'verifymember.html'])
        self.redirect(url)

class VerifyMember(form.Form):
    """ Second step in the activation process.

    The second step activates the site login with a verification form
    based on their given details. One prerequisite is, that the person
    already exists. That's what step 1 was all about. Therefore we
    create a member on the fly:

    >>> import uuid
    >>> from nuw.types.member import Person
    >>> import transaction
    >>> memberid = u'NNMAYN00217925'
    >>> personid = str(uuid.uuid4())
    >>> data = dict(firstname=u'Tom', lastname=u'Cameron',
    ...     nuwdbid=memberid, homepostcode='4012', webstatus=u'member',
    ...     dob=u'1954-01-24T00:00:00')
    >>> session = Session()
    >>> session.add(
    ...     Person(personid, **data)
    ... )
    >>> transaction.commit()

    ..  note:: The example ``Person`` instance is created without an
        email. The email is provided by the member in the activation form.

    Now we can proceede with the second step:

    >>> from plone.testing.z2 import Browser
    >>> setup_activation_folder(layer['portal'])
    >>> portal_url = layer['portal'].absolute_url()
    >>> browser = Browser(layer['app'])
    >>> url = '/'.join([portal_url, personid, 'verifymember.html'])
    >>> browser.open(url)

    The member now fills out the fields in order to verify his identity.
    The email:

    >>> email = 'tom@mooball.net'

    is used to create the user and stored on the ``Person`` instance:

    >>> browser.getControl('Last Name').value = data[u'lastname']
    >>> browser.getControl('Postcode').value = '4151'
    >>> browser.getControl(name='form.widgets.dob-day').value = '24'
    >>> browser.getControl(name='form.widgets.dob-year').value = '1954'
    >>> browser.getControl('E-mail').value = email
    >>> browser.getControl('Activate my site login').click()

    Whoops wrong details:

    >>> from nuw.types.browser.activation import VerifyMember
    >>> VerifyMember.lookupErrorMessage in browser.contents
    True

    So the member now provides the correct details:

    >>> browser.getControl('Postcode').value = data['homepostcode']
    >>> browser.getControl('Activate my site login').click()

    and is forwarded to the password reset/set step:

    >>> from nuw.types.browser.activation import EmailVerification
    >>> EmailVerification.label in browser.contents
    True

    Furthermore, no members are allowed to activate their accounts who
    are not ``webstatus`` or ``non-financial``. This is a class
    attribute on the VerifyMember view:

    >>> ['member', 'non-financial'] == VerifyMember.allowedWebStatus
    True

    The email is now set against the example ``Person``:

    >>> person = session.query(Person).filter_by(personid=personid).one()
    >>> email == person.email
    True
    """
    grok.name('verifymember.html')
    grok.implements(IActivationJoinViews)
    grok.require('zope2.View')
    grok.context(nuw.types.base.MockTable)

    ignoreContext = True
    fields = z3c.form.field.Fields(ISignupPerson).select(
        'lastname', 'dob', 'homepostcode')
    fields += z3c.form.field.Fields( zope.schema.TextLine(
        __name__ = 'email',
        title=u'E-mail',
        description=u'This address will become your Site Login.<br>Logins are case' +\
                ' sensitive, please choose the case carefully',
        constraint=lambda val: Products.CMFDefault.utils.checkEmailAddress( val ) or True,
    ) )


    label = u'Activate your Site Login'
    description = (u'You have not yet activated your Site Login. Please'
                   ' provide the following information so that we can'
                   ' activate your site login. All fields are case sensitive,'
                   ' this means your email - your site login - is too,'
                   ' please choose wisely.')
    lookupErrorMessage = (
        u'Sorry, we are unable to find your membership. Please'
        ' check the details carefully and if you still have'
        ' problems call us on 1300 275 689 to activate your Login')

    memberHasLogin = False
    memberHasLoginErrorLabel = u'Reset your password'

    activation_email_tpl = ViewPageTemplateFile( 'activation_templates/activationdetailsconfirm.pt' )

    def update(self):
        super(VerifyMember, self).update()
        self.request.set('disable_plone.leftcolumn', 1)
        self.request.set('disable_plone.rightcolumn', 1)
        self.request.set('disable_border', 1)

        # member already has a log-in. Should proceede to the password
        # reset page
        person = self.context.table
        self.memberHasLogin = person.has_login()

    def verify(self, data):
        person = self.context.table
        if not isinstance(person.dob, datetime.datetime):
            return

        is_verified = (person.dob.date() == data['dob'] and
                       isinstance( person.lastname, basestring ) and
                       isinstance( data['lastname'], basestring ) and
                       person.lastname.lower() == data['lastname'].lower() and
                       person.homepostcode == data['homepostcode'] and
                       self._in_allowed_webstatus(person.webstatuses))
        same_person = self._is_same_person(data.get('email', ''))
        if is_verified and 'email' in data and same_person:
            person.email = data['email']
            return person

    def _in_allowed_webstatus(self, webstatuses):
        acl_users = getToolByName(self.context, 'acl_users')
        if acl_users and PLUGIN_NAME in acl_users:
            self.allowedWebStatus = acl_users[PLUGIN_NAME].webstatus
        else:
            return False

        for webstatus in webstatuses:
            if webstatus in self.allowedWebStatus:
                return True

    def _is_same_person(self, email):
        """ Query by email to check if the user is not attempting to
            overwrite another persons e-mail address.
        """
        session = Session()
        result = session.query(User).filter_by(name=email).count()
        return result == 0

    @z3c.form.button.buttonAndHandler(u'Submit >')
    def apply(self, action):
        data, errors = self.extractData()
        if errors:
            self.status = self.formErrorsMessage
            return
        person = self.verify(data)
        # wrong member number given or e-mail invalid
        if person is None:
            self.status = self.lookupErrorMessage
            return

        event.notify(
            ObjectModifiedEvent(person))

        mhost = getToolByName(self, 'MailHost')
        email = get_join_admin_email()
        mail_content = self.activation_email_tpl(
            to_email = email, name = person.firstname + ' ' + person.lastname,
            email = person.email, phone = person.home, mobile = person.mobile,
            personid = person.personid, portal_url = self.context.portal_url,
        )
        mhost.send( mail_content )

        # all is fine and dandy - proceede to the next step
        url = '/'.join([self.context.aq_parent.absolute_url(),
                        person.personid,
                        'verifyemail.html'])
        self.redirect(url)


class EmailVerification(grok.View):
    """ Third step in the activation process.

    The member arrives once he has verified himself in the two last
    steps. This step sends a confirmation e-mail to the user in order to
    confirm if his provided e-mail address is valid.

    We create an example member ``Person``:

    >>> import uuid
    >>> from nuw.types.member import Person
    >>> import transaction

    >>> data = dict(
    ...     personid=str(uuid.uuid4()),
    ...     firstname=u'Tom',
    ...     lastname=u'Cameron',
    ...     homepostcode='4012',
    ...     nuwdbid=u'NNMAYN00217925',
    ...     email=u'tom@foobar.net',
    ...     dob=u'1954-01-24T00:00:00')
    >>> session = Session()
    >>> session.add(
    ...     Person(**data)
    ... )
    >>> transaction.commit()

    With the member created, we procede now to the email confirmation
    step:

    >>> from plone.testing.z2 import Browser
    >>> portal_url = layer['portal'].absolute_url()
    >>> setup_activation_folder(layer['portal'])
    >>> browser = Browser(layer['app'])
    >>> url = '/'.join([portal_url, data['personid'], 'verifyemail.html'])
    >>> browser.handleErrors = False
    >>> browser.open(url)

    The view only renders a helpful message informing the user that a
    confirmation e-mail has been send:

    >>> from nuw.types.browser.activation import EmailVerification
    >>> EmailVerification.label in browser.contents
    True

    A confirmation email has been send to the member:

    >>> mailhost = layer['portal'].MailHost
    >>> len(mailhost.messages)
    1
    >>> mail = mailhost.messages[0]
    >>> 'To: {email}'.format(**data) in mail
    True

    with a randomly generated password which we'll use for verification
    in the next step:

    >>> from nuw.types.member import User
    >>> user = session.query(User).one()
    >>> user.password in mail
    True

    In case the user cancels the step at this point, but returns later,
    a new password and e-mail is generated:

    >>> old_password = user.password
    >>> browser.open(url)
    >>> len(mailhost.messages)
    2
    >>> user = session.query(User).one()
    >>> old_password != user.password
    True
    """
    grok.name('verifyemail.html')
    grok.require('zope2.View')
    grok.context(nuw.types.base.MockTable)

    label = u'Please check your mailbox'

    sent_email_tpl = ViewPageTemplateFile( 'activation_templates/activationemailsent.pt' )

    def update(self):
        self.request.set('disable_plone.leftcolumn', 1)
        self.request.set('disable_plone.rightcolumn', 1)
        self.request.set('disable_border', 1)
        person = self.context.table
        token = ''.join(random.sample(string.digits + string.letters, 30))
        session = Session()
        user = session.query(User).filter_by(name=person.email).first()
        if not user:
            user = User(name=person.email, password=token)
            person.user = user
            session.add(user)
        else:
            user.password = token
            person.user = user

        self.send_confirmation_email()

    def send_confirmation_email(self):
        person = self.context.table
        mailform = zope.component.getMultiAdapter(
            (self.context, self.request), name='mail')
        mailform.prepare_and_send(
            'activationsetpasswordmail.html',
            u'NUW website login activation',
            person.email, {})

        mhost = getToolByName(self, 'MailHost')
        email = get_join_admin_email()
        mail_content = self.sent_email_tpl(
            to_email = email, name = person.firstname + ' ' + person.lastname,
            email = person.email, phone = person.home, mobile = person.mobile,
            personid = person.personid, portal_url = self.context.portal_url,
        )
        mhost.send( mail_content )


class ActivationSetPassword(grok.View):
    grok.name('activationsetpasswordmail.html')
    grok.require('zope2.View')
    grok.context(nuw.types.base.MockTable)


def check_password_strength(value):
    """ Checks the password strength.

    Passwords need to be:

        #. at least contain 5 characters
        #. at least one uppercase character
        #. at least one lowercase character
        #. at least one number
    """
    valid = False
    try:
        ascii = value.encode('ascii')
    except UnicodeEncodeError:
        raise zope.interface.Invalid(
            u"You've chosen a password with special characters. Please"
            " choose only ASCII characters ({})".format(string.letters)
            )
    if len(ascii) >= 5:
        upper = lower = numbers = False
        for c in ascii:
            if c in string.uppercase:
                upper = True
            elif c in string.lowercase:
                lower = True
            elif c in string.digits:
                numbers = True

            if upper and lower and numbers:
                valid = True
                break
    if not valid:
        raise zope.interface.Invalid(
            u'Weak password. Please choose a password with at least 5'
            ' characters, one uppercase, one lowercase and at least one'
            ' number.')
    return valid


class IPasswordStep(zope.interface.Interface):

    login = zope.schema.TextLine(
        title=u'Your Login (E-mail)',
        readonly=True,
        )

    password = zope.schema.Password(
        title=u'Password',
        description=(u'Please choose a secure password. Passwords must'
                     ' contain min 5 characters, at least 1 uppercase, one'
                     ' lowercase and one number.'),
        constraint=check_password_strength,
        )

    password_confirm = zope.schema.Password(
        title=u'Confirm Password',
        description=u'Re-type your password.',
        )

    @zope.interface.invariant
    def password_confirmed(data):
        if data.password != data.password_confirm:
            raise zope.interface.Invalid(
                u'Password and Confirm Password have to be the same.')


class PasswordReset(form.Form):
    """ Fourth step in the activation process.

    This is the last step. The member arrives here if he verified, that
    he's a member and confirmed his e-mail.

    We create an example member ``Person`` and a ``User`` wich have been
    created in the previous step:

    >>> import uuid
    >>> from nuw.types.member import Person, User
    >>> import transaction

    >>> data = dict(
    ...     personid=str(uuid.uuid4()),
    ...     firstname=u'Tom',
    ...     lastname=u'Cameron',
    ...     homepostcode='4012',
    ...     nuwdbid=u'NNMAYN00217925',
    ...     email=u'tom@foobar.net',
    ...     dob=u'1954-01-24T00:00:00')
    >>> person = Person(**data)
    >>> person.user = User(name=data['email'], password='asdf')
    >>> session = Session()
    >>> session.add(person)
    >>> transaction.commit()

    >>> from plone.testing.z2 import Browser
    >>> setup_activation_folder(layer['portal'])
    >>> portal_url = layer['portal'].absolute_url()
    >>> browser = Browser(layer['app'])

    First to which could happen: the member confirms his e-mail but with an
    incorrect token (for whatever reason):

    >>> url = '/'.join([portal_url, data['personid'], 'password.html'])
    >>> browser.open(url + '?token=frob')

    An error message is displayed and he will not be able to set his
    password:

    >>> from nuw.types.browser.activation import PasswordReset
    >>> PasswordReset.notverified_label in browser.contents
    True
    >>> browser.getLink('clicking here') is not None
    True

    Lets say, the user clicked on the correct link. He'll see a password
    form. The form shows the e-mail address we've provided in the second
    step:

    >>> browser.open(url + '?token={}'.format(person.user.password))
    >>> pyquery(browser.contents)(
    ...     '#form-widgets-login').text() == data['email']
    True
    >>> PasswordReset.label in browser.contents
    True

    Now it's up to him to set his password:

    >>> browser.getControl('Password', index=0).value = '1Newpass'
    >>> browser.getControl('Confirm Password').value = '1Newpas'
    >>> browser.getControl('Set my new password').click()

    Whoops - the passwords don't match:

    >>> 'have to be the same' in browser.contents
    True
    >>> browser.getControl('Confirm Password').value = '1Newpass'
    >>> browser.getControl('Password', index=0).value = '1Newpass'
    >>> browser.getControl('Set my new password').click()
    >>> 'successfully' in browser.contents
    True
    """
    grok.name('password.html')
    grok.implements(IActivationJoinViews)
    grok.require('zope2.View')
    grok.context(nuw.types.base.MockTable)

    ignoreContext = True

    label = u'Set your Password.'
    description = (u'Your Site Login is activated. Set your password.')
    fields = z3c.form.field.Fields(IPasswordStep)

    verified = False
    notverified_label = u'Error: Your e-mail is not verified'

    password_email_tpl = ViewPageTemplateFile( 'activation_templates/activationpasswordreset.pt' )

    def update(self):
        # we query for the provided token and check with the generated
        # user password. If that's the case the user is allowed to set
        # his password now.
        super(PasswordReset, self).update()
        person = self.context.table
        if person.user is not None:
            token = self.get_token(person.user)
            self.verified = token == person.user.password
            # first time this form is called. Keep the token in the
            # browser session, since the form may be send off again with
            # incomplete data. If that happens we need to re-verify the
            # user again, otherwise we'll end up with an unverified,
            # incomplete mess
            if token and 'token' in self.request.form:
                browsersession = self.request.SESSION
                browsersession.set(person.user.name, token)
        self.request.set('disable_plone.leftcolumn', 1)
        self.request.set('disable_plone.rightcolumn', 1)
        self.request.set('disable_border', 1)

    def get_token(self, user):
        assert user is not None
        browsersession = self.request.SESSION
        return (browsersession.get(user.name, '')
                if 'token' not in self.request.form
                else self.request.form.get('token', '')
               )

    def updateWidgets(self):
        super(PasswordReset, self).updateWidgets()
        person = self.context.table
        self.widgets['login'].value = person.email

    @z3c.form.button.buttonAndHandler(u'Submit >')
    def apply(self, action):
        data, errors = self.extractData()
        if errors:
            self.verified = True
            self.status = self.formErrorsMessage
            return

        person = self.context.table
        person.user.password = data['password']
        # We don't need the token anymore.
        # XXX might cause a performance impact. Perhapse better to leave
        # it.
        if person.user.name in self.request.SESSION.keys():
            del self.request.SESSION[person.user.name]

        mhost = getToolByName(self, 'MailHost')
        email = get_join_admin_email()
        mail_content = self.password_email_tpl(
            to_email = email, name = person.firstname + ' ' + person.lastname,
            email = person.email, phone = person.home, mobile = person.mobile,
            personid = person.personid, portal_url = self.context.portal_url,
        )
        mhost.send( mail_content )

        IStatusMessage(self.request).addStatusMessage(
            u'Password successfully changed. Welcome to NUW. Please login.',
            'info')
        portal = getToolByName(
            self.context, 'portal_url').getPortalObject()
        self.redirect(self.url(portal, 'login',
                               {'__ac_name': person.user.name})
                     )


class ActivationGuideViewlet(grok.Viewlet):
    grok.context(nuw.types.base.MockTable)
    grok.name('nuw.types.activation.GuideViewlet')
    grok.viewletmanager(IBelowContent)

    def update(self):
        self.step_title = None
        self.step_description = None

        if 'verifymember.html' in self.request.getURL():
            self.step_title = u'Activate your site login'
            self.step_description = u'''
                You have not yet activated your Site Login. Please provide the
                following information so that we can activate your site login.
                '''
        if 'password.html' in self.request.getURL():
            self.step_title = u'Password Reset'
            self.step_description = u'''
                Reset your password by filling out the form to the right,
                an email will be sent to the address associated with your
                membership, click the link in the email to activate.
                '''

class ActivationHeaderViewlet(grok.Viewlet):
    grok.view(IActivationJoinViews)
    grok.context(Interface)
    grok.name('nuw.types.activation.HeaderViewlet')
    grok.viewletmanager(IAboveContent)
