from Products.CMFCore.utils import getToolByName
from Products.CMFDefault.utils import EmailAddressInvalid
from Products.CMFDefault.utils import checkEmailAddress
from five import grok
from nuw.types import Base
from nuw.types.base import ContactDetailsMixin
from nuw.types.base import IContactDetails
from nuw.types.base import IMappedTable
from nuw.types.base import INUWItem
from nuw.types.base import NUWItem
from nuw.types.base import VocabMixin
from nuw.types.base import XMLBase
from nuw.types.base import apply_data
from nuw.types.base import create_or_get_typehelper
from nuw.types.base import vocabulary_factory
from sqlalchemy import Column, Integer, String, Sequence, DateTime,\
        Boolean, ForeignKey, Unicode, UnicodeText, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, backref
from z3c.saconfig import named_scoped_session
from zope.schema.interfaces import IFromUnicode, IDatetime
from zope.schema.vocabulary import SimpleVocabulary
import datetime
import zope.interface
import zope
from zope.lifecycleevent import ObjectModifiedEvent

Session = named_scoped_session('nuw.types')

def get_user_person( context ):
    '''
    Returns the person object for the current user. Returns None if no person can be found
    '''
    plone_user = getToolByName( context, 'portal_membership' ).getAuthenticatedMember()

    if plone_user.getUserName() != 'Anonymous User':
        sess = Session()

        return sess.query( Person ).filter( User.name == plone_user.getUserName(), Person.user_id == User.id ).first()

class EmailExists( zope.schema.ValidationError ):
    __doc__ = 'The entered email address is already in use by another member. Please use a different one.'

    def __str__( self ):
        return self.__doc__

def email_exists( email, personid = '' ):
    '''
        Returns true is email address is assigned to any person, except for the
        person requesting the change.
    '''
    email = unicode( str(email).lower().strip() )
    sess = Session()
    query = sess.query( User ).filter( func.lower(User.name) == email )

    return query.count() > 0

def change_person_email( context, person, new_email ):
    '''
        Takes an IPerson object and the new email as a string.
        Updates the email in subscribed active campaign lists
    '''
    if IPerson( person ).email == new_email:
        # Email is the same, no update required (you silly person!)
        return

    # Change person's username (if user is setup)
    if person.user:
        person.user.name = new_email

    actool = getToolByName( context, 'portal_activecampaign' )

    # Lookup the subscriber via old email
    sub = actool.get_subscriber_by( person.email )

    if sub:
        # Person has subscriptions so do change
        actool.edit_subscriber_email( sub, new_email )

class DateTimeFromUnicode(grok.Adapter):
    grok.provides(IFromUnicode)
    grok.context(IDatetime)

    format = '%Y-%m-%dT%H:%M:%S'

    def fromUnicode(self, value):
        d = datetime.datetime.strptime(value[:19], self.format)
        self.context.validate(d)
        return d


