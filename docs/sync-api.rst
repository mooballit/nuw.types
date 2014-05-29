======================
Sync API Documentation
======================

This document describes the API that is used to syncronise data between the new NUW site and the NUW Information Hub.

Calling the API
===============

The API is called using the HTTP protocol using either GET or POST requests. The GET request would be used for read only calls and the POST request for calls that require
data to be changed.

API Location
------------

The base URL for the API will be located under a separate subdomain (ex. http://api.domain.com). This enables us to easily separate the main website from the API or even have it located
at a completely different IP without having to do major configuration changes. It also gives us a simple way to assign an SSL certificate for the API and not the main site.

Selecting the API Call
----------------------

The API Call to be executed is determined by the URL path after the domain name. So a call to an API Call named *explode* would look like:

`http://api.domain.com/explode/?api_key=12345`

Providing Attributes
--------------------

There are two ways of providing attributes to the API Calls. The first is to just pass them in the URL using standard GET type encoding and the second is to pass it as an XML structure
in the body of the HTTP request. For the API Calls that require GET requests, passing the attributes in the URL is the only option. But for POST ones it can be either, depending on the
the data type. Simple attributes that can be represented using only a name and a value are passed in the URL and more complex structures like the list of changed items are passed as
XML Structures in the body.

All API Calls require the api_key attribute to be passed in the URL.

The API Key
-----------

The API Key is an attribute that has to be passed to the API Calls so the API can determine if the caller is authorised to use it or not. It has been decided that
the key should be a previously agreed upon static key which rarely changes (unless the security of the system has been compromised). This should be a complex string
of characters that is hard for a human to remember and contain many special characters to increse its entropy.

The API Calls
=============

Here follows a description of each of the API Calls and their attributes.

.. _getdata:

get_data
--------

.. autoclass:: nuw.types.api.tool.GetData
    :members:


.. _getchanges:

get_changes
-----------

.. autoclass:: nuw.types.api.tool.GetChanges
    :members:

.. _clear_changes:

clear_changes
-------------

.. autoclass:: nuw.types.api.tool.ClearChanges
    :members:

get_data
--------

.. autoclass:: nuw.types.api.tool.GetData
    :members:

push_changes
------------

TODO: returns list of assigned ids (for add records)

This is a POST call that allows the caller to push changes to the website database. The changes attribute is in the same format as the data returned by the :ref:`get_changes <getchanges>` call
except the datetime of the actual change is not needed. Once the API has received and updated the database with the changes it will return a success or failure message. It is very important
that the caller does not mark the changes as synced until the returned success message has been received. If anything goes wrong along the way or a failure message is received, both
ends need to do a rollback and another attempt should be made. This to ensure no race conditions happen and the two ends fall out of sync.

========== ============================================ =============
Attribute  Type                                         Description
========== ============================================ =============
api_key    STRING                                       The api key
changes    List of :ref:`Change Items <changeitem>`     The changes
========== ============================================ =============

.. _datatypes:

Data Types
==========

IDs
---

Since the two ends of the API each have their own internal schema for storing the different types it cannot be assumed that the same objects will have the same IDs.
Therefore it is imporant that both the website and information hub ids are passed along with the object data.

The website database will store the ids as long integers and the Infrmation HUB stores them as a UUID string.

Foreign Keys
------------

In the passed and returned data some object might refer to other objects. In the databases these references are stored using the ID of the refered object.
However, since the two sides of the API store ID differently, references to other objects will be stored using only the HUB ID.

Reference Checking
------------------
Each type which references other rows uses a decorator to check if the
given data already exists in our database:


.. automodule:: nuw.types.base
    :members: check_references

Date times
----------

Datetimes should be stored as UTC to simplify timezone handling and be encoded as ISO 8601 strings with year, month, day, hour, minute and second.

.. rubric:: Example:

2012-03-16T09:56:00Z

Phone Numbers
-------------

Phone numbers should be stored in their international format. This is done in case we have numbers from other countries. ( This might be discussed tho )

The stored phone number string should only contain digits and follow the following format:

``CCAAxxxxxxxx``

Where CC is the country code, AA is the area code ( could be one to many digits, depeding on the country, and will not include the leading zero ) and the rest is the subscriber number.

.. rubric:: Example:

Mooball's number 07 3843 0516 would be stored as ``61738430516``

Email Addresses
---------------

These should be stored in the standard ITU-T E.123 format for Email addresses (user@domain.tld).

.. rubric:: Example:

``bilbo@bagend.com``

.. _changeitem:

Change Item
-----------

This stores the data of the changed objects and is stored as a ``change`` XML-element with the following attributes:

========== ======================== ==========================================================================
Attribute  Type                     Description
========== ======================== ==========================================================================
action     ENUM (add,update,delete) What sort of change
otype      STRING                   The type of the changed object
web-id     INT                      The id of the object within the website's database
hub-id     INT                      The id of the object within the NUW Information Hub
changed    DATETIME                 The time and date of the actual change (optional in the push_changes call)
<obj-data> ?                        The data of the changed object (not needed when otype is delete)
========== ======================== ==========================================================================

.. rubric:: Example:

``<change action="update" otype="person" web-id="123" changed="2012-01-01T10:04:03Z" firstname="Bilbo" lastname="Baggins" address="Bag End" ......... />``


Success/Failure Message
-----------------------

This stores the result of an API operation. It is stored as an ``result`` XML-element with the following attributes:

========= ====================== =================================
Attribute Type                   Description
========= ====================== =================================
status    ENUM (success,failure) Did the operation succeed or not?
code      INT                    On failure this is the error code
========= ====================== =================================

The result XML-element wraps a message letting the caller know what happened. In the case of failures, this message is a string version of the error linked to the error code.

.. rubric:: Example:

``<result status="success">All synced</result>``

or

``<result status="failure" code="123">There was some clink on the stuffer expander</result>``

Other issues
============

Change Collissions
------------------

It has been established that the Information Hub has preference over the website database. So if we ever run into a situation where an item has been updates at both ends the update
to the item in the Information Hub will override the other changes.

Stale Changes
-------------

It might occur that change records never get cleared in which case, someone needs to be notified of that fact. Therefore we would need a cron job to check if the age of a change record is
above a set threshold at which case it would alert an admin to administer some manual action.


Events
======

Events trigger the creation of change items.

.. autointerface:: nuw.types.api.change.IChange
    :members:
