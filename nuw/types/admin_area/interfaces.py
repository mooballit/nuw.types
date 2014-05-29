import zope.schema
from plone.directives import form

class IRecurringSettings(form.Schema):
    recur_week = zope.schema.Float(
            title = u'Weekly Recurring Charge',
            required = False,
            default = None,
            )
    recur_month = zope.schema.Float(
            title = u'Monthly Recurring Charge',
            required = False,
            default = None,
            )
    recur_quarter = zope.schema.Float(
            title = u'Quarterly Recurring Charge',
            required = False,
            default = None,
            )
    recur_year = zope.schema.Float(
            title = u'Yearly Recurring Charge',
            required = False,
            default = None,
            )
    # Market research fees
    recur_week_market_research = zope.schema.Float(
            title = u'Weekly Reccuring Charge for Market Research groups',
            required = False,
            default = None,
        )
    recur_month_market_research = zope.schema.Float(
            title = u'Monthly Reccuring Charge for Market Research groups',
            required = False,
            default = None,
        )
    recur_quarter_market_research = zope.schema.Float(
            title = u'Quarterly Reccuring Charge for Market Research groups',
            required = False,
            default = None,
        )
    recur_year_market_research = zope.schema.Float(
            title = u'Yearly Reccuring Charge for Market Research groups',
            required = False,
            default = None,
        )
    # Community membership fees
    recur_week_community = zope.schema.Float(
            title = u'Weekly Reccuring Charge for Community Membership',
            required = False,
            default = None,
        )
    recur_quarter_community = zope.schema.Float(
            title = u'Quarterly Reccuring Charge for Community Membership',
            required = False,
            default = None,
        )
    recur_year_community = zope.schema.Float(
            title = u'Yearly Reccuring Charge for Community Membership',
            required = False,
            default = None,
        )



class IAdminEmails(form.Schema):
    """"""
    join_email = zope.schema.TextLine(
            title = u'Activation/Join Email Recipient',
            description = u'''All activations and joins will send an email
                    here.''',
            required = True,
            )

    """
    fail_email = zope.schema.TextLine(
            title = u'Bounce/Failing Email Recipient',
            description = u'''Problems with site and email out fails.''',
            required = True,
            )
    """

    general_email = zope.schema.TextLine(
            title = u'General Contact Email Recipient',
            description = u'''All general emails will come here''',
            required = True,
            )

    fees_email = zope.schema.TextLine(
            title = u'Fees and Transactions Email Recipient',
            description = u'''Member fees and transaction failures, etc''',
            required = True,
            )