class IPerson(INUWItem, IContactDetails):
    """Person which holds personal and address information."""

    personid = zope.schema.TextLine(
        title=u'GUID',
    )

    title = zope.schema.TextLine(
        title=u'Title',
        required=False,
    )

    firstname = zope.schema.TextLine(
        title=u'First Name',
        required=False,
    )

    lastname = zope.schema.TextLine(
        title=u'Last Name',
        required=False,
    )

    type = zope.schema.Choice(
        title=u'Type',
        vocabulary='persontypes',
        required=False,
    )

    # also defined in browser.join.py
    gender = zope.schema.Choice(
        title=u'Gender',
        values=[u'Male', u'Female', u'Unknown'],
        required=False,
    )

    preferredname = zope.schema.TextLine(
        title=u'Preferred Name',
        required=False,
    )

    homeaddress1 = zope.schema.Text(
        title=u'Home Address Line 1',
        required=False,
    )

    homeaddress2 = zope.schema.Text(
        title=u'Home Address Line 2',
        required=False,
    )

    homesuburb = zope.schema.TextLine(
        title=u'Suburb',
        required=False,
    )

    homestate = zope.schema.TextLine(
        title=u'State',
        required=False,
    )

    homepostcode = zope.schema.TextLine(
        title=u'Postcode',
        required=False,
    )

    mobile = zope.schema.TextLine(
        title=u'Mobile Phone',
        required=False,
    )

    home = zope.schema.TextLine(
        title=u'Home Phone',
        required=False,
    )

    work = zope.schema.TextLine(
        title=u'Work Phone',
        required=False,
    )

    email = zope.schema.TextLine(
        title=u'E-mail',
        required=False,
    )

    dob = zope.schema.Datetime(
        title=u'Date of Birth',
        required=False,
    )

    status = zope.schema.TextLine(
        title=u'Financial Status',
        required=False,
    )

    webstatus = zope.schema.TextLine(
        title=u'Website Status',
        required=False,
    )

    # XXX enum - should be Table
    activity = zope.schema.TextLine(
        title=u'Activity',
        required=False,
    )

    employeeid = zope.schema.TextLine(
        title=u'Employee ID',
        required=False,
    )

    employmenttype = zope.schema.Choice(
        title=u'Employment Type',
        vocabulary='employment',
        required=False,
    )

    shift = zope.schema.TextLine(
        title=u'Shift',
        required=False,
    )

    locationcode = zope.schema.TextLine(
        title=u'Location Code',
        required=False,
    )

    languagemain = zope.schema.Choice(
        title=u'Main Language',
        vocabulary='languages',
        required=False,
    )

    languagetranslator = zope.schema.Choice(
        title=u'Can Translate..',
        vocabulary='languages',
        required=False,
    )

    languageneed = zope.schema.Choice(
        title=u'Needs Translation..',
        vocabulary='languages',
        required=False,
    )

    # TODO: This seems to be specified by Lucas, but the model (Labour
    # hire groups) suggests otherwise
    agency = zope.schema.TextLine(
        title=u'Agency',
        required=False,
    )

    socialgroup = zope.schema.TextLine(
        title=u'Socialgroup',
        required=False,
    )

    custom1 = zope.schema.TextLine(
        title=u'Custom 1',
        required=False,
    )

    custom2 = zope.schema.TextLine(
        title=u'Custom 2',
        required=False,
    )

    custom3 = zope.schema.TextLine(
        title=u'Custom 3',
        required=False,
    )

    custom4 = zope.schema.TextLine(
        title=u'Custom 4',
        required=False,
    )

    custom5 = zope.schema.TextLine(
        title=u'Custom 5',
        required=False,
    )

    custom6 = zope.schema.TextLine(
        title=u'Custom 6',
        required=False,
    )

    custom7 = zope.schema.TextLine(
        title=u'Custom 7',
        required=False,
    )

    custom8 = zope.schema.TextLine(
        title=u'Custom 8',
        required=False,
    )

    custom9 = zope.schema.TextLine(
        title=u'Custom 9',
        required=False,
    )

    custom10 = zope.schema.TextLine(
        title=u'Custom 10',
        required=False,
    )

    issues = zope.schema.TextLine(
        title=u'Issues & Objections',
        required=False,
    )


def employment_vocabulary(context):
    values = [(u'permanent', u'Permanent'),
              (u'part time', u'Part Time'),
              (u'casual', u'Casual'),
              (u'agency', u'Agency')
             ]
    terms = [SimpleVocabulary.createTerm(x, x, y) for x, y in values]
    return SimpleVocabulary(terms)

grok.global_utility(employment_vocabulary,
                    provides=zope.schema.interfaces.IVocabularyFactory,
                    name='employment', direct=True)

