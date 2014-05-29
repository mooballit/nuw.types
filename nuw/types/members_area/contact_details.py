from five import grok
from members_area import get_or_kick_user
from OFS.interfaces import IFolder
from nuw.types.member import IPerson, Person

from zope.lifecycleevent import ObjectModifiedEvent

from zope.i18nmessageid import MessageFactory
from z3c.form import button

from plone.directives import form
from z3c.saconfig import named_scoped_session
import z3c.form.field
import zope.interface

from Products.statusmessages.interfaces import IStatusMessage
from Products.CMFDefault.exceptions import EmailAddressInvalid

from nuw.types.EmailUpdateTool.EmailUpdateTool import send_confirmation_email
from nuw.types.member import EmailExists
from nuw.types.role import get_person_agencies, get_person_employers, get_person_worksites
from nuw.types.role import get_person_reps, is_person_delegate, is_person_hsr, is_person_labourhire
from nuw.types.role import get_person_nuw_member_number, get_person_nuw_assist_number
from nuw.types.role import get_person_nuw_activity_level, get_person_nuw_member_type, get_person_nuw_member_status

Session = named_scoped_session( 'nuw.types' )
_ = MessageFactory('nuw.types')
grok.templatedir( 'templates' )


class ContactDetails( grok.View ):
    grok.context( IFolder )
    grok.name( 'contact-details' )

    def update( self ):
        self.user = get_or_kick_user( self.context, self.request )
        self.person = self.user.person

    def birth_date( self ):
        if self.person.dob != None and self.person.dob != '':
            return self.person.dob.strftime("%d %B %Y")

    def get_dummy_pass( self ):
        return ''.join("*" for i in range(0, len(self.user.password)))

    def get_member_number( self ):
        return get_person_nuw_member_number(self.person.personid)

    def get_member_assist_number( self ):
        return get_person_nuw_assist_number(self.person.personid)

    def get_agencies( self ):
        return get_person_agencies(self.person.personid)

    def get_employers( self ):
        return get_person_employers(self.person.personid)

    def get_worksites( self ):
        return get_person_worksites(self.person.personid)

    def get_worksite_reps( self ):
        reps = get_person_reps(self.person.personid)
        if len(reps):
            if reps[0].get('reps'):
                return reps

    def activity_type( self ):
        return get_person_nuw_activity_level(self.person.personid)

    def member_type( self ):
        return get_person_nuw_member_type(self.person.personid)

    def member_status( self ):
        return get_person_nuw_member_status(self.person.personid)

    def is_delegate( self ):
        if is_person_delegate(self.person.personid):
            return 'Yes'

    def is_hsr( self ):
        if is_person_hsr(self.person.personid):
            return 'Yes'


class PersonalDetailsForm( form.EditForm ):
    grok.context( IFolder )
    grok.name( 'personal-details-form' )

    enabled = ["preferredname", "firstname", "lastname", "title", "gender", "dob", "mobile", "home",
               "work", "languagemain", "languagetranslator", "languageneed", "postaddress1", "postaddress2", "postsuburb", "poststate", "postpcode",
               "homeaddress1", "homeaddress2", "homesuburb", "homestate", "homepostcode"]
    fields = z3c.form.field.Fields(IPerson).select(*enabled)

    def getContent( self ):
        # Get users details
        user = get_or_kick_user( self.context, self.request )
        person = user.person

        return person

    def applyChanges( self, data ):
        user = get_or_kick_user( self.context, self.request )
        person = user.person

        for key in self.enabled:
            setattr(person, key, data[key])

        # notify the API
        zope.event.notify(
            ObjectModifiedEvent(person))

    @button.buttonAndHandler(_('Save'), name=None)
    def handleSave(self, action):
        data, errors = self.extractData()

        user = get_or_kick_user( self.context, self.request )
        person = user.person

        if errors:
            self.status = self.formErrorsMessage
            return

        if data.get('email') != person.email and data.get('email'):
            try:
                send_confirmation_email(self.context, data.get('email'), user.name, person)
            except EmailAddressInvalid:
                self.status = u"Invalid email address!"
                return
            except EmailExists as e:
                self.status = e.__doc__
                return

            IStatusMessage(self.request).addStatusMessage(u"A verification email has been sent to your new address", "info")
            self.request.response.redirect("@@contact-details")
            return

        if 'email' in self.enabled and not data.get('email'):
            self.status = u"Cannot have an empty email!"
            return

        if data.has_key('new_password') and data.has_key('new_password_confirm'):
            if data['new_password'] != data['new_password_confirm']:
                self.status = u"Please make sure that both passwords are the same"
                return
            if data['new_password'] is None or data['new_password'] == '':
                self.status = u"Cannot have an empty password!"
                return

        self.applyChanges(data)
        IStatusMessage(self.request).addStatusMessage(u"Changes saved", "info")
        self.request.response.redirect("@@contact-details")

    @button.buttonAndHandler(_('Cancel'), name='cancel')
    def handleCancel(self, action):
        self.status = u"Edit cancelled"
        self.request.response.redirect("@@contact-details")


class EmailDetailsForm( PersonalDetailsForm ):
    grok.name( 'email-details-form' )

    enabled = ("email",)
    fields = z3c.form.field.Fields(IPerson).select(*enabled)

    def applyChanges( self, data ):
        return


class IUser( form.Schema ):
    name = zope.schema.TextLine(
        title=u'Username',
        required=False,
    )

    new_password = zope.schema.Password(
        title=u'New Password',
        required=False,
    )

    new_password_confirm = zope.schema.Password(
        title=u'Confirm New Password',
        required=False,
    )


class PasswordInputForm( PersonalDetailsForm ):
    grok.name( 'pass-input-form' )
    enabled = ("new_password", "new_password_confirm",)

    fields = z3c.form.field.Fields(IUser).select(*enabled)

    def getContent( self ):
        class TempUser( object ):
            zope.interface.implements( IUser )

        user = get_or_kick_user( self.context, self.request )
        obj = TempUser()
        return obj

    def applyChanges( self, data ):
        user = get_or_kick_user( self.context, self.request )
        if data['new_password'] == data['new_password_confirm']:
            user.password = data['new_password']

        # notify the API
        zope.event.notify(
            ObjectModifiedEvent(user))
