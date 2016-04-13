Release 1.4.5
-------------
* Added better error handling for uploads to Box.
* Added setting for `EMORY_MANAGERS` so multiple emory people can receive email notifications.

Release 1.4.4
-------------
* Updated the Zephir download to comply with their new security. Release 1.4.1 only updated it for upload.

Release 1.4.3
-------------
Moved the writing MARC record to disk into the function that prepares the MARC so it will be regenerated when a KDip is reprocessed.

Release 1.4.2
-------------
Fix to make Alma MARC records comply with HathiTrust.
* As a user, I want the marcxml record submitted to HathiTrust to contain only one 035$a field containing a valid OCLC number, so that the record will validate when uploaded to Zephir

Release 1.4.1
-------------
Updates:
* Changes the 035 filed in the MARC XML to be compatible with HathiTrust.
* Updated the Zephir to comply with their new security.
* Handles pure Alma records with no reference to Aleph.

Bug fixes:
* Now pulling MARC record from Alma for real.

Release 1.4
-----------
Features:
* As a user, when I open a Job, I'd like to see how many Kdips are in that job, so that I know when it's the right size to send to Hathi Trust
* As a user I want the OCLC number recorded and displayed, so that I can tell which KDip volumes belong to the same work
* As a user, I want to be able to see Jobs and Kdips (by default) sorted with the most recent record at the top of the screen, so that I don't have to constantly scroll down
* As a user I want all relevant 856 fields to be added to the MARC record once a KDip has been published to HathiTrust
* As a library patron searching in EUCLID or DiscoverE, when i find a digitized volume  that has been published to HathiTrust, I want to see a clickable link in so I can view the item in HathiTrust.

Bug fixes:
* The meta.yml file should only list one "capture-date"

Other:
* Switched from Aleph to Alma.

Release 1.3
-----------
Features:
* As a user, once Zephir produces a report that the marc records for a Job have been processed, I want the application to automatically set the Job to "Ready for Hathi", so that I don't have to do it manually.
* As a user I want any and all staged digitized volumes to have a corresponding KDip record associated with it, so that no staged volumes end up getting "lost".
* As a user, once all the kdips in a job have been uploaded to MBox, I want an email automatically sent to Hathi Trust staff, so that the uploaded kdips will be processed into HT.

Bug fixes:
* Finally got the reprocessing of an individual KDip wroking reliably.
* Box.com changed the JSON response and the code was not able to find the checksum of the uploaded file and makring the job as `Failed to Upload`. The checksum had been called `zip_sha1` in the JSON but is now just `sha1`.

Improvements:
* The name of a directory to skip, eg `test` is now configurable instead of hardcoded.
* More tests.

Release 1.2.2
-------------
* Started getting an error for `datetime.strptime` that it was getting a tuple and not a string from the `DateTime` tiff tag. This release fixes that by converting the found DateTime to a string.

Release 1.2.1
-------------
* Upgrading from LIMB 2.x to 3.3 has broke the METS validation routine. The xpath for `techmd` was adjusted.
* Automated email to notify HT of new deposits was re-enabled.

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
