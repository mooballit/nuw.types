# Copyright (c) 2012 Mooball IT
# See also LICENSE.txt
"""
The join process is divided into two steps:

    #. collecting personal information
    #. confirming information and,
    #. collecting payment information.

"""
from Acquisition import aq_inner, aq_base
from Products.statusmessages.interfaces import IStatusMessage
from collective.z3cform.wizard import wizard
from five import grok
from nuw.types.base import IContactDetails
from nuw.types.base import INUWItem
from nuw.types.group import Group
from nuw.types.group import agency_source_binder
from nuw.types.group import worksites_source_binder
from nuw.types.group import is_group_market_research
from nuw.types.grouprole import GroupRole
from nuw.types.interfaces import IJoinContext
from nuw.types.member import Person, email_exists, EmailExists
from nuw.types.admin_area.admin_views import get_join_admin_email, \
                                            get_fees_admin_email
from Products.CMFDefault.exceptions import EmailAddressInvalid
from nuw.types.admin_area.interfaces import IRecurringSettings
from nuw.types import recurpayment
from nuw.types.authentication import get_user_worksite
from plone.formwidget.autocomplete import AutocompleteFieldWidget
from plone.z3cform import layout
from plone.z3cform.fieldsets import group
from plone.z3cform.fieldsets.utils import move
from plone.z3cform.traversal import FormWidgetTraversal
from Products.CMFCore.utils import getToolByName
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from plone.registry.interfaces import IRegistry
from zope.component import queryUtility
from zope.interface import Invalid, invariant
from z3c.form import interfaces
from z3c.form.error import InvalidErrorViewSnippet
from z3c.form.browser.radio import RadioFieldWidget
from z3c.saconfig import named_scoped_session
from z3c.form.interfaces import ActionExecutionError, WidgetActionExecutionError
from zope.lifecycleevent import ObjectAddedEvent, ObjectModifiedEvent
from zope.publisher.interfaces.browser import IBrowserRequest
from zope.traversing.interfaces import TraversalError
from sqlalchemy import text, bindparam
from z3c.form.interfaces import INPUT_MODE, HIDDEN_MODE
import Products.CMFDefault.utils
import datetime
import nuw.types.spreedly.spreedly
import spreedlycore
import z3c.form.button
import uuid
import z3c.form.field
import zope.schema
import transaction
import json
import logging
from pprint import pprint

logger = logging.getLogger(__name__)
Session = named_scoped_session('nuw.types')
OMIT_FIELDS = ['employmenttype',
               'other_worksite',
               'other_agency',
               'worksite',
               'agency_name',
               'worksite_id',
               'agency',
               'disclosure',
              ]

display_fields = ['employmenttype',
       'worksite',
       'other_worksite',
       'agency_name',
       'other_agency',
      ]
PAYMENT_FREQUENCIES = dict(weekly=u'Weekly Payment',
                           monthly=u'Monthly Payment',
                          )
PAYMENT_MAPPING = dict(weekly=40,
                       monthly=50,
                      )



def validEmail(value):
    Products.CMFDefault.utils.checkEmailAddress(value)
    if email_exists( value ):
        raise EmailExists

    return True


class PhoneNumberInvalid(zope.schema.ValidationError):
    __doc__ = 'Phone number must be 10 digits.'

    def __str__(self):
        return self.__doc__

def validatePhoneNumber(value):
    if value and len(value) != 10:
        raise PhoneNumberInvalid

    return True

class PostcodeInvalid(zope.schema.ValidationError):
    __doc__ = 'Postcode must be 4 digits.'

    def __str__(self):
        return self.__doc__

def validatePostcode(value):
    if value and len(value) != 4:
        raise PostcodeInvalid

    return True

class InvalidDoB(zope.schema.ValidationError):
    __doc__ = 'Year must be 4 digits.'

    def __str__(self):
        return self.__doc__

def validateDateTime(value):
    if value and len(str(value.year)) != 4:
        raise InvalidDoB

    return True


class ISignupPerson(zope.interface.Interface):

    firstname = zope.schema.TextLine(
        title=u'First Name',
    )

    lastname = zope.schema.TextLine(
        title=u'Last Name',
    )

    # also defined in member.py
    gender = zope.schema.Choice(
        title=u'Gender',
        values=[u'Male', u'Female', u'Unknown'],
    )

    dob = zope.schema.Date(
        title=u'Date of Birth',
        description=u'Please enter your date of birth.',
        constraint=validateDateTime,
    )

    homeaddress1 = zope.schema.TextLine(
        title=u'Unit/Street No',
    )

    homeaddress2 = zope.schema.TextLine(
        title=u'Street Address',
    )

    homesuburb = zope.schema.TextLine(
        title=u'Suburb',
    )

    homestate = zope.schema.Choice(
        title=u'State',
        values=[u'QLD',
                u'VIC',
                u'TAS',
                u'NSW',
                u'SA',
                u'WA',
                u'ACT',
                u'NT',
               ]
    )

    homepostcode = zope.schema.TextLine(
        title=u'Postcode',
        constraint=validatePostcode,
    )

    email = zope.schema.TextLine(
        title=u'E-mail',
        description=u'This address will become your Site Login',
        constraint=validEmail,
    )

    home = zope.schema.TextLine(
        title=u'Home Number',
        description=u'Please provide your primary phone number.',
        constraint=validatePhoneNumber,
        required=False
    )

    mobile = zope.schema.TextLine(
        title=u'Mobile Number',
        required=False,
    )

    employmenttype = zope.schema.Choice(
        title=u'Employment Type',
        description=u'Please choose an employment type.',
        vocabulary='employment',
    )

    worksite = zope.schema.TextLine(
        title=u'Worksite',
        description=(u'Specify the worksite by typing in the first'
                     ' letters. A choice of worksites is given to you from'
                     ' which you can choose from.'),
        required=False,
        )

    worksite_id = zope.schema.TextLine(
        title=u'Worksite ID',
        description=(u'Specify the worksite by typing in the first'
                     ' letters. A choice of worksites is given to you from'
                     ' which you can choose from.'),
        required=False,
    )

    # Inconsistent naming scheme, totally not my fault, too many references to change :)
    agency_name = zope.schema.TextLine(
        title=u'Agency',
        description=u'Labour hire agency (if applicable)',
        required=False,
    )

    agency = zope.schema.TextLine(
        title=u'Agency ID',
        description=u'Labour hire agency (if applicable)',
        required=False,
    )

    disclosure = zope.schema.Bool(
        title=u'I have read the terms notice.',
        description=u'',
        required=False
    )

    other_worksite = zope.schema.TextLine(
        title=u"I can't find my worksite",
        description=u'',
        required=False
    )

    other_agency = zope.schema.TextLine(
        title=u"I can't find my agency",
        description=u'',
        required=False
    )



