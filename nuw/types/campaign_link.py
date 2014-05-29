from five import grok
from zope import schema
from urllib import quote
from plone.directives import form
from zope.component import getUtility
from zope.interface import implements
from plone.dexterity.content import Item
from Products.CMFCore.utils import getToolByName
from zope.schema.vocabulary import SimpleVocabulary
from Products.CMFPlone.interfaces import IPloneSiteRoot
from zope.schema.interfaces import IContextSourceBinder
from plone.app.content.interfaces import INameFromTitle


@grok.provider(IContextSourceBinder)
def campaign_source_binder(context):
    terms = []
    catalog = getToolByName(context, 'portal_catalog')

    for campaign in catalog(portal_type='nuw.types.campaign'):
        term = SimpleVocabulary.createTerm(
                campaign.getPath(),
                str(campaign.getPath()),
                campaign.Title
            )
        terms.append(term)

    return SimpleVocabulary(terms)


class INameFromCampaign(INameFromTitle):
    """ Marker interface for new 'title' naming scheme
    """


class NameFromCampaign(object):
    """ Override the default 'title' naming scheme. Will also pass this title
        to the 'id' setting functions.
    """

    implements(INameFromCampaign)

    def __init__(self, context):
        self.context = context

    @property
    def title(self):
        site = getUtility(IPloneSiteRoot)
        return site.unrestrictedTraverse(self.context.campaign).Title()

    @property
    def description(self):
        site = getUtility(IPloneSiteRoot)
        return site.unrestrictedTraverse(self.context.campaign).Description()

    @property
    def effective(self):
        site = getUtility(IPloneSiteRoot)
        return site.unrestrictedTraverse(self.context.campaign).effective


class ICampaignLink(form.Schema):

    campaign = schema.Choice(
            title=u'Campaign to link to',
            source=campaign_source_binder,
        )


class CampaignLink(Item):

    def getRemoteUrl(self):
        return quote(self.remote_url() or '', safe='?$#@/:=+;$,&%')

    def remote_url(self):
        return self.campaign

    def Title(self):
        site = getUtility(IPloneSiteRoot)
        return site.unrestrictedTraverse(self.campaign).Title()

    def Description(self):
        site = getUtility(IPloneSiteRoot)
        return site.unrestrictedTraverse(self.campaign).Description()

    def EffectiveDate(self):
        site = getUtility(IPloneSiteRoot)
        return site.unrestrictedTraverse(self.campaign).EffectiveDate()

    @property
    def effective(self):
        site = getUtility(IPloneSiteRoot)
        return site.unrestrictedTraverse(self.campaign).effective

    @property
    def image(self):
        site = getUtility(IPloneSiteRoot)
        return site.unrestrictedTraverse(self.campaign).image
