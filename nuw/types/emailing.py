from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from nuw.types.admin_area.admin_views import get_debug_email
from Products.CMFCore.utils import getToolByName
from pprint import pprint
import string
# Utility module to make debugging email functionality more debuggable

def send_email_to( context, people, sender, template_html, template_text, subject, **extra_data ):
    '''
        people: List/Iterable of Person objects to send the email to
            NOTE: It is assumed that people without email addresses are filtered out!
        sender: Name + email of sender
        template_*: template object to send (html and text versions)
            Needs to at least have to_email, to_name variables in it
            to insertion of person's email and name
        extra_data: any extra data to be inserted into the template

        To enable email debugging just the debug email in site setup
    '''
    mhost = getToolByName(context, 'MailHost')

    # Lookup if debug email is set and
    debug_email = get_debug_email()

    extra_data['content'] = filter(lambda x: x in string.printable, extra_data['content'])
    for person in people:
        base_email = MIMEMultipart('alternative')
        base_email['to'] = "%s %s <%s>" % (
            person.firstname, person.lastname, debug_email or person.email
        )
        base_email['from'] = sender
        base_email['subject'] = subject

        text_part = MIMEText( template_text(
            first_name = person.firstname,
            last_name = person.lastname,
            **extra_data
        ), 'plain')
        base_email.attach( text_part )

        html_part = MIMEText( template_html(
            first_name = person.firstname,
            last_name = person.lastname,
            **extra_data
        ), 'html')
        base_email.attach( html_part )

        mhost.send( base_email.as_string() )
