from five import grok
from campaign import ICampaign, CampaignAddForm

import zope.schema

class ICampaignEvent( ICampaign ):
    start = zope.schema.Datetime( title = u'Start Date' )
    end = zope.schema.Datetime( title = u'End Date' )
    
class CampaignEventAddForm( CampaignAddForm ):
    grok.name( 'nuw.types.campaignevent' )
