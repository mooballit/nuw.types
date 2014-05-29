from five import grok
from mooball.plone.spreedlycore.configlet import SiteSpreedlyCredentials
from nuw.types.campaign import ICampaign
from nuw.types.member import get_user_person
from nuw.types.spreedly.spreedly import charge, get_connection, get_default_gateway, db_get_user_payment_methods,\
        db_get_payment_method, db_add_method, db_get_gateway, db_add_gateway
from plone.app.portlets.portlets import base
from plone.portlets.interfaces import IPortletDataProvider
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from spreedlycore import PaymentMethod, APIRequest
from zope.formlib import form
from zope.interface import implements

import datetime

class IDonationPortlet( IPortletDataProvider ):
    pass

class Assignment( base.Assignment ):
    implements( IDonationPortlet )

    title = u'Donation Portlet'
    
class AddForm( base.AddForm ):
    form_fields = form.Fields( IDonationPortlet )

    def create( self, data ):
        return Assignment()


class EditForm( base.EditForm ):
    form_fields = form.Fields( IDonationPortlet )

class Renderer( base.Renderer ):
    _template = ViewPageTemplateFile( 'templates/donationportlet.pt' )

    @property
    def available( self ):
        return ICampaign.providedBy( self.context ) and self.context.has_donation

    def render( self ):
        return self._template()
        
grok.templatedir( 'templates' )

class DonationForm( grok.View ):
    grok.name( 'donate' )
    grok.context( ICampaign )
    
    def update( self ):
        self.data = {}
        self.success = False
        
        self.apilogin = SiteSpreedlyCredentials().getLogin()
        
        custom_donation = self.request.form.get( 'custom-donation', '' )
        donation = self.request.form.get( 'donation', '' )
        
        self.donation = ( custom_donation.isdigit() and int( custom_donation ) ) or ( donation.isdigit() and int( donation ) ) or None 
        
        self.person = get_user_person( self.context )
        self.persons_pms = self.person and db_get_user_payment_methods( self.person.personid, only_retained = True ) or None
        if self.persons_pms:
            if self.persons_pms.count() == long(0):
                self.persons_pms = None
        
        if self.person:
            # Load default values from person in case user wants to enter in a new card.
            self.data = {
                'first_name': self.person.firstname,
                'last_name': self.person.lastname,
                'email': self.person.email,
                'phone_number': self.person.home or self.person.mobile or self.person.work or None,
                'address1': ' '.join( [ addr for addr in [ self.person.homeaddress1, self.person.homeaddress2 ] if addr ] ),
                'zip': self.person.homepostcode,
                'city': self.person.homesuburb,
                'state': self.person.homestate,
            }
        
        self.errors = []
        self.field_errors = {}
        
        self.token = self.request.form.get( 'token' )
        if self.donation and self.token:
            # Do charge
            conn = get_connection()
            gw = get_default_gateway( conn )
            dbgw = db_get_gateway( gw.token )
            if dbgw is None:
                db_add_gateway( gw )
                dbgw = db_get_gateway( gw.token )
            
            dbpm = db_get_payment_method( self.token )
            pm = PaymentMethod( conn, self.token )
            if dbpm is None:
                db_add_method( pm, self.person and self.person.personid or None )
                dbpm = db_get_payment_method( self.token )
            else:
                pm.from_dict( dbpm.__dict__ )
            
            try:
                tx = charge( pm, dbpm.id, gw, dbgw.id, self.person and self.person.personid or None, self.donation, 'Donation - %s' % self.context.Title() )
            except APIRequest.RequestFailed, e:
                # Handle errors
                self.errors = e.errors
                
                # TODO: Some of this should probably be moved to spreedlycore module
                for error in e.field_errors:
                    if error.has_key('attribute'):
                        self.field_errors[error['attribute']] = error['text']
                
                # Set some default data from the provided payment method
                self.data = {
                    'first_name': pm.data['first_name'],
                    'last_name': pm.data['last_name'],
                    'email': pm.data['email'],
                    'phone_number': pm.data['phone_number'],
                    'address1': pm.data['address1'],
                    'zip': pm.data['zip'],
                    'city': pm.data['city'],
                    'state': pm.data['state'],
                    'number': pm.data['number'],
                    'verification_value': pm.data['verification_value'],
                    'month': str( pm.data['month'] ).zfill( 2 ),
                    'year': str( pm.data['year'] ),
                }
            else:
                self.success = True

    def valid_years( self ):
        now = datetime.date.today()
        return [ str( year ) for year in range( now.year, now.year + 20 ) ]
