.. _DEPLOYNOTES:

Installation
============

Software dependencies
---------------------

We recommend the use of `pip <http://pip.openplans.org/>`_ and `virtualenv
<http://virtualenv.openplans.org/>`_ for environment and dependency management
in this and other Python projects. If you don't have them installed we
recommend ``sudo easy_install pip`` and then ``sudo pip install virtualenv``.

Configure the environment
~~~~~~~~~~~~~~~~~~~~~~~~~

When first installing this project, you'll need to create a virtual environment
for it. The environment is just a directory. You can store it anywhere you
like; in this documentation it'll live right next to the source. For instance,
if the source is in ``/home/httpd/digitizedbooks/src``, consider creating an
environment in ``/home/httpd/digitizedbooks/env``. To create such an environment, su
into apache's user and::

  $ virtualenv --no-site-packages /home/httpd/digitizedbooks/env

This creates a new virtual environment in that directory. Source the activation
file to invoke the virtual environment (requires that you use the bash shell)::

  $ . /home/httpd/digitizedbooks/env/bin/activate

Once the environment has been activated inside a shell, Python programs
spawned from that shell will read their environment only from this
directory, not from the system-wide site packages. Installations will
correspondingly be installed into this environment.

.. Note::
  Installation instructions and upgrade notes below assume that
  you are already in an activated shell.

Install python dependencies
~~~~~~~~~~~~~~~~~~~~~~~~~~~

DigitizedBooks depends on several python libraries. The installation is mostly
automated, and will print status messages as packages are installed. If there
are any errors, pip should announce them very loudly.

To install python dependencies, cd into the repository checkout and::

  $ pip install -r pip-install-req.txt

If you are a developer or are installing to a continuous integration server
where you plan to run unit tests, code coverage reports, or build sphinx
documentation, you probably will also want to::

  $ pip install -r pip-dev-req.txt

After this step, your virtual environment should contain all of the
needed dependencies.


Install the application
-----------------------

Apache
~~~~~~

After installing dependencies, copy and edit the wsgi and apache
configuration files in src/apache inside the source code checkout. Both may
require some tweaking for paths and other system details.

Configuration
~~~~~~~~~~~~~

Configure application settings by copying ``localsettings.py.dist`` to
``localsettings.py`` and editing for local settings.

After configuring all settings, initialize the db with all needed
tables and initial data using::

  $ python manage.py syncdb
  $ python manage.py migrate

Running Tests
~~~~~~~~~~~~~
Download this set of test KDips to the project's root directory.
https://emory.box.com/s/q4086fm3gfrufv7ggqd90xj0fkolglou

Make sure its path is ``kdips``.

PID Manager
^^^^^^^^^^^
Make sure the user for PIDMAN has the following rights:
* Can add pid
* Can add target
* Can change pid
* Can change target

Background Jobs
~~~~~~~~~~~~~~~

``digitizedbooks/apps/publish/tasks.py`` uploads the packages to Box.com. It is started when a job is has a status of ``ready for hathi``.

Cron jobs
~~~~~~~~~

Session cleanup
^^^^^^^^^^^^^^^

The application uses database-backed sessions. Django recommends
periodically `clearing the session table <https://docs.djangoproject.com/en/1.3/topics/http/sessions/#clearing-the-session-table>`_
in this configuration. To do this, set up a cron job to run the following
command periodically from within the application's virtual environment::

  $ manage.py cleanup

This script removes any expired sessions from the database. We recommend
doing this about every week, though exact timing depends on usage patterns
and administrative discretion.

This command should be ran once a week to renew the Box API key so it does not expire.

  $ manage.py boxrefresh

This command should be ran nightly (or very early in the morning) to load any new KDips.

  $ manage.py loadKDips

This command should run daily to check if submitted KDips have been made live on HathiTrust

  $ manage.py check_ht

This command should run daily to check if submitted KDips that are live on HathiTrust have udated MARC records.

  $ manage.py check_al

This command should run daily to check if all the KDips in a submitted job are live on HathiTrust.

  $ manage.py update_job_status


Local Settings
==============
There a many special localsettings. See digizedbooks/localsettings.py.dst for notes.
