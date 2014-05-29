from Products.CMFPlone.tests.utils import MockMailHost
from Products.MailHost.interfaces import IMailHost
from Testing import ZopeTestCase as ztc
from nuw.types import Base
from nuw.types.setuphandlers import bootstrap_data
from plone.app.testing import PLONE_FIXTURE
from plone.app.testing import PloneSandboxLayer
from plone.app.testing import applyProfile
from plone.app.testing.layers import FunctionalTesting
from plone.app.testing.layers import IntegrationTesting
from z3c.saconfig import EngineFactory
from z3c.saconfig import GloballyScopedSession
from z3c.saconfig import named_scoped_session
from z3c.saconfig.interfaces import IScopedSession
from zope.configuration import xmlconfig
import nuw.types
import os
import transaction
import zope.component


Session = named_scoped_session('nuw.types')


class NUWTypesBase(PloneSandboxLayer):
    defaultBases = (PLONE_FIXTURE,)

    def setUpZope(self, app, configurationContext):
        # load ZCML
        xmlconfig.file('configure.zcml', nuw.types,
                       context=configurationContext)

        engineurl = os.environ.get('sqlalchemy.url')
        assert engineurl is not None

        factory = EngineFactory(engineurl)
        engine = factory()
        Base.metadata.bind = engine
        utility = GloballyScopedSession(
                  bind=engine)

        zope.component.provideUtility(utility, provides=IScopedSession,
                name="nuw.types")
        zope.component.provideUtility(utility, provides=IScopedSession,
                name="nuw.types.auth")
        ztc.utils.setupCoreSessions(app)
        transaction.commit()

    def setUpPloneSite(self, portal):
        # install into the Plone site
        Base.metadata.create_all()
        applyProfile(portal, 'nuw.types:default')

        # Set up a mock mailhost
        portal._original_MailHost = portal.MailHost
        portal.MailHost = mailhost = MockMailHost('MailHost')
        sm = zope.component.getSiteManager(context=portal)
        sm.unregisterUtility(provided=IMailHost)
        sm.registerUtility(mailhost, provided=IMailHost)
        # We need to fake a valid mail setup
        portal.email_from_address = "portal@plone.test"

    def tearDownZope(self, app):
        Base.metadata.drop_all()
        transaction.commit()


NUWTYPES_FIXTURE = NUWTypesBase()
NUWTYPES_INTEGRATION_TESTING = IntegrationTesting(
    bases=(NUWTYPES_FIXTURE,), name="NUWTypesBase:Integration")
NUWTYPES_FUNCTIONAL_TESTING = FunctionalTesting(
    bases=(NUWTYPES_FIXTURE,), name="NUWTypesBase:Functional")


class SQLIntegration(PloneSandboxLayer):
    defaultBases = (NUWTYPES_FIXTURE, )

    def testSetUp(self):
        session = Session()
        Base.metadata.create_all(session.bind)
        bootstrap_data()

    def testTearDown(self):
        transaction.abort()
        Base.metadata.drop_all()


SQL_INTEGRATION = SQLIntegration()
NUWTYPES_SQLINTEGRATION_TESTING = FunctionalTesting(
    bases=(SQL_INTEGRATION,), name="NUWTypesBase:SQLIntegration")


def debug_contents(bcontents):
    """
    Writes given (test-) browser contents to /tmp/debug.html.
    """
    with open('/tmp/debug.html', 'w') as f:
        f.write(bcontents)


def get_testdata(filename):
    """
    Simply reads data from the given filename and returns it.
    """
    fp = os.path.join(os.path.dirname(__file__), 'tests', 'testdata',
                      filename)
    with open(fp, 'r') as f:
        return f.read()