def languages_vocabulary(context):
    values = [(u'', ''),
              (u'South Slavic', u'South Slavic'),
              (u'Spanish', u'Spanish'),
              (u'Swedish', u'Swedish'),
              (u'Swahili', u'Swahili'),
              (u'Tagalog (Filipino)', u'Tagalog (Filipino)'),
              (u'Tai', u'Tai'),
              (u'Tajik', u'Tajik'),
              (u'Tamil', u'Tamil'),
              (u'Tatar', u'Tatar'),
              (u'Telugu', u'Telugu'),
              (u'Teochew', u'Teochew'),
              (u'Tetum', u'Tetum'),
              (u'Thai', u'Thai'),
              (u'Tho', u'Tho'),
              (u'Tigrinya', u'Tigrinya'),
              (u'Timorese', u'Timorese'),
              (u'Tiwi', u'Tiwi'),
              (u'Tok Pisin', u'Tok Pisin'),
              (u'Tongan', u'Tongan'),
              (u'Torres Strait Creole (Broken)', u'Torres Strait Creole (Broken)'),
              (u'Tulu', u'Tulu'),
              (u'Turkish', u'Turkish'),
              (u'Tuvaluan', u'Tuvaluan'),
              (u'Ukrainian', u'Ukrainian'),
              (u'Urdu', u'Urdu'),
              (u'Vietnamese', u'Vietnamese'),
              (u'Walmajarri (Walmadjari)', u'Walmajarri (Walmadjari)'),
              (u'Warumungu (Warumunga)', u'Warumungu (Warumunga)'),
              (u'Welsh', u'Welsh'),
              (u'West Slavic', u'West Slavic'),
              (u'Wik-Mungkan', u'Wik-Mungkan'),
              (u'Wu', u'Wu'),
              (u'Yankunytjatjara', u'Yankunytjatjara'),
              (u'Yanyuwa (Anula)', u'Yanyuwa (Anula)'),
              (u'Yao', u'Yao'),
              (u'Yiddish', u'Yiddish'),
              (u'Yindjibarndi', u'Yindjibarndi'),
              (u'Yoruba', u'Yoruba'),
              (u'Yulparija', u'Yulparija'),
              (u'Zulu', u'Zulu'),
              (u'Acholi', u'Acholi'),
              (u'Adnymathanha (Yura Ngawarla)', u'Adnymathanha (Yura Ngawarla)'),
              (u'Afrikaans', u'Afrikaans'),
              (u'Ainu', u'Ainu'),
              (u'Akan', u'Akan'),
              (u'Albanian', u'Albanian'),
              (u'Alyawarr (Alyawarra)', u'Alyawarr (Alyawarra)'),
              (u'Amharic', u'Amharic'),
              (u'Anindilyakwa', u'Anindilyakwa'),
              (u'Anmatyerr (Anmatyirra)', u'Anmatyerr (Anmatyirra)'),
              (u'Arabana (Arabuna)', u'Arabana (Arabuna)'),
              (u'Arabic', u'Arabic'),
              (u'Aramaic', u'Aramaic'),
              (u'Aromunian (Macedo-Romanian)', u'Aromunian (Macedo-Romanian)'),
              (u'Arrernte (Aranda)', u'Arrernte (Aranda)'),
              (u'Asante', u'Asante'),
              (u'Assamese', u'Assamese'),
              (u'Assyrian', u'Assyrian'),
              (u'Auslan', u'Auslan'),
              (u'Azeri', u'Azeri'),
              (u'Balinese', u'Balinese'),
              (u'Balochi', u'Balochi'),
              (u'Balti', u'Balti'),
              (u'Baltic', u'Baltic'),
              (u'Bardi', u'Bardi'),
              (u'Basque', u'Basque'),
              (u'Belorussian', u'Belorussian'),
              (u'Bemba', u'Bemba'),
              (u'Bengali', u'Bengali'),
              (u'Bhotia', u'Bhotia'),
              (u'Bikol', u'Bikol'),
              (u'Bisaya', u'Bisaya'),
              (u'Bislama', u'Bislama'),
              (u'Bosnian', u'Bosnian'),
              (u'Brahui', u'Brahui'),
              (u'Breton', u'Breton'),
              (u'Bulgarian', u'Bulgarian'),
              (u'Bunuba (Bunaba)', u'Bunuba (Bunaba)'),
              (u'Burarra', u'Burarra'),
              (u'Burmese', u'Burmese'),
              (u'Burushaski', u'Burushaski'),
              (u'Buyi', u'Buyi'),
              (u'Cantonese', u'Cantonese'),
              (u'Catalan', u'Catalan'),
              (u'Cebuano', u'Cebuano'),
              (u'Celtic', u'Celtic'),
              (u'Chang Chow', u'Chang Chow'),
              (u'Chinese', u'Chinese'),
              (u'Cornish', u'Cornish'),
              (u'Crioulo', u'Crioulo'),
              (u'Croatian', u'Croatian'),
              (u'Czech', u'Czech'),
              (u"Dhay'yi", u"Dhay'yi"),
              (u'Dhaangu', u'Dhaangu'),
              (u'Dhuwal-Dhuwala', u'Dhuwal-Dhuwala'),
              (u'Djinang', u'Djinang'),
              (u'East Slavic', u'East Slavic'),
              (u'Estonian', u'Estonian'),
              (u'Faeroese', u'Faeroese'),
              (u'Fijian', u'Fijian'),
              (u'Finnic', u'Finnic'),
              (u'Finnish', u'Finnish'),
              (u'French', u'French'),
              (u'Frisian', u'Frisian'),
              (u'Friulian', u'Friulian'),
              (u'Gaelic (Scotland)', u'Gaelic (Scotland)'),
              (u'Galician', u'Galician'),
              (u'Georgian', u'Georgian'),
              (u'German', u'German'),
              (u'Gilbertese', u'Gilbertese'),
              (u'Greek', u'Greek'),
              (u'Gugu Yalanji', u'Gugu Yalanji'),
              (u'Gujarati', u'Gujarati'),
              (u'Guugu Yimidhirr', u'Guugu Yimidhirr'),
              (u'Hakka', u'Hakka'),
              (u'Hawaiian', u'Hawaiian'),
              (u'Hebrew', u'Hebrew'),
              (u'Hindi', u'Hindi'),
              (u'Hmon', u'Hmon'),
              (u'Hmong-Mien', u'Hmong-Mien'),
              (u'Hokkien', u'Hokkien'),
              (u'Hunan', u'Hunan'),
              (u'Hungarian', u'Hungarian'),
              (u'Iberian Romance', u'Iberian Romance'),
              (u'Icelandic', u'Icelandic'),
              (u'Indonesian', u'Indonesian'),
              (u'Iranic', u'Iranic'),
              (u'Irish', u'Irish'),
              (u'Italian', u'Italian'),
              (u'Japanese', u'Japanese'),
              (u'Jaru (Djaru)', u'Jaru (Djaru)'),
              (u'Jui', u'Jui'),
              (u'Kalaw Lagaw Ya (Kalaw Kawa Ya)', u'Kalaw Lagaw Ya (Kalaw Kawa Ya)'),
              (u'Kan', u'Kan'),
              (u'Kannada', u'Kannada'),
              (u'Karelian', u'Karelian'),
              (u'Karrwa (Garrwa, Garawa)', u'Karrwa (Garrwa, Garawa)'),
              (u'Kashmiri', u'Kashmiri'),
              (u'Khasi', u'Khasi'),
              (u'Khmer', u'Khmer'),
              (u'Khmu', u'Khmu'),
              (u'Kija (Gidya)', u'Kija (Gidya)'),
              (u'Konkani', u'Konkani'),
              (u'Korean', u'Korean'),
              (u'Kukatha (Kokatha, Gugada)', u'Kukatha (Kokatha, Gugada)'),
              (u'Kukatja (Gugaja)', u'Kukatja (Gugaja)'),
              (u'Kunwinjku (Gunwinggu)', u'Kunwinjku (Gunwinggu)'),
              (u'Kurdish', u'Kurdish'),
              (u"Kuuku-Ya'u", u"Kuuku-Ya'u"),
              (u'Kuurinji (Gurindji)', u'Kuurinji (Gurindji)'),
              (u'Ladino', u'Ladino'),
              (u'Lao', u'Lao'),
              (u'Lapp', u'Lapp'),
              (u'Latin', u'Latin'),
              (u'Latvian', u'Latvian'),
              (u'Lebanese', u'Lebanese'),
              (u'Letzeburgish', u'Letzeburgish'),
              (u'Lisu', u'Lisu'),
              (u'Lithuanian', u'Lithuanian'),
              (u'Ludic', u'Ludic'),
              (u'Macedonian', u'Macedonian'),
              (u'Makaton', u'Makaton'),
              (u'Malagasy', u'Malagasy'),
              (u'Malay', u'Malay'),
              (u'Malayalam', u'Malayalam'),
              (u'Maltese', u'Maltese'),
              (u'Mandarin', u'Mandarin'),
              (u'Manx', u'Manx'),
              (u'Maori (Cook Island)', u'Maori (Cook Island)'),
              (u'Maori (New Zealand)', u'Maori (New Zealand)'),
              (u'Marathi', u'Marathi'),
              (u'Mauritian Creole', u'Mauritian Creole'),
              (u'Meryam Mir', u'Meryam Mir'),
              (u'Mien', u'Mien'),
              (u'Miriwoong', u'Miriwoong'),
              (u'Mon-Khmer', u'Mon-Khmer'),
              (u'Motu', u'Motu'),
              (u'Muong', u'Muong'),
              (u'Murrinh-Patha', u'Murrinh-Patha'),
              (u'Mutpurra (Mudburra)', u'Mutpurra (Mudburra)'),
              (u'Nauruan', u'Nauruan'),
              (u'Nepali', u'Nepali'),
              (u'Netherlandic', u'Netherlandic'),
              (u'Ngaatjatjara', u'Ngaatjatjara'),
              (u'Ngangkikurungurr', u'Ngangkikurungurr'),
              (u'Ngarluma', u'Ngarluma'),
              (u'Niue', u'Niue'),
              (u'Norwegian', u'Norwegian'),
              (u'Nunggubuyu', u'Nunggubuyu'),
              (u'Nyangumarta', u'Nyangumarta'),
              (u'Nyungar (Noongar)', u'Nyungar (Noongar)'),
              (u'Oromo', u'Oromo'),
              (u'Ossetic', u'Ossetic'),
              (u'Papuan', u'Papuan'),
              (u'Pashto', u'Pashto'),
              (u'Persian', u'Persian'),
              (u'Pho', u'Pho'),
              (u'Pintupi', u'Pintupi'),
              (u'Pitcairnese, Solomon Islands Pidgin (Pijin)', u'Pitcairnese, Solomon Islands Pidgin (Pijin)'),
              (u'Pitjantjatjara', u'Pitjantjatjara'),
              (u'Polish', u'Polish'),
              (u'Portuguese', u'Portuguese'),
              (u'Punjabi', u'Punjabi'),
              (u'Rajasthani', u'Rajasthani'),
              (u'Rawang', u'Rawang'),
              (u'Rembarrnga', u'Rembarrnga'),
              (u'Riff', u'Riff'),
              (u'Ritharrngu', u'Ritharrngu'),
              (u'Romanian', u'Romanian'),
              (u'Romansch', u'Romansch'),
              (u'Romany', u'Romany'),
              (u'Samoan', u'Samoan'),
              (u'Scandinavian', u'Scandinavian'),
              (u'Serbian', u'Serbian'),
              (u'Shluh', u'Shluh'),
              (u'Shona', u'Shona'),
              (u'Sindhi', u'Sindhi'),
              (u'Sinhalese', u'Sinhalese'),
              (u'Slovak', u'Slovak'),
              (u'Slovene', u'Slovene'),
              (u'Somali', u'Somali'),
             ]
    terms = [SimpleVocabulary.createTerm(x, x, y) for x, y in values]
    return SimpleVocabulary(terms)

