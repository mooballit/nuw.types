# Copyright (c) 2012 Mooball IT
# See also LICENSE.txt
from nuw.types.interfaces import IActivationContext
from nuw.types.testing import NUWTYPES_FUNCTIONAL_TESTING
from plone.testing import layered
from pyquery import PyQuery
from z3c.saconfig import named_scoped_session
import doctest
import nuw.types.browser.activation
import transaction
import unittest
import zope.interface


Session = named_scoped_session('nuw.types')


def setup_activation_folder(container):
    zope.interface.alsoProvides(container, IActivationContext)
    transaction.commit()


OPTIONFLAGS = doctest.NORMALIZE_WHITESPACE | doctest.ELLIPSIS
GLOBALS = dict(Session=Session, pyquery=PyQuery,
               setup_activation_folder=setup_activation_folder)
LAYEREDDOCFILES = [
    nuw.types.browser.activation,
]
DOCFILES = [
    nuw.types.base,
]


def test_suite():
    suite = unittest.TestSuite()
    suite.addTests([
        layered(doctest.DocTestSuite(
            docfile,
            globs=GLOBALS,
            optionflags=OPTIONFLAGS),
            layer=NUWTYPES_FUNCTIONAL_TESTING)
        for docfile in LAYEREDDOCFILES
    ])
    suite.addTests([
        doctest.DocTestSuite(
            docfile,
            globs=GLOBALS,
            optionflags=OPTIONFLAGS)
        for docfile in DOCFILES
    ])
    return suite