class BasePersonalInfoGroup(group.Group):
    label = u'Personal Information'
    prefix = 'personalinfo'

    def update(self):
        lastfield = 'homepostcode'
        self.request.set('disable_plone.leftcolumn', 1)
        self.request.set('disable_plone.rightcolumn', 1)
        self.request.set('disable_border', 1)
        rendered = self.fields.keys()
        for fid, field in zope.schema.getFieldsInOrder(IContactDetails):
            if fid not in rendered:
                continue
            move(self, fid, after=lastfield)
            lastfield = fid
        super(BasePersonalInfoGroup, self).update()


class PersonalInformationGroup(BasePersonalInfoGroup):
    fields = z3c.form.field.Fields(
        ISignupPerson).omit(*OMIT_FIELDS)


class BaseDisplayGroup(group.Group):
    mode = z3c.form.interfaces.DISPLAY_MODE

    def updateWidgets(self):
        super(BaseDisplayGroup, self).updateWidgets()
        self.widgets.mode = self.mode
        self.widgets.update()

    def getContent(self):
        form = self.parentForm
        wizard = form.wizard
        return wizard.activeSteps[0].getContent()


class ConfirmPersonalInformation(BaseDisplayGroup):
    fields = z3c.form.field.Fields(ISignupPerson).omit(*OMIT_FIELDS)
    label = u'Personal Information'
    prefix = 'personalinfo'


class ConfirmWorkInformation(BaseDisplayGroup):
    fields = z3c.form.field.Fields(ISignupPerson).select(*display_fields)
    label = u'Worksite Information'
    prefix = 'workinformation'

    def update(self):
        self.request.set('disable_plone.leftcolumn', 1)
        self.request.set('disable_plone.rightcolumn', 1)
        self.request.set('disable_border', 1)
        # Hide agency field if 'agency' isn't an employmenttype
        data = self.getContent()
        if isinstance(data, dict):
            if (data.get('agency', None) == None or \
                    data.get('agency', None) == interfaces.NOVALUE) and \
                    data.get('employmenttype', None) == 'agency':
                work_agency = 'worksite'
                if data.get('worksite_id', None) == None or data.get('worksite_id', None) == interfaces.NOVALUE:
                    self.fields = z3c.form.field.Fields(
                            ISignupPerson).select(*display_fields)
                    work_agency = 'worksite or agency'
                else:
                    self.fields = z3c.form.field.Fields(
                            ISignupPerson).select(*display_fields)
                IStatusMessage(self.request).addStatusMessage(
                    u'You have not selected a %s. A representative will be in contact with you as soon as possible when you confirm your details.' % work_agency,
                    'info')
            elif (data.get('worksite_id', None) == None or \
                    data.get('worksite_id', None) == interfaces.NOVALUE):
                self.fields = z3c.form.field.Fields(
                        ISignupPerson).select(*display_fields)
                IStatusMessage(self.request).addStatusMessage(
                    u'You have not selected a worksite. A representative will be in contact with you as soon as possible when you confirm your details.',
                    'info')
            elif data.get('employmenttype', None) != 'agency':
                self.fields = z3c.form.field.Fields(
                        ISignupPerson).select(*display_fields)
        super(ConfirmWorkInformation, self).update()


