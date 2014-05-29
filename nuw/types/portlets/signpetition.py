from plone.portlets.interfaces import IPortletDataProvider
from zope import schema
from plone.app.portlets.portlets import base
from zope.interface import implements
from zope.formlib import form
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from plone.app.vocabularies.catalog import SearchableTextSourceBinder
from Products.CMFCore.utils import getToolByName
from zope.component import getMultiAdapter
from string import Template
from z3c.saconfig import named_scoped_session
from nuw.types.petition import Signee
from nuw.types.member import get_user_person
from string import Template

Session = named_scoped_session("nuw.types")

JsTemplate = Template("""
            jQuery( function () {
                jQuery('#$petition_id').validate({
                    submitHandler: function(form) {
                        jQuery.ajax({
                            url: '$action_url',
                            type: 'post',
                            dataType: 'json',
                            data: jQuery('form#$petition_id').serialize(),
                            success: function(data) {
                               jQuery('#$petition_id-portlet .sign-title').html("Thank you for signing!")
                               .hide()
                               .fadeIn(1500);
                               if(data['success'] = true) {
                                   jQuery('#$petition_id').html("");
                                   var num = parseInt(jq('#$petition_signees').html()) + 1;
                                   var needed = parseInt(jq('#$petition_needed').html()) - 1;
                                   var total = parseInt(num) + parseInt(needed);
                                   var percent = parseInt(num) / total;
                                   jQuery('#$petition_signees').html( num.toString() );
                                   jQuery('#$petition_needed').html( needed.toString() );
                                   jQuery('#progress-bar div.bar').width( percent * 100.0 + "%" );
                                   jQuery('.petition-details').html('<a style="color: #E3173E" href="$petition_url">View the list of Public Signees</a>');
                                } else if(data['error']) {
                                    jQuery('#$petition_id').html("Error:" + data['error']);
                                }
                            },
                            error: function(errorThrown){
                               console.log(errorThrown);
                            }
                        });
                    }
                });
                jQuery('#$petition_submit').click(function() {
                    jQuery(this).hide();
                });
            }); //end
        """)

class ISignPetitionPortlet(IPortletDataProvider):
    display_progress = schema.Bool(title = u"Display progress bar",
                                   description = u"Check if you would like to display progress bar in the portlet.",
                                   required = False)
    
    display_stats = schema.Bool(title = u"Display petition statistics",
                                description = u"Check if you would like to display petition statistics (total number signed, target number, etc.)",
                                required = False)
    
    limit_to_target = schema.Bool(title = u"Limit petition to target of petition",
                                  description = u"Check if you would like to stop allowing signatures after petition reaches target number.",
                                  required = False)

class Assignment(base.Assignment):
    implements(ISignPetitionPortlet)
    
    title = u'Sign Petition Portlet'
    
    def __init__( self, display_progress = True, display_stats = True, limit_to_target = True):
        self.display_progress = display_progress
        self.display_stats = display_stats
        self.limit_to_target = limit_to_target
    
    def get_person( self ):
        self.person = get_user_person(self.context)
    
    def get_firstname( self ):
        if self.person:
            return self.person.firstname

    def get_lastname( self ):
        if self.person:
            return self.person.lastname

    def get_email( self ):
        if self.person:
            return self.person.email
    
    def get_postcode( self ):
        if self.person:
            return self.person.homepostcode
    
class AddForm(base.AddForm):
    form_fields = form.Fields(ISignPetitionPortlet)
    label = u"Add Sign this petition portlet"
    description = u"This portlet lets users sign the petition that is selected."
    
    def create(self, data):
        return Assignment(**data)
    
class EditForm(base.EditForm):
    form_fields = form.Fields(ISignPetitionPortlet)
    label = u"Add Sign this petition portlet"
    description = u"This portlet lets users sign the petition that is selected."
    

class Renderer(base.Renderer):
    _template = ViewPageTemplateFile('templates/signpetition.pt')
    
    def update(self):
        context = self.context.aq_inner
        catalog = getToolByName(context, 'portal_catalog')
        # query petition by path from root
        path = '/'.join( context.getPhysicalPath() )
        result = catalog({'Type':['Petition',],
                          'path': path},
                          sort_on='modified',
                          sort_order='descending',
                          review_state='published')
        
        if result:
            self.petition = result[0]
            petition_obj = result[0].getObject()
            self.action_url = result[0].getPath()
            
            # set up all the petition ids to be used in the content
            self.petition_id = "petition-" + self.petition['UID']
            self.petition_submit = self.petition_id + "-submit"
            self.petition_portlet = self.petition_id + "-portlet"
            self.petition_signees = self.petition_id + "-signees"
            self.petition_text = None
            if petition_obj and\
                    petition_obj.recipient_text and\
                    len(petition_obj.recipient_text.output):
                self.petition_text = Template(petition_obj.recipient_text.output).safe_substitute(recipient_name = petition_obj.recipient_name, first_name = 'Joe', 
                                                                                        last_name = 'Bloggs', email = 'jbloggs@nuw.org.au',
                                                                                        country = 'Australia', postcode = 2000)
            
            # query db for signee figures
            self.portlet_totalSignees = petition_obj.get_nr_signees() # query all signees for counting
            target = float(petition_obj.target_num)
            self.portlet_progressPercentWidth = ("width: %s" % ((self.portlet_totalSignees / target) * 100)) + "%;"
            self.portlet_target_num = petition_obj.target_num
            self.portlet_target_needed = self.portlet_target_num - self.portlet_totalSignees
            self.petition_needed = self.petition_id + "-needed"
            
            # dynamic js declaration for multiple portlets rendered on same page with unique ids 
            self.ajax_code = JsTemplate.substitute(petition_id=self.petition_id, action_url=self.action_url + "/@@postForm",
                                                   petition_submit=self.petition_submit, petition_signees=self.petition_signees,
                                                   petition_needed=self.petition_needed, petition_url=self.action_url)
            
            sdm = context.session_data_manager
            session = sdm.getSessionData(create=True)
            if self.petition['UID'] in self.request or session.has_key(self.petition['UID']): # found cookie, dont render
                self.already_signed = True
            else:
                self.already_signed = False
                
            # check if petition should not be rendered anymore
            if self.data.limit_to_target:    
                if self.portlet_totalSignees >= self.portlet_target_num:
                    self.already_signed = False
        else:
            self.petition = None
        
    def displayProgess(self):
        return True if self.data.display_progress else False
        
    def displayStats(self):
        return True if self.data.display_stats else False
            
    def render(self):
        return self._template()
