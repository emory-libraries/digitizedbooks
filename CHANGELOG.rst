Release 1.2
-----------
* Upgrade to Django 1.8
* As a DigitizedBooks user, I want to know that a volume has successfully been published at HathiTrust, and to free up disk space in the staging area, so that the PID Manager is updated with valid target URLs, and so that we free up expensive disk space.
* As a DigitizedBooks user, I want to be able to flag a Digitized Books record to show that it has been uploaded to the Internet Archive, and to note the IA record ID, so that I may perform such submissions "out of band" of the scope of the current DigitizedBooks release, keeping track of them now in case we advance to the 2.0 release.
* An application's copyright validation is able to handle "uncertain" dates in different date types or more accurate validation.
* As a library patron searching in EUCLID or DiscoverE, when i find a digitized volume  that has been published to HathiTrust, I want to see a clickable link in so I can view the item in HathiTrust.
* As a user I want to be able to verify a KDip's MARC record as been updated with the HathiTrust version so I don't have to check manually.

Release 1.0.5
-------------
* An application's copyright validation is able to handle "uncertain" dates and continuing resources
* An application's copyright validation is able to handle "uncertain" dates in different date types or more accurate validation.
* An application's copyright validation is able to handle "uncertain" dates found in enumcron for more accurate validation.
* As a DigitizedBooks user, I want to be able to write miscellaneous notes about a KDip, so that I can keep track of clean up tasks that I need to perform.

Release 1.0.4
-------------
* As an admin I want to want to receive an error report via email of validation failures so they can be fixed in a timely manner.
* When an admin process a job for Zephir, an email is sent to Zephir with information about the bundled marcxml file to meet Zephir's submission requirements.
* When an admin process a job for Zephir, all the marcxml records and bundled into one file to meet Zephir's submission requirements.
* When an admin processes a job for Zephir, bundled marcxml file will be ftp'd to Zephir so they can process it. 

Release 1.0.3
-------------
* As an user, I want a Job that is set to "Ready to Process" to continue processing in the background when I close the web browser, so that I have more freedom to do other things with my computer (such as close my laptop and take it home).

Release 1.0.2
-------------
* As an admin I want to see the number of volumes in a job so I can have an idea of how big it is.

* When an application finds that a KDip is invalid, it records all the reasons for failure, not just the first one encountered.

Release 1.0.1 - Hathi Trust Basic Ingest (Tweaked)
--------------------------------------------------

 * As a user I want to filter KDIPs in the admin interface by status and job so I can find them more easlily.
 * An application, in its KDip brief results display, shows the columns "KDip id", "Status", "Reason", "EnumCron", "Job".
 * An application, when retrieving MARCXML for a digitized volume, keeps only one 999 field (the one containing the matching barcode).
 * An application is able to handle volumes whose directory names are 'barcode-whatever' (32 char max).
 * A user is able to add/edit enumeration/chronology information for a digitized volume, and have that information saved to the MARCXML 999|a.
 * After creating an ARK for a digitized volume, an application stores the value of the PID in its database.
 * An application uses 'barcode-whatever' as the SIP identifier.
 * An application checks to see if a volume's path has changed and updates if it has so database can stay in sync with the file system.
 * When an admin processes a job for HT injestion the SIP is crated in a "HT" directory so they can be more easily managed and cleaned up.
 
Relase 1.0.0 - Hathi Trust Basic Ingest
---------------------------------------

 * All the basic validation and packaging steps for Hathi Trust ingest.


Release 0.1.0 - Initial Prototype
---------------------------------
First working prototype.

**Internal prototype: Not for production release**

 * An application administrator can run a script that uploads a file to Internet Archive.