class WorkInformationGroup(group.Group):
    fields = z3c.form.field.Fields(ISignupPerson).select(
        'employmenttype', 'worksite_id', 'worksite', 'other_worksite', 'agency_name', 'agency', 'other_agency', 'disclosure', )
    # fields['worksite_id'].widgetFactory = AutocompleteFieldWidget
    # fields['agency'].widgetFactory = AutocompleteFieldWidget
    # fields['employmenttype'].widgetFactory = SelectFieldWidget
    label = u'Worksite Information'
    prefix = 'workinformation'

    def js_extra(self):
        # Javascript to hide agency field only when agency type isn't checked
        return """
                $(function() {
                    var employmenttype_agency_checked = $( '#formfield-workinformation-widgets-employmenttype select' ).val() == 'agency';
                    if ( !employmenttype_agency_checked ) {
                        $( "#formfield-workinformation-widgets-agency_name" ).hide();
                        $( "#formfield-workinformation-widgets-other_agency" ).hide();
                    } else {
                        $( "#formfield-workinformation-widgets-agency_name" ).show();
                        $( "#formfield-workinformation-widgets-other_agency" ).show();
                    }

                    $('#workinformation-widgets-other_worksite').attr('placeholder', 'Enter worksite name');
                    $('#workinformation-widgets-other_agency').attr('placeholder', 'Enter agency name');

                     /* Hacky way to force form wide validation */
                    var $continue = $('#form-buttons-continue');
                    var $home = $('#personalinfo-widgets-home');
                    var $mobile = $('#personalinfo-widgets-mobile');

                    var required = ["firstname", "lastname", "homeaddress1", "homeaddress2", "homesuburb", "email"];
                    $continue.click(function(ev) {
                        var error = false;
                        $('.fieldErrorBox').empty();
                        $('.error').removeClass('error');

                        $.each(required, function(idx, val) {
                            var $widget = $("#personalinfo-widgets-" + val);
                            if($widget.val() == '') {
                                error = true;
                                $("#formfield-personalinfo-widgets-" + val).addClass('error');
                                $("#formfield-personalinfo-widgets-" + val + " label").after('<div class="fieldErrorBox"><div class="error">Required input is missing.</div></div>');
                            }
                        });

                        if(($("#personalinfo-widgets-dob-day").val() == '') || ($("#personalinfo-widgets-dob-year").val() == '')) {
                            error = true;
                            $("#formfield-personalinfo-widgets-dob").addClass('error');
                            $("#formfield-personalinfo-widgets-dob label").after('<div class="fieldErrorBox"><div class="error">Required input is missing.</div></div>');
                        } else if($("#personalinfo-widgets-dob-year").val().length != 4) {
                            error = true;
                            $("#formfield-personalinfo-widgets-dob").addClass('error');
                            $("#formfield-personalinfo-widgets-dob label").after('<div class="fieldErrorBox"><div class="error">Year must be 4 digits.</div></div>');
                        }
                        if($("#personalinfo-widgets-homepostcode").val() == '') {
                            error = true;
                            $("#formfield-personalinfo-widgets-homepostcode").addClass('error');
                            $("#formfield-personalinfo-widgets-homepostcode label").after('<div class="fieldErrorBox"><div class="error">Required input is missing.</div></div>');
                        } else if($("#personalinfo-widgets-homepostcode").val().length != 4) {
                            error = true;
                            $("#formfield-personalinfo-widgets-homepostcode").addClass('error');
                            $("#formfield-personalinfo-widgets-homepostcode label").after('<div class="fieldErrorBox"><div class="error">Postcode must be 4 digits.</div></div>');
                        }
                        if(!$("#workinformation-widgets-disclosure-0").is(":checked")) {
                            error = true;
                            $("#formfield-workinformation-widgets-disclosure").addClass('error');
                            $("#formfield-workinformation-widgets-disclosure span label").after('<div class="fieldErrorBox"><div class="error">Required to confirm you have read before continuing.</div></div>');
                        }
                        if (($home.val() == '' && $mobile.val() == '')) {
                            error = true;
                            $('#formfield-personalinfo-widgets-mobile').addClass('error');
                            $('#formfield-personalinfo-widgets-home').addClass('error');
                            $('#formfield-personalinfo-widgets-mobile label').after('<div class="fieldErrorBox"><div class="error">Home or mobile number required. <br/>Please enter at least one.</div></div>');
                            $('#formfield-personalinfo-widgets-home label').after('<div class="fieldErrorBox"><div class="error">Home or mobile number required. <br/>Please enter at least one.</div></div>');
                        } else {
                            if ($home.val() != '' && $home.val().length != 10) {
                                error = true;
                                $('#formfield-personalinfo-widgets-home').addClass('error');
                                $('#formfield-personalinfo-widgets-home label').after('<div class="fieldErrorBox"><div class="error">Home number must be 10 digits.</div></div>');
                            }
                            if ($mobile.val() != '' && $mobile.val().length != 10) {
                                error = true;
                                $('#formfield-personalinfo-widgets-mobile').addClass('error');
                                $('#formfield-personalinfo-widgets-mobile label').after('<div class="fieldErrorBox"><div class="error">Mobile number must be 10 digits.</div></div>');
                            }
                        }
                        if($("#personalinfo-widgets-email").val() != '' && !error) {
                            $.post("@@validateEmail", {email: $("#personalinfo-widgets-email").val()}).done(function(data){
                                if(!data.success) {
                                    error = true;
                                    $("#formfield-personalinfo-widgets-email").addClass('error');
                                    $("#formfield-personalinfo-widgets-email label").after('<div class="fieldErrorBox"><div class="error">' + data.message + '</div></div>');
                                } else {
                                    $('#collectdetails').submit();
                                }
                            });
                        }
                        if (error) {
                            return false;
                        }
                    });

                    $('#formfield-workinformation-widgets-disclosure span.option').before('<a target="_blank" href="/terms/terms-notice">Click here</a> to read terms notice.');
                });
                """

    def updateWidgets(self):
        super(WorkInformationGroup, self).updateWidgets()
        self.fields['agency'].mode = HIDDEN_MODE
        agency_template = ViewPageTemplateFile('join_templates/agencyautocombobox.pt')
        self.widgets['employmenttype'].onchange = u'if( $(this).val() == "agency" ) { $( "#formfield-workinformation-widgets-agency_name:hidden" ).slideDown("fast"); $( "#formfield-workinformation-widgets-other_agency:hidden" ).slideDown("fast");  } else { $( "#formfield-workinformation-widgets-agency_name:visible" ).slideUp("fast"); $( "#formfield-workinformation-widgets-other_agency:visible" ).slideUp("fast"); $("#workinformation-widgets-agency-novalue").click(); }'

        self.widgets['agency_name'].template = agency_template

        self.fields['worksite_id'].mode = HIDDEN_MODE
        worksite_template = ViewPageTemplateFile('join_templates/worksiteautocombobox.pt')
        self.widgets['worksite'].template = worksite_template
        self.widgets['worksite'].extra_js = self.js_extra

        # self.widgets['worksite_id'].onchange = u'if(this.checked) { $("#formfield-workinformation-widgets-other_worksite").slideDown("fast"); } else { $("#formfield-workinformation-widgets-other_worksite").slideUp("fast"); }'
        # self.widgets['worksite_id'].js_extra = self.js_worksite_toggle

