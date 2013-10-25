The following instructions can be ignored when deploying to a staging
or production environment, but may be helpful to a developer working
on the project or running automated tests.

Session configuration
---------------------

By default, this project is configured to mark session cookies as secure. To
enable login over HTTP (e.g., when developing with Django's runserver), you
will need to override this in your ``localsettings.py``.  See the example
and comments in ``localsettings.py.dist``.

Test setup
----------


Database support
----------------
See DEPLOYNOTES for first time install

Sending Email
-------------

Django email configurations should not be needed in staging or production,
but to test sending emails on a development machine, you may need to add
settings for **EMAIL_HOST** and **SERVER_EMAIL**.

.. Note::
   As of 05/16/2013 due to a change on the SMTP server,
   it may not longer be possible to send emails from developer machines.


-----

Notes on included items
~~~~~~~~~~~~~~~~~~~~~~~



