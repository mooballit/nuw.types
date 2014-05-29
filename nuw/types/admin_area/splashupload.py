from five import grok
from Products.statusmessages.interfaces import IStatusMessage
from Products.CMFPlone.interfaces import IPloneSiteRoot
from plone.directives import form
from nuw.types.admin_area.admin_area import permission

from Products.CMFCore.utils import UniqueObject
from Globals import InitializeClass
from Products.CMFCore.utils import getToolByName

from Products.CMFDefault.formlib.schema import SchemaAdapterBase
from zope.component import adapts
from zope.interface import implements

from plone.namedfile.field import NamedImage
import plone.namedfile
from zope.schema import TextLine
from z3c.form import button


class SplashUploadTool(grok.Container):
    id = 'splash_tool'
    meta_type = 'Splash Upload Tool'
    plone_tool = 1

    splash_filename = None
    splash_url = str()

InitializeClass(SplashUploadTool)


class ISplashUpload(form.Schema):
    splash_image = NamedImage(
            title=u"Splash Image",
            description=u"Please provide a JPEG image that is 800px wide and 600px high.",
            default=None)

    splash_url = TextLine(
            title=u"URL for Splash",
            description=u"Specify the URL that the Splash links to.",
            default=u"",
            required=False)


class SplashUpload(form.SchemaForm):
    grok.name('splash_upload')
    grok.require(permission)
    grok.context(IPloneSiteRoot)

    schema = ISplashUpload
    ignoreContext = True

    label = u"Upload a Splash Image"
    description = """Upload a new splash image, or delete the existing splash"""

    def update(self):
        super(SplashUpload, self).update()
        self.request.set('disable_plone.leftcolumn', 1)
        self.request.set('disable_plone.rightcolumn', 1)
        self.request.set('disable_border', 1)

    @button.buttonAndHandler(u'Upload')
    def handleUpload(self, action):
        data, errors = self.extractData()
        if errors:
            self.status = self.formErrorsMessage
            return

        splash_tool = getToolByName(self.context, 'splash_tool')
        if hasattr(splash_tool, 'splash_image'):
            self.context.manage_delObjects(['splash_image'])
        splash_tool.invokeFactory('Image', 'splash_image', image=data['splash_image'].data)
        splash_tool.splash_filename = data['splash_image'].filename
        splash_tool.splash_url = data['splash_url']

        IStatusMessage(self.request).addStatusMessage(
                u"Splash image uploaded, Image: "
                +str(splash_tool.splash_filename)
                +u" URL: "
                +str(splash_tool.splash_url), "info")
        self.request.response.expireCookie('splash_seen')
        self.request.response.redirect("@@splash_upload")

    @button.buttonAndHandler(u'Delete Image')
    def handleDelete(self, action):
        splash_tool = getToolByName(self.context, 'splash_tool')
        if hasattr(splash_tool, 'splash_image'):
            self.context.manage_delObjects(['splash_image'])
        splash_tool.splash_filename = None
        splash_tool.splash_url = None

        IStatusMessage(self.request).addStatusMessage(
                u"Deleted existing splash image", "info")
        self.request.response.expireCookie('splash_seen')
        self.request.response.redirect("@@splash_upload")

    @button.buttonAndHandler(u'Cancel', name='cancel')
    def handleCancel(self, action):
        IStatusMessage(self.request).addStatusMessage(
                u"Upload cancelled", "info")
        self.request.response.redirect("@@overview-controlpanel")