class CollectDetailsForm(wizard.GroupStep):
    """ A step in the @@joinwizard.html wizard.

    This collects all personal and work related information from the user.
    """
    label = u'Personal Information'
    prefix = 'collectdetails'
    description = """Provide your information to apply to NUW. Your email
                will be used as your site login (this is case sensitive).
                An email will be sent to this address to activate your login
                and update your password."""
    groups = [PersonalInformationGroup, WorkInformationGroup]

    # For use in oil industry hack.
    without_worksite_tpl = ViewPageTemplateFile( 'join_templates/joindetailsconfirm_noworksite.pt' )
    oil_email_tpl = ViewPageTemplateFile( 'join_templates/oiljoinemail.pt' )
    general_email_tpl = ViewPageTemplateFile( 'join_templates/joindetailsconfirm.pt' )

    def apply(self, context):
        session = Session()
        data = self.getContent()
        personid = str(uuid.uuid4())
        person_factory = zope.component.getUtility(
            zope.component.interfaces.IFactory, 'person')

        # Set some default values (some will change after successful payment)
        data[ 'webstatus' ] = 'unfinancial-member'
        data[ 'status' ] = 'Awaiting 1st payment'
        data[ 'type' ] = 'Member'
        data[ 'activity' ] = 'supportive'

        person = person_factory(personid, **data)
        session.add(person)
        transaction.commit()

        # notify the API
        zope.event.notify(
            ObjectAddedEvent(person, self, person.id))

        is_oil = None
        in_worksite = data.get('worksite_id', None)
        in_agency = data.get('agency', None)
        if in_worksite or (data.get('employmenttype', None) == 'agency' and in_agency and in_worksite):
            self.set_roles(person)
            # Hack to redirect people in Oil Industry
            is_oil = session.query( GroupRole ).filter( GroupRole.groupid == data['worksite_id'], GroupRole.supergroupid == '0E2FC41E-BDF2-E011-90F7-005056A20027' ).count() > 0

        if not in_worksite:
            self.set_roles(person, nonworksite=True)

        # Notify correct people when hack has been executed
        mhost = getToolByName(self, 'MailHost')
        if is_oil:
            for email in [ 'tom@mooball.net', get_join_admin_email() ]:
                mail_content = self.oil_email_tpl(
                    to_email = email, name = data['firstname'] + ' ' + data['lastname'],
                    email = data['email'], phone = data['home'], mobile = data['mobile'],
                    worksitename = self.worksitename,
                    personid = personid, portal_url = self.context.portal_url,
                )
                mhost.send( mail_content )
        if not in_worksite or (data.get('employmenttype', None) == 'agency' and not in_agency):
            email = get_join_admin_email()
            mail_content = self.without_worksite_tpl(
                to_email = email, name = data['firstname'] + ' ' + data['lastname'],
                email = data['email'], phone = data['home'], mobile = data['mobile'],
                personid = personid, portal_url = self.context.portal_url,
                employmenttype = data.get('employmenttype', None),
                other_worksite = data.get('other_worksite', None),
                other_agency = data.get('other_agency', None),
            )
            mhost.send( mail_content )
        else:
            email = get_join_admin_email()
            mail_content = self.general_email_tpl(
                to_email = email, name = data['firstname'] + ' ' + data['lastname'],
                email = data['email'], phone = data['home'], mobile = data['mobile'],
                personid = personid, portal_url = self.context.portal_url,
            )
            mhost.send( mail_content )

        view = zope.component.getMultiAdapter(
            (self.context, self.request), name = ( (not in_worksite or (data.get('employmenttype', None) == 'agency' and not in_agency) or is_oil) and 'join_thankyou.html' or 'join_payment.html' ) )
        url = zope.component.getMultiAdapter(
            (view, self.request), name='absolute_url')()
        self.request.response.redirect(
            ''.join([url, '?nuw.types.uuid={}'.format(person.personid), '&nuw.types.mr={}'.format(1 if is_group_market_research(in_worksite, hubid=True) else 0)])
            )

    def set_roles(self, person, nonworksite=False):
        session = Session()
        data = self.getContent()
        is_hired = data.get('agency') is not None
        role_factory = zope.component.getUtility(
            zope.component.interfaces.IFactory, 'role')
        if not nonworksite:
            worksite = session.query(
                Group).filter_by(hubid=data['worksite_id']).one()
        elif nonworksite:
            worksite = session.query(Group).filter_by(hubid="836FEBC5-EE00-E111-A628-005056A20027").one()

        self.worksitename = None
        if worksite:
            self.worksitename = worksite.name
        roles = [(u'Employee', worksite)]

        if is_hired:
            agency = session.query(
                Group).filter_by(hubid=data['agency']).one()
            roles = [(u'Labour Hire', worksite),
                     (u'Employee', agency)]

        for roletype, groupobj in roles:
            role = role_factory(roleid=str(uuid.uuid4()),
                                role=roletype,
                                groupid=INUWItem(groupobj).hubid,
                                personid=INUWItem(person).hubid,
                                startdate=datetime.datetime.today(),
                               )
            session.add(role)
            transaction.commit()

            # notify the API
            zope.event.notify(
                ObjectAddedEvent(role, self, role.id))