grok.global_utility(languages_vocabulary,
                    provides=zope.schema.interfaces.IVocabularyFactory,
                    name='languages', direct=True)


class PersonType(Base, VocabMixin):
    __tablename__ = 'persontype'

    id = Column(Integer, Sequence('persontype_id'), primary_key=True)


def add_or_get_persontype(token, name=None):
    return create_or_get_typehelper(token, PersonType, name)

personTypeFactory = zope.component.factory.Factory(add_or_get_persontype)
grok.global_utility(personTypeFactory, name='person.type', direct=True)


def persontype_vocabulary(context):
    return vocabulary_factory(PersonType)

grok.global_utility(persontype_vocabulary,
                    provides=zope.schema.interfaces.IVocabularyFactory,
                    name='persontypes', direct=True)


class Person(Base, ContactDetailsMixin, NUWItem):
    zope.interface.implements(IPerson)
    __tablename__ = 'person'

    id = Column(Integer, Sequence('person_id'), primary_key=True)
    personid = Column(UUID, unique=True)
    nuw_number = Column(Integer)
    user_id = Column(Integer, ForeignKey('user.id'))

    title = Column(String)
    firstname = Column(Unicode)
    lastname = Column(Unicode)
    persontype_id = Column(Integer, ForeignKey('persontype.id'))

    gender = Column(String)
    preferredname = Column(Unicode)
    homeaddress1 = Column(UnicodeText)
    homeaddress2 = Column(UnicodeText)
    homesuburb = Column(Unicode)
    homestate = Column(Unicode)
    homepostcode = Column(String)
    mobile = Column(String)
    home = Column(String)
    work = Column(String)
    email = Column(Unicode)
    dob = Column(DateTime)
    status = Column(String)
    activity = Column(String)  # XXX should be table
    webstatus = Column(String)  # XXX should be table

    employeeid = Column(String)
    employmenttype = Column(String)
    shift = Column(Unicode)
    locationcode = Column(String)
    agency = Column(Unicode)
    socialgroup = Column(String)

    is_subscribed = Column(Boolean)
    languagemain = Column(String)
    languagetranslator = Column(String)
    languageneed = Column(String)
    issues = Column(String)
    custom1 = Column(String)
    custom2 = Column(String)
    custom3 = Column(String)
    custom4 = Column(String)
    custom5 = Column(String)
    custom6 = Column(String)
    custom7 = Column(String)
    custom8 = Column(String)
    custom9 = Column(String)
    custom10 = Column(String)
    user = relationship('User', uselist = False, backref = backref('person', uselist = False))
    type = relationship(PersonType,
                        backref=backref('persontype_id'))

    @property
    def webstatuses( self ):
        ''' Returns a list of webstatuses assigned to the person '''
        return self.webstatus is not None and self.webstatus.split( ' ' ) or []

    def __init__(self, personid, **kwargs):
        self.personid = personid
        apply_data(self, IPerson, kwargs)

    def has_login(self):
        """ Returns True, if:

        * the person is associated with a user
        * the user has `name` and `password` set and
        * the users `name` is a syntactic valid e-mail address
        """
        result = False
        if self.user is not None:
            valid_email = True
            try:
                checkEmailAddress(self.user.name)
            except EmailAddressInvalid:
                valid_email = False
            result = valid_email and self.user.password
        return result


personFactory = zope.component.factory.Factory(Person)
grok.global_utility(personFactory, name='person', direct=True)
grok.global_utility(Person, provides=IMappedTable, name='person', direct=True)


class XML(XMLBase):
    grok.context(IPerson)
    grok.require('zope2.Public')


class User(Base):
    __tablename__ = 'user'

    id = Column(Integer, Sequence('user_id'), primary_key=True)
    name = Column(String(40), nullable=False, index=True)
    password = Column(String(40), nullable=False)
