from five import grok
from zope import schema
from plone.directives import form

from zope.interface import Invalid
from zope.app.container.interfaces import IObjectRemovedEvent
from plone.app.textfield import RichText
from plone.dexterity.content import Item
from Products.statusmessages.interfaces import IStatusMessage

from Products.CMFCore.utils import getToolByName
from z3c.saconfig import named_scoped_session
from sqlalchemy import Column, Integer, Text, String, Sequence

from plone.uuid.interfaces import IUUID
from Acquisition import aq_base, aq_inner
from Products.CMFCore.utils import getToolByName
from nuw.types import Base
import datetime
import json
import csv
import cStringIO
import logging
from string import Template

grok.templatedir('templates')
Session = named_scoped_session("nuw.types")
logger = logging.getLogger("nuw.types.petition")

class IPetition(form.Schema):
    """A petition 
    """
    
    text = RichText(title = u"Petition details",
                    description = u"Detailed description of the petition",
                    required = False)
    
    target_num = schema.Int(title = u"Target number of signs")
    
    recipient_bool = schema.Bool(title = u"Send to a recipient",
                                 description = u"If this is checked, every time someone signs the petition an email will be sent to the recipient specified below. Note: All fields below are required if recipient emailing enabled!")
    
    recipient_email = schema.TextLine(title = u"Recipient email",
                                     description = u"Only for petitions with a recipient to email",
                                     required = False)
    
    recipient_name = schema.TextLine(title = u"Recipient name",
                                     description = u"Only for petitions with a recipient to email",
                                     required = False)
    
    recipient_subject = schema.TextLine(title = u"Email subject",
                                        description = u"Subject of the email sent to the recipient.",
                                        required = False)
    
    recipient_text = RichText(title = u"Email template",
                              description = u"""The contents will be used as the body of the email sent to the recipient, the following keywords will be replace with the corresponding details:
                                              $first_name is the first name of the signee.
                                              $last_name is the last_name of the signee.
                                              $email is the email of the signee.
                                              $country is the country of the signee.
                                              $postcode is the post code of the signee.
                                              $recipient_name is the name of the recipient.
                                              All of these are optional.""",
                              default = u"""Dear $recipient_name, 
                                            $first_name $last_name from $country, $postcode; has just signed a petition regarding such and such.""",
                              required = False)

class Petition( Item ):
    def get_signees( self, public = True ):
        """Get all the signees that belong to this petition.
        """
        sess = Session()
        if public:
            dbsignees = sess.query(Signee).filter(Signee.petition_id == IUUID(self, None), Signee.public == ( public and 1 or 0 ) ).order_by(Signee.id.desc())
        else:
            dbsignees = sess.query(Signee).filter(Signee.petition_id == IUUID(self, None)).order_by(Signee.id.desc())
        
        return dbsignees
    
    def get_nr_signees( self, public = False ):
        return self.get_signees( public ).count()
 
class Signee(Base):
    __tablename__ = "signees"
    
    id = Column(Integer, Sequence( "signee_id" ), primary_key = True)
    petition_id = Column(String, index = True)
    first_name = Column(String(200), nullable = False)
    last_name = Column(String(200), nullable = False)
    email = Column(String(200), nullable = False)
    country = Column(String(100), nullable = False)
    postcode = Column(Integer, index = True)
    public = Column(Integer, index = True)

  
@grok.subscribe(IPetition, IObjectRemovedEvent)
def create_handler(petition, event):
    """Delete all the signees for this petition
    """
    sess = Session()
    context = aq_base(petition)
    dbsignees = sess.query(Signee).filter(Signee.petition_id == IUUID(context, None)).delete()
  
class PetitionView(grok.View):
    grok.context(IPetition)
    grok.require('zope2.View')
    grok.name('view')

    def update(self):
       """Called before rendering the template
       """
       self.totalSignees = int(self.context.get_nr_signees()) # query all signees for counting
       self.getSignees = self._data()[:5] # by default only query public showing signees then limit result set to 5
       target = float(self.context.target_num)
       self.progressPercentWidth = ("width: %s" % int((self.totalSignees / target) * 100)) + "%;"
       self.target_num = self.context.target_num
       self.haveSignees = self.totalSignees > 0

    def _data(self, public=True):
        dbsignees = self.context.get_signees( public )
        return [ dict(first_name = signee.first_name,
                      last_name = signee.last_name,
                      country = signee.country,
                      public = signee.public,)
                for signee in dbsignees
                ]

class AjaxPetitionPostView(grok.View):
    grok.context(IPetition)
    grok.require('zope2.View')
    grok.name('postForm')
    
    def update(self):
        context = self.context
        self.signedSuccess = False
        self.email_exception = False

        if "signed" in self.request.form:
           sess = Session()
           form = self.request.form
           petition_id = IUUID(context, None)
           sess.add(Signee(petition_id = petition_id, 
                         first_name = form['first_name'], 
                         last_name = form['last_name'], 
                         email = form['email'],
                         country = form['country'],
                         postcode = form['postcode'],
                         public = 1 if 'public' in form else 0))
           # confirm succesful signature
           self.signedSuccess = True
           self.request.response.setCookie(petition_id, 'signed', expires=(datetime.datetime.now() + datetime.timedelta(weeks=520)).strftime('%a, %d %b %Y %H:%M:%S GMT'), path='/')
           # set session data so that portlet can hide on confirmation
           # of success because cookie won't be seen till post-rendering
           sdm = context.session_data_manager
           session = sdm.getSessionData(create=True)
           session.set(petition_id, 'signed')
           # then proceed to email if requied
           if context.recipient_bool: # only if recipient exists and publicity of signee has been aproved
               body = Template(context.recipient_text.output).safe_substitute(recipient_name = context.recipient_name, first_name = form['first_name'], 
                                                                                        last_name = form['last_name'], email = form['email'],
                                                                                        country = form['country'], postcode = form['postcode'])
               try:
                   host = getToolByName(context, 'MailHost')
                   host.send(body.encode('ascii','xmlcharrefreplace'), mto=context.recipient_email, mfrom=form['email'], subject=context.recipient_subject, 
                             msg_type='text/html')
                   self.email_exception = False
               except UnicodeEncodeError as e:
                   self.signedSuccess = False
                   self.email_exception = e
                   logger.error("Encountered an mail sending error: %s" % str(e))

    def render(self):
        response = self.request.response
        response.setHeader("Content-type", "application/json")
        if self.signedSuccess:
            response_dict = {"success": True}
        else:
            response_dict = {"success": False}
            if self.email_exception:
                response_dict.update({"error" : "Email failed to send."})
                
        return json.dumps(response_dict) # return JSON
    
class PetitionAsCSVView(grok.View):
    grok.context(IPetition)
    grok.require('zope2.View')
    grok.name('petitionAsCSV')
    
    def render(self):
        response = self.request.response
        response.setHeader("Content-Type", "application/force-download")
        response.setHeader("Content-Disposition", "attachment; filename=petition.csv")
        sess = Session()
        dbsignees = sess.query(Signee).filter(Signee.petition_id == IUUID(self.context, None))
        output = cStringIO.StringIO()
        writer = csv.writer(output, delimiter=',')
        writer.writerow(['first_name','last_name','postcode','country','email','public'])
        for signee in dbsignees:
            writer.writerow([signee.first_name, signee.last_name, signee.postcode, signee.country, signee.email, signee.public])
        return output.getvalue()