class ConfirmDetailsForm(wizard.GroupStep):
    """ A step in the join process.

    This step confirms the entered personal details and collects payment
    information.
    """
    label = u'Confirmation'
    prefix = 'confirmdetails'
    description = """Please confirm your application details
                    below and if they are not correct, you can use the back
                    button to modify them. Once confirmed, you will be passed
                    on to the payment."""
    groups = [ConfirmPersonalInformation, ConfirmWorkInformation]

    def apply(self, context):
        pass


class JoinFormWizard(wizard.Wizard):
    label = u'Join NUW'
    description = (u'Become an NUW member now and gain access to this'
        ' site and other NUW services.')
    steps = CollectDetailsForm, ConfirmDetailsForm

    # since we can not simply un-button the form and remove the 'clear'
    # button, we'll add any other button and delegate
    @z3c.form.button.buttonAndHandler(
        u'< Back', name='back',
        condition=lambda form: not form.onFirstStep)
    def handleBack(self, action):
        return super(JoinFormWizard, self).handleBack(self, action)

    @z3c.form.button.buttonAndHandler(u'Cancel')
    def cancel(self, action):
        portal_state = zope.component.getMultiAdapter(
            (self.context, self.request), name='plone_portal_state')
        self.request.response.redirect(
            portal_state.portal_url())

    # a.k.a. finish
    @z3c.form.button.buttonAndHandler(
        u'Continue >', name='continue_to_payment',
        condition=lambda form: form.allStepsFinished and form.onLastStep)
    def handleFinish(self, action):
        return super(JoinFormWizard, self).handleFinish(self, action)

    @z3c.form.button.buttonAndHandler(
        u'Continue >', name='continue',
        condition=lambda form: not form.onLastStep)
    def handleContinue(self, action):
        # TODO: self.extractData() fails here,
        # can't find any other way, so wooo for hacky JS validation
        # pprint(self.steps)
        # data = self.steps[0].getContent()
        # pprint(data)

        # if 'home' in data and 'mobile' in data:
        #     if len(data['home']) == 0 or len(data['mobile']) == 0:
        #         raise ActionExecutionError(Invalid('Home or mobile phone number is required. Please fill in at least one.'))

        return super(JoinFormWizard, self).handleContinue(self, action)


JoinFormWizardView = layout.wrap_form(JoinFormWizard)


class AutoWizardWidgetTraversal(FormWidgetTraversal):
    """Allow traversal to widgets via the ++widget++ namespace.
    """
    zope.component.adapts(JoinFormWizardView, IBrowserRequest)

    def _prepareForm(self):
        form = self.context.form_instance
        form.update()
        for step in form.activeSteps:
            step.update()
        return form

    def traverse(self, name, ignored):
        # XXX Better would be to have the steps traversable, instead of
        # the form. This means potentially, that also widgets need to be
        # changed. Because we're adapting JoinFormWizardView, the
        # traverse method is specific to the wizard and will obviously
        # not work on any other context.
        parts = name.split('.')
        form = aq_base(self._prepareForm())
        widget = None
        if parts:
            name = parts.pop()
            widget = self._form_traverse(form, name)
        if not widget:
            raise TraversalError(name)
        widget.__parent__ = aq_inner(self.context)
        return widget

    def _form_traverse(self, form, name):
        widget = None
        if form.widgets is not None and name in form.widgets:
            return form.widgets.get(name)
        # If there are no groups, give up now
        if getattr(form, 'groups', None) is not None:
            for group in form.groups:
                if group.widgets and name in group.widgets:
                    widget = group.widgets.get(name)
                    break
        elif getattr(form, 'activeSteps', None) is not None:
            for step in form.activeSteps:
                widget = self._form_traverse(step, name)
                if widget is not None:
                    break
        return widget


