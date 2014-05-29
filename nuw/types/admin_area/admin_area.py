from five import grok
from zope.interface import Interface

from Products.CMFPlone.PloneBatch import Batch, opt, calculate_pagenumber
from Products.CMFPlone.PloneBatch import calculate_pagerange
from Products.CMFPlone.PloneBatch import calculate_quantum_leap_gap
from Products.CMFPlone.PloneBatch import calculate_leapback
from Products.CMFPlone.PloneBatch import calculate_leapforward
from ExtensionClass import Base

grok.templatedir( 'templates' )
permission = 'cmf.ManagePortal'


class AdminArea(grok.View):
    '''
    Add 'configlets' here to populate the admin area.
    '''
    grok.context(Interface)
    grok.name('admin-area')
    grok.require(permission)

    categories = ({'title': 'Member Administration',
                    'configlets': (
                        {'title': 'Member Search', 'url': '@@member-search'},
                        {'title': 'Upload a Splash Image', 'url': '@@splash_upload'},
                        {'title': 'Administrator Emails', 'url': '@@admin-emails'},
                    )},
                  {'title': 'Payments',
                    'configlets': (
                        {'title': 'Transactions', 'url': '@@member-trans'},
                        {'title': 'Payment Methods', 'url': '@@member-methods'},
                        {'title': 'Shop Orders', 'url': '@@manage-orders'},
                        {'title': 'Join Form Recurring Charges', 'url': '@@recur-charges'},
                        {'title': 'Recurring Payments', 'url': '@@recurring-payments'},
                    )},
                )


class LazyPrevBatch(Base):
    def __of__(self, parent):
        return LargeBatch(parent._sequence, parent.sequence_length, parent._size,
                     parent.first - parent._size + parent.overlap, 0,
                     parent.orphan, parent.overlap)


class LazyNextBatch(Base):
    def __of__(self, parent):
        if parent.end >= (parent.last + parent.size):
            return None
        return LargeBatch(parent._sequence, parent.sequence_length, parent._size,
                     parent.end - parent.overlap, 0,
                     parent.orphan, parent.overlap)


class LargeBatch(Batch):
    sequence_length = 0
    previous = LazyPrevBatch()
    next = LazyNextBatch()

    def __init__(self, sequence, sequence_length, size, start=0, end=0,
            orphan=0, overlap=0, pagerange=7, quantumleap=0,
            b_start_str='b_start'):
        """ Encapsulate sequence in batches of size
        Meant for very large batching, as in > 2'000 queries. 'sequence' will be
        a 'size' sized snippet of the original query, usually a snippet from
        'start' to 'start + size' (i.e. query[start:start+size]).
        sequence        - the data to batch. Shortened length of query.
        sequence_length - total length of the query.
        size            - the number of items in each batch. This will be
                            computed if left out.
        start           - the first element of sequence to include in batch
                            (0-index)
        end             - the last element of sequence to include in batch
                            (0-index, optional)
        orphan          - the next page will be combined with the current page
                            if it does not contain more than orphan elements
        overlap         - the number of overlapping elements in each batch
        pagerange       - the number of pages to display in the navigation
        quantumleap     - 0 or 1 to indicate if bigger increments should be
                            used in the navigation list for big results.
        b_start_str     - the request variable used for start, default 'b_start'
        """
        start = start + 1
        self._sequence = sequence
        self._size = size
        self.sequence_length = sequence_length

        start, end, sz = opt(start, end, size, orphan, sequence_length)

        self.size = sz
        self.start = start
        self.end = end
        self.orphan = orphan
        self.overlap = overlap
        self.first = max(start - 1, 0)
        self.length = self.end - self.first

        self.b_start_str = b_start_str

        self.last = sequence_length - size

        # Set up next and previous
        if self.first == 0:
            self.previous = None

        # Set up the total number of pages
        self.numpages = calculate_pagenumber(self.sequence_length - self.orphan,
                self.size, self.overlap)

        # Set up the current page number
        self.pagenumber = calculate_pagenumber(self.start, self.size, self.overlap)

        # Set up pagerange for the navigation quick links
        self.pagerange, self.pagerangestart, self.pagerangeend = calculate_pagerange(self.pagenumber, self.numpages, pagerange)

        # Set up the lists for the navigation: 4 5 [6] 7 8
        #  navlist is the complete list, including pagenumber
        #  prevlist is the 4 5 in the example above
        #  nextlist is 7 8 in the example above
        self.navlist = self.prevlist = self.nextlist = []
        if self.pagerange and self.numpages >= 1:
            self.navlist = range(self.pagerangestart, self.pagerangeend)
            self.prevlist = range(self.pagerangestart, self.pagenumber)
            self.nextlist = range(self.pagenumber + 1, self.pagerangeend)

        # QuantumLeap - faster navigation for big result sets
        self.quantumleap = quantumleap
        self.leapback = self.leapforward = []
        if self.quantumleap:
            self.leapback = calculate_leapback(
                    self.pagenumber, self.numpages, self.pagerange)
            self.leapforward = calculate_leapforward(
                    self.pagenumber, self.numpages, self.pagerange)
