# Interface definitions
from zope.interface import Interface, Attribute

class IEmailUpdateToolView(Interface):
    """ grok.View with utility methods """

    def encode_mail_header(text):
        """ Encodes text into correctly encoded email header """

    def encoded_mail_sender():
        """ returns encoded version of Portal name <portal_email> """

    def registered_notify_subject():
        """ returns encoded version of registered notify template subject line """

    def mail_password_subject():
        """ returns encoded version of mail password template subject line """

class portal_email_update(Interface):
    """Defines an interface for a tool that provides a facility to
    update email addresses."""

    id = Attribute('id','Must be set to "portal_email_update"')

    def requestUpdate(userid, email):
        """Ask the system to start the email update procedure for
        user 'userid'.

        Returns the random string that must be used to update the
        email."""

    def updateEmail(randomstring):
        """Set the email (in 'email') for the user who maps to
        the string in 'randomstring'. The 'userid' parameter is provided
        in case extra authentication is needed."""
