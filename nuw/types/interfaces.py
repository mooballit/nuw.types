# Copyright (c) 2012 Mooball IT
# See also LICENSE.txt
import zope.interface


class IUnionRep(zope.interface.Interface):
    """Marker interface to distinguish portals from each other.

    The IUnionRep provided portal has a slightly different
    authentication.
    """


class IActivationContext(zope.interface.Interface):
    """Marker interface in order to call activation views on a different
       context than the siteroot.
    """

class IJoinContext( zope.interface.Interface ):
    '''
    Marker interface to add to any folders where people should be albe to
    access the join form
    '''
    pass
