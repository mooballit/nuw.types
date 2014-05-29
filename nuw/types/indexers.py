from plone.indexer.decorator import indexer
from Products.ATContentTypes.interfaces.news import IATNewsItem

from nuw.types.industry import IIndustry
from nuw.types.base import get_parent_content_type

@indexer(IATNewsItem)
def newsitem_campaign(object, **kw):
    if hasattr(object, 'acquire_campaign'):
        return object.acquire_campaign().Title()

@indexer(IATNewsItem)
def newsitem_industry(object, **kw):
    industry = get_parent_content_type(object, IIndustry)
    if industry and object != industry:
        return industry.Title()
