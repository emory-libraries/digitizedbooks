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

