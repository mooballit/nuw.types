from zope.i18nmessageid import MessageFactory
from sqlalchemy.ext.declarative import declarative_base
from Products.CMFCore import utils as cmf_utils

# Set up the i18n message factory for our package
MessageFactory = MessageFactory('nuw.types')
Base = declarative_base()


def initialize(context):
    """Initializer called when used as a Zope 2 product."""
    from nuw.types.api.tool import SyncAPITool
    cmf_utils.ToolInit(
        SyncAPITool.id,
        tools=(SyncAPITool, ),
        icon='resources/apitool.png',
        ).initialize(context)

    from nuw.types.EmailUpdateTool import EmailUpdateTool
    cmf_utils.ToolInit(
        EmailUpdateTool.EmailUpdateTool.id,
        tools=(EmailUpdateTool, ),
        icon='resources/apitool.png',
        ).initialize(context)

    from nuw.types.admin_area.splashupload import SplashUploadTool
    cmf_utils.ToolInit(
        SplashUploadTool.id,
        tools=(SplashUploadTool, ),
        icon='resources/apitool.png',
        ).initialize(context)