class PaymentForm(grok.View):
    grok.name('join_payment.html')
    grok.require('zope2.View')
    grok.context(IJoinContext)

    connection = None
    errors = dict()

    payment_email_tpl = ViewPageTemplateFile( 'join_templates/joinpaymentconfirm.pt' )

    def get_errors(self, pay_method):
        # Why this? Because the errors item in the PaymentMethod can be
        # either a dict (single error), a str (no error) or a list of
        # dicts (multiple errors). Excellent integration!
        assert getattr(pay_method, 'data', None) is not None
        assert isinstance(pay_method.data, dict)

        errors = pay_method.data.get('errors')
        if not errors:
            return []
        if isinstance(errors['error'], dict):
            return [errors['error']]
        elif isinstance(errors['error'], list):
            return errors['error']

    def update(self):
        self.errors = dict()
        self.request.set('disable_plone.leftcolumn', 1)
        self.request.set('disable_plone.rightcolumn', 1)
        self.request.set('disable_border', 1)
        try:
            self.connection = nuw.types.spreedly.spreedly.get_connection()
        except Warning, e:
            IStatusMessage(self.request).addStatusMessage(unicode(e), "error")

        token = self.request.form.get('token')
        if token is not None:
            pay_method = spreedlycore.PaymentMethod(self.connection, token)
            pay_method.load()
            errors = self.get_errors(pay_method)
            if errors:
                for error in errors:
                    self.errors[error['attribute']] = error['text']
                return

            if token and 'frequency' in pay_method.data['data']:
                # now we cobble together the rest to make a payment m)
                frequency = pay_method.data['data'].get('frequency')
                return self.payify(token, frequency)

    def payify(self, token, frequency):
        person = self.get_person()
        amount = self.get_payment_amount(frequency)

        if recurpayment.check_existing_recurring_payment(person):
            IStatusMessage(self.request).addStatusMessage(
                u'Your NUW membership application has been completed and your' +
                u' payment method has been accepted. Please check your email (%s) to complete the setup of your login to this website'  % person.email,
                'info')
            self.request.response.redirect(self.url('join_thankyou.html'))
            return

        gateway, db_gateway = self.get_payment_gateways(token)
        pay_method, db_pay_method = self.get_payment_methods(person, token)
        try:
            transaction = nuw.types.spreedly.spreedly.charge(
                pm=pay_method, db_method_id=db_pay_method.id,
                pg=gateway, db_gateway_id=db_gateway.id,
                person_id=person.id, amount=amount,
                component='Membership Fees')
        except spreedlycore.APIRequest.RequestFailed, e:
            for error in e.errors:
                # TODO: :( will overwrite if we have more than one error
                self.errors['transaction'] = (
                    'Unable to charge against the provided credit card.'
                    ' Error message was: {error}'.format(error=error['text'])
                )
            return

        # Successful payment has been made, update person to financial member
        sess = Session()

        person.webstatus = person.webstatus.replace( 'unfinancial-member', 'financial-member' )
        person.status = 'paying'

        sess.add( person )
        transaction.capture()

        zope.event.notify( ObjectModifiedEvent( person ) )

        recurpayment.add_recurring_payment(person, frequency, amount)

        mhost = getToolByName(self, 'MailHost')
        email = get_join_admin_email()
        mail_content = self.payment_email_tpl(
            to_email = email, name = person.firstname + ' ' + person.lastname,
            email = person.email, phone = person.home, mobile = person.mobile,
            frequency = frequency, amount = amount,
            personid = person.personid, portal_url = self.context.portal_url,
        )
        mhost.send( mail_content )

        self.request.response.redirect(self.url(person.personid+'/verifyemail.html'))

    def get_payment_methods(self, person, token):
        """ Same shit with the gateways :(
        """
        # this one sets the database payment method, but returns the
        # spreedly core payment method
        pay_method = nuw.types.spreedly.spreedly.set_user_payment_method(
            self.connection, token, person.personid, True, True)

        # aah the db payment method. Finally.
        db_pay_method = nuw.types.spreedly.spreedly.db_get_payment_method(
            token)
        # hang on.. don't you want to check if the database returns an
        # object? Perhaps I should, but why the heck do I set one then
        # before?
        assert pay_method is not None
        assert db_pay_method is not None
        return (pay_method, db_pay_method)

    def get_payment_gateways(self, token):
        """ Returns a tuple with payment gateways.

        Because if this confusing implementation of a
        (spreedly-core-python) PaymentGateway, and the existance of a
        PaymentGateway in the database, we'll wrap the retrieval of both
        in this method. Aaah... and btw I almost forgot to tell you: if
        there is no PaymentGateway, we create one... in the database.

        :rtype: tuple - (spreedlycore-python PaymentGateway, SQLAlchemy
                         PaymentGateway)
        """
        db_gateway = nuw.types.spreedly.spreedly.db_get_gateway(token)
        gateway = nuw.types.spreedly.spreedly.get_default_gateway(
            self.connection)
        if db_gateway is None:
            nuw.types.spreedly.spreedly.db_add_gateway(gateway)
            db_gateway = nuw.types.spreedly.spreedly.db_get_gateway(
                gateway.token)

        assert gateway is not None
        assert db_gateway is not None

        return (gateway, db_gateway)

    def get_payment_frequencies(self):
        registry = queryUtility(IRegistry)
        settings = registry.forInterface(IRecurringSettings)

        frequencies = []

        if int(self.request.form.get('nuw.types.mr', 0)):
            if settings.recur_week_market_research:
                frequencies.append(
                        ('recur_week_market_research', str(settings.recur_week_market_research)+"-week",
                        'Weekly')
                        )

            if settings.recur_month_market_research:
                frequencies.append(
                        ('recur_month_market_research', str(settings.recur_month_market_research)+"-month",
                        'Monthly')
                        )

            if settings.recur_quarter_market_research:
                frequencies.append(
                        ('recur_quarter_market_research', str(settings.recur_quarter_market_research)+"-quarter",
                        'Quarterly')
                        )

            if settings.recur_year_market_research:
                frequencies.append(
                        ('recur_year_market_research', str(settings.recur_year_market_research)+"-year",
                        'Yearly')
                        )

        else:
            if settings.recur_week:
                frequencies.append(
                        ('recur_week', str(settings.recur_week)+"-week",
                        'Weekly')
                        )

            if settings.recur_month:
                frequencies.append(
                        ('recur_month', str(settings.recur_month)+"-month",
                        'Monthly')
                        )

            if settings.recur_quarter:
                frequencies.append(
                        ('recur_quarter', str(settings.recur_quarter)+"-quarter",
                        'Quarterly')
                        )

            if settings.recur_year:
                frequencies.append(
                        ('recur_year', str(settings.recur_year)+"-year",
                        'Yearly')
                        )

        return frequencies

    def get_payment_amount(self, frequency, market_research=False):
        # TODO: What do we do if that fails (e.g. it has been tampered
        # with)
        registry = queryUtility(IRegistry)
        settings = registry.forInterface(IRecurringSettings)
        return getattr(settings, frequency)

    def api_login(self):
        assert self.connection is not None
        return self.connection.login

    def get_person(self):
        uuid = self.request.form.get('nuw.types.uuid')
        person = None
        if uuid is not None:
            session = Session()
            person = session.query(Person).filter_by(hubid=uuid).first()
        return person

    def get_personal_info(self):
        fields = dict(email='email', address1='homeaddress1',
                      address2='homeaddress2', city='homesuburb',
                      state='homestate', zip='homepostcode',
                      phone_number='home', first_name='firstname',
                      last_name='lastname')
        result = []
        context = self.get_person()
        for key, fid in fields.items():
            info = dict(name='credit_card[{key}]'.format(key=key),
                        value=getattr(context, fid),
                       )
            result.append(info)
        return result

    def valid_years(self):
        now = datetime.date.today()
        return range(now.year, now.year + 10)


