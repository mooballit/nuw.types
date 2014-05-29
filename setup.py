from setuptools import setup, find_packages

version = '0.7.7-activation'
tests_require = ['plone.app.testing',
                 'mock>=1.0.1',
                 'testfixtures',
                ]


setup(name='nuw.types',
      version=version,
      description="NUW Content Types",
      long_description=open("README.txt").read(),
      # Get more strings from
      # http://pypi.python.org/pypi?%3Aaction=list_classifiers
      classifiers=[
        "Framework :: Plone",
        "Programming Language :: Python",
        "Topic :: Software Development :: Libraries :: Python Modules",
        ],
      keywords='',
      author='',
      author_email='',
      url='http://svn.plone.org/svn/collective/',
      license='gpl',
      packages=find_packages(exclude=['ez_setup']),
      namespace_packages=['nuw'],
      include_package_data=True,
      zip_safe=False,
      install_requires=[
          'Products.CMFPlone',
          'collective.z3cform.wizard',
          'collective.autopermission',
          'lxml',
          'mooball.plone.activecampaign>=0.3',
          'plone.app.dexterity',
          'plone.formwidget.autocomplete',
          'plone.resource',
          'psycopg2',
          'pyquery',
          'setuptools',
          'spreedly-core-python>=0.3',
          'sqlalchemy-migrate',
          'z3c.saconfig',
          'pcommerce.core>0.4',
          'pcommerce.shipment.parcel>0.1',
          'mooball.plone.spreedlycore>1.0',
          'z3c.jbot>=0.6.0',
          'z3c.traverser',
      ],
      entry_points="""
      # -*- Entry points: -*-
      [z3c.autoinclude.plugin]
      target = plone
      """,
      setup_requires=["PasteScript"],
      paster_plugins=["ZopeSkel"],
      extras_require=dict(tests=tests_require),
      )
