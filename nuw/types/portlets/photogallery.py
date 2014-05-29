from zope.interface import implements
from zope.component import getMultiAdapter
from zope import schema
from zope.formlib import form
from plone.app.portlets.portlets import base
from plone.portlets.interfaces import IPortletDataProvider
from Products.CMFCore.utils import getToolByName
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile

from nuw.types.campaign import ICampaign


class IPhotoGalleryPortlet(IPortletDataProvider):
    count = schema.Int(title=u'Number of images to display',
            description=u'How many images to list.',
            required=True,
            default=12)


class Assignment(base.Assignment):
    implements(IPhotoGalleryPortlet)
    title = u'Campaign Photo Gallery'

    def __init__(self, count=12, size='thumb'):
        base.Assignment.__init__(self)
        self.count = count
        self.size = size


class AddForm(base.AddForm):
    form_fields = form.Fields(IPhotoGalleryPortlet)

    def create(self, data):
        return Assignment(**data)


class EditForm(base.EditForm):
    form_fields = form.Fields(IPhotoGalleryPortlet)


class Renderer(base.Renderer):
    render = ViewPageTemplateFile('templates/photogallery.pt')

    @property
    def folder(self):
        """
        Get the parent Campaign path and append the gallery
        """
        try:
            campaign = self.context.acquire_campaign()
        except AttributeError:
            return None

        folder_path = ''
        for sub_path in campaign.getPhysicalPath():
            folder_path += sub_path + '/'

        return folder_path + 'gallery'

    @property
    def image_brains(self):
        """
        Return a list of images sorted in descending creation date
        """
        path = self.folder
        if not path:
            return []
        catalog = getToolByName(self.context, 'portal_catalog')

        query = {
            'portal_type': 'Image',
            'sort_on': 'effective',
            'sort_order': 'descending',
            'path': path
        }

        return catalog(**query)[:self.data.count]

    @property
    def images(self):
        """
        Return the queried images as scaled Image objects
        """
        return [i.getObject() for i in self.image_brains]

    @property
    def available(self):
        if len(self.images) > 2:
            return True
        else:
            return False