class JoinThankYou(grok.View):
    grok.name('join_thankyou.html')
    grok.require('zope2.View')
    grok.context(IJoinContext)

# class DisclosureRedirect(grok.View):
#     grok.name('read-disclosures')
#     grok.require('zope2.View')
#     grok.context(IJoinContext)

#     def update(self):
#         self.request.response.redirect()

class AjaxWorksiteSource(grok.View):
    """ Returns JSON of filtered or most popular worksites
    """
    grok.name('worksites.json')
    grok.require('zope2.View')
    grok.context(IJoinContext)

    def render(self):
        form = self.request.form
        response = self.request.response
        response.setHeader("Content-type", "application/json")
        sess = Session()
        pprint(form)
        filter_token = form.get('token')
        name_filter = form.get('query')

        if filter_token == 'agency':
            query = text("""
                        with first_group_for_each_parent as (
                            SELECT min(g.nuwassistid) nuwassistid,
                                CASE WHEN sg.name is null THEN g.name ElSE sg.name END
                            FROM "group" g
                            LEFT JOIN (
                                SELECT gr.groupid, sg.supergroupid, sg.name
                                FROM grouprole gr
                                INNER JOIN supergroup sg on gr.supergroupid = sg.supergroupid
                                WHERE
                                    sg.type_id IN (SELECT id FROM supergrouptype WHERE token = 'Ownership Group')
                                )    sg on g.groupid = sg.groupid
                                WHERE
                                    grouptype_id IN (SELECT id FROM grouptype WHERE token = 'Employment Agency')
                                GROUP BY
                                    CASE WHEN sg.name is null THEN g.name ELSE sg.name END
                        )
                        SELECT g.groupid, p.name
                        FROM first_group_for_each_parent p
                        INNER JOIN "group" g on p.nuwassistid = g.nuwassistid
                        WHERE p.name ilike :name_filter
                        ORDER BY p.name;
                                    """, bindparams=[bindparam('name_filter', ('%%%s%%' % name_filter))])
        elif filter_token == 'employment':
            query = text("""
                    with results as (
                        SELECT g.groupid, g.name, g.sitesuburb,
                            CASE WHEN parent.name is null THEN
                            regexp_replace(g.name, coalesce(g.sitesuburb, ''), '', 'i') ELSE parent.name end || upper(coalesce(' ' || g.sitesuburb, '')) proposed_name
                        FROM "group" g
                        LEFT JOIN (
                            SELECT gr.groupid groupid, regexp_replace(regexp_replace(sg.name, 'pay centre', '', 'i'), 'payin', 'i') AS name
                            FROM grouprole gr
                            INNER JOIN supergroup sg on gr.supergroupid = sg.supergroupid
                            WHERE sg.type_id IN (SELECT id FROM supergrouptype WHERE token = 'Ownership Group')
                            AND not sg.name ilike '%debit%'
                            ) parent ON g.groupid = parent.groupid
                        WHERE g.grouptype_id IN (SELECT id FROM grouptype WHERE token = 'Union Site')
                        AND coalesce(g.sitesuburb, '') <> ''
                        ORDER BY
                            CASE WHEN parent.name is null THEN
                            regexp_replace(g.name, g.sitesuburb, '', 'i') ELSE parent.name end || upper(coalesce(' ' || g.sitesuburb, ''))
                    )
                    SELECT r.groupid, r.proposed_name
                    FROM results r
                    WHERE r.proposed_name ilike :name_filter
                    ORDER BY r.proposed_name;
                                    """, bindparams=[bindparam('name_filter', ('%%%s%%' % name_filter))])

        result = sess.execute(query)

        response_dict = {"query": name_filter,
                        "suggestions": []}

        for place in result:
            response_dict['suggestions'].append({'value': place[1],
                                            'data': place[0]})

        return json.dumps(response_dict)

class AjaxValdiateEmail(grok.View):
    grok.name('validateEmail')
    grok.require('zope2.View')
    grok.context(IJoinContext)

    def render(self):
        form = self.request.form
        response = self.request.response
        response.setHeader("Content-type", "application/json")

        email = form.get('email')
        try:
            Products.CMFDefault.utils.checkEmailAddress(email)
        except EmailAddressInvalid:
            return json.dumps({"success":False, "message":"Invalid email address format."})
        if email_exists(email):
            return json.dumps({"success":False, "message":"Email exists. Please enter a different one."})

        return json.dumps({"success":True, "message":""})


