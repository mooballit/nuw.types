from five import grok
from members_area import get_or_kick_user
from OFS.interfaces import IFolder
from OFS.SimpleItem import SimpleItem
from Products.CMFCore.utils import UniqueObject
from z3c.saconfig import named_scoped_session
from zope.interface import Interface, implements

from Products.statusmessages.interfaces import IStatusMessage
from zope.i18nmessageid import MessageFactory

from nuw.types.spreedly import spreedly
import spreedlycore
import datetime, string
import json

_ = MessageFactory('nuw.types')

Session = named_scoped_session( 'nuw.types' )
grok.templatedir( 'templates' )

class UpdateCard( grok.View ):
    grok.context( IFolder )
    grok.name( 'update_card' )
    
    data = None
    
    def update( self ):
        if self.request.form:
            self.data = self.request.form
            self.user = get_or_kick_user(self.context, self.request)
            self.person = self.user.person
    
    def render( self ):
        if self.data:
            try:
                time = datetime.datetime.now().utcnow().ctime()
                
                if 'set_as_default' in self.data:
                    sess = Session()
                    token = self.data.get('set_as_default')
                    old_default = sess.query(spreedly.PaymentMethod).filter(spreedly.PaymentMethod.personid == unicode(self.person.personid), spreedly.PaymentMethod.defaulted == True).first()
                    if old_default:
                        old_default.defaulted = False
                        
                    new_default = spreedly.db_get_payment_method(token)
                    if new_default:
                        new_default.defaulted = True
                    
                    return json.dumps( { 'status': 'ok', 'method':'set as default', 'time':time } )

                if 'delete_token' in self.request.form:
                    try:
                        self.connection = spreedly.get_connection()
                    except Warning, e:
                        return json.dumps( { 'status': 'fail', 'except': str( e ), 'time':time } )

                    token = self.data.get('delete_token')
                    method = spreedlycore.PaymentMethod(self.connection, token)

                    try:
                        message = spreedly.delete_method(method, self.person.personid)
                    except spreedlycore.APIRequest.RequestFailed, e:
                        return json.dumps( { 'status': 'fail', 'except': str( e.errors ), 'time':time } )
                        
                    return json.dumps( { 'status': 'ok', 'method':'deleted', 'time':time } )
                
            except Exception as e:
                return json.dumps( { 'status': 'fail', 'except': str( e ) } )

class PaymentMethods( grok.View ):
    grok.context( IFolder )
    grok.name( 'payment-methods' )
    
    user = None
    connection = None
    errors = dict()
    
    def update(self):
        self.errors = dict()
        
        try:
            self.connection = spreedly.get_connection()
        except Warning, e:
            IStatusMessage(self.request).addStatusMessage(unicode(e), "error")
            return False
        
        self.user = get_or_kick_user(self.context, self.request)
        self.person = self.user.person
        
        if 'token' in self.request.form:
            token = self.request.form.get('token')
            
            try:
                spreedly.set_user_payment_method(self.connection, token, self.person.personid, True, False)
            except spreedlycore.APIRequest.RequestFailed, e:
                for error in e.field_errors:
                    if error.has_key('attribute'):
                        self.errors[error['attribute']] = error['text']
                if len(e.errors):
                    self.errors[token] = ''
                    for error in e.errors:
                        self.errors[token] += error['text'] + ' '
                    IStatusMessage(self.request).addStatusMessage(_(self.errors[token]), "error")
            
            return
    
    def get_methods(self):
        if self.person:
            person_id = self.person.personid
            methods = spreedly.db_get_user_payment_methods(person_id, only_retained = True)
            if methods.count() > long(0):
                return methods

    def get_transactions(self):
        if self.person:
            person_id = self.person.personid
            transactions = spreedly.db_get_user_transactions(person_id)
            return transactions

    def get_phone(self):
        if self.person.mobile and self.person.mobile != '':
            return self.person.mobile
        elif self.person.home and self.person.home != '':
            return self.person.home
        else:
            return self.person.work
    
    def api_login(self):
        return self.connection.login

    def redirect(self):
        return "%s/@@payment-methods" % self.context.absolute_url()

    def get_date(self):
        return datetime.date.today()

    def valid_years(self):
        now = datetime.date.today()
        return [str(year) for year in range(now.year, now.year + 19)]