class CommunityMembership(grok.View):
    """ Simple view for Community Membership join form
    """

    grok.name('community_join.html')
    grok.require('zope2.View')
    grok.context(zope.interface.Interface)

    connection = None
    errors = dict()

    community_membership_payment_tpl = ViewPageTemplateFile( 'join_templates/community_email.pt' )


    def update(self):
        form = self.request.form
        session = Session()

        # try:
        self.connection = nuw.types.spreedly.spreedly.get_connection()
        # except Warning, e:
        #     IStatusMessage(self.request).addStatusMessage(unicode(e), "error")

        fake_uuuid = '11111a11-aaa1-a111-11a1-111111a11111'

        person = session.query(Person).filter_by(hubid=fake_uuuid).first()
        if person is None:
            data = {'firstname':'Community', 'lastname':'User'}
            person_factory = zope.component.getUtility(
                zope.component.interfaces.IFactory, 'person')

            # Set some default values (some will change after successful payment)
            data[ 'webstatus' ] = 'unfinancial-member'
            data[ 'status' ] = 'Dummy member'
            data[ 'type' ] = 'Member'
            data[ 'activity' ] = 'supportive'

            person = person_factory(fake_uuuid, **data)
            session.add(person)

        token = form.get('token')
        if token is not None:
            pay_method = spreedlycore.PaymentMethod(self.connection, token)
            pay_method.load()
            errors = self.get_errors(pay_method)
            if errors:
                for error in errors:
                    self.errors[error['attribute']] = error['text']
                return

            if token and 'frequency' in pay_method.data['data']:
                # now we cobble together the rest to make a payment m)
                frequency = pay_method.data['data'].get('frequency')
                return self.payify(token, frequency, person, pay_method.data)

    def payify(self, token, frequency, person, data):
        form = self.request.form
        registry = queryUtility(IRegistry)
        settings = registry.forInterface(IRecurringSettings)
        amount = getattr(settings, frequency)

        gateway, db_gateway = self.get_payment_gateways(token)
        pay_method, db_pay_method = self.get_payment_methods(person, token)
        try:
            transaction = nuw.types.spreedly.spreedly.charge(
                pm=pay_method, db_method_id=db_pay_method.id,
                pg=gateway, db_gateway_id=db_gateway.id,
                person_id=person.id, amount=amount,
                component='Community Membership')
        except spreedlycore.APIRequest.RequestFailed, e:
            for error in e.errors:
                # TODO: :( will overwrite if we have more than one error
                logger.info(
                    'Unable to charge against the provided credit card.'
                    ' Error message was: {error}'.format(error=error['text'])
                )

        transaction.capture()
        recurpayment.add_recurring_payment(person, frequency, amount)

        mhost = getToolByName(self, 'MailHost')
        email = get_join_admin_email()
        mail_content = self.community_membership_payment_tpl(
            to_email = email, name = data['first_name'] + ' ' + data['last_name'],
            email = data['email'], phone = data['phone_number'], mobile = data['data'].get('mobile', ''),
            dob = data['data'].get('dob_day') + '/' + data['data'].get('dob_month') + '/' + data['data'].get('dob_year'),
            gender = data['data'].get('gender'), address = data['address1'], suburb = data['city'], state = data['state'],
            postcode = data['zip'], frequency = frequency, amount = amount,
        )
        mhost.send( mail_content )

        self.request.response.redirect(self.url('/community_thankyou.html'))

    def get_payment_methods(self, person, token):
        """ Same shit with the gateways :(
        """
        # this one sets the database payment method, but returns the
        # spreedly core payment method
        pay_method = nuw.types.spreedly.spreedly.set_user_payment_method(
            self.connection, token, person.personid, True, True)

        # aah the db payment method. Finally.
        db_pay_method = nuw.types.spreedly.spreedly.db_get_payment_method(
            token)
        # hang on.. don't you want to check if the database returns an
        # object? Perhaps I should, but why the heck do I set one then
        # before?
        assert pay_method is not None
        assert db_pay_method is not None
        return (pay_method, db_pay_method)

    def get_payment_gateways(self, token):
        """ Returns a tuple with payment gateways.

        Because if this confusing implementation of a
        (spreedly-core-python) PaymentGateway, and the existance of a
        PaymentGateway in the database, we'll wrap the retrieval of both
        in this method. Aaah... and btw I almost forgot to tell you: if
        there is no PaymentGateway, we create one... in the database.

        :rtype: tuple - (spreedlycore-python PaymentGateway, SQLAlchemy
                         PaymentGateway)
        """
        db_gateway = nuw.types.spreedly.spreedly.db_get_gateway(token)
        gateway = nuw.types.spreedly.spreedly.get_default_gateway(
            self.connection)
        if db_gateway is None:
            nuw.types.spreedly.spreedly.db_add_gateway(gateway)
            db_gateway = nuw.types.spreedly.spreedly.db_get_gateway(
                gateway.token)

        assert gateway is not None
        assert db_gateway is not None

        return (gateway, db_gateway)


    def api_login(self):
        assert self.connection is not None
        return self.connection.login

    def get_errors(self, pay_method):
        # Why this? Because the errors item in the PaymentMethod can be
        # either a dict (single error), a str (no error) or a list of
        # dicts (multiple errors). Excellent integration!
        assert getattr(pay_method, 'data', None) is not None
        assert isinstance(pay_method.data, dict)

        errors = pay_method.data.get('errors')
        if not errors:
            return []
        if isinstance(errors['error'], dict):
            return [errors['error']]
        elif isinstance(errors['error'], list):
            return errors['error']


    def valid_years(self):
        now = datetime.date.today()
        return range(now.year, now.year + 10)


    def get_payment_frequencies(self):
        registry = queryUtility(IRegistry)
        settings = registry.forInterface(IRecurringSettings)

        frequencies = []

        if settings.recur_week_community:
            frequencies.append(
                    ('recur_week_community', str(settings.recur_week_community)+"-week",
                    'Weekly')
                    )

        if settings.recur_quarter_community:
            frequencies.append(
                    ('recur_quarter_community', str(settings.recur_quarter_community)+"-quarter",
                    'Quarterly')
                    )

        if settings.recur_year_community:
            frequencies.append(
                    ('recur_year_community', str(settings.recur_year_community)+"-year",
                    'Yearly')
                    )

        return frequencies

class CommunityThankYou(grok.View):
    grok.name('community_thankyou.html')
    grok.require('zope2.View')
    grok.context(zope.interface.Interface)