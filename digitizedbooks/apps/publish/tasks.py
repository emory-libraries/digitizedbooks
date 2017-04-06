'''
Task to create the zip package for HT, upload it to Box and let HT know it is there.
The package contains
* All the tiff files
* All the OCR text and xml files
* METS
* MARC
* Yaml file with metadata
* Text file listing all the checksums of all the files
'''
from __future__ import absolute_import

# Django stuff
from django.conf import settings
from django.core.mail import send_mail
import digitizedbooks.apps.publish.models as models
# PIDMAN stuff
from pidservices.clients import parse_ark
from pidservices.djangowrapper.shortcuts import DjangoPidmanRestClient
# Basic python stuff
import os
import shutil
import sys
import json
import glob
import zipfile
import logging
import traceback
from requests import ConnectionError
import gc
# A few specifics
from hashlib import md5, sha1
from box import refresh_v2_token, BoxClient, ItemAlreadyExists
from time import sleep, strftime, gmtime
# Exceptions
from OpenSSL.SSL import SysCallError
from django_rq import job
from boxsdk import OAuth2, Client, JWTAuth
import boxsdk.exception as BoxException
# TODO maybe the HathiTrust package should be made into a class.

def kdip_fail(job, kdip, error):
    print 'ERROR: {}'.format(error)
    now = strftime("%m-%d-%Y %H:%M", gmtime())
    kdip.status = 'upload_fail'
    # Only update the notes when if fails for the last time.
    if (job.upload_attempts == 5) or ('ConnectionError' not in str(error)):
        kdip.notes = kdip.notes + '\n' if len(kdip.notes) > 0 else ''
        kdip.notes = kdip.notes + ' ' + now + ' ' + str(error)
    kdip.save()

def refresh_client(job, kdip):
    # TODO maybe use the refreshbox manage command. We would need to store
    # access_token in the db.

    # Make sure we have a valid token for Box.com
    token = models.BoxToken.objects.get(id=1)
    response = None
    try:
        oauth = JWTAuth(
            client_id=token.client_id,
            client_secret=token.client_secret,
            enterprise_id='None',
            user=settings.BOXUSER,
            jwt_key_id=settings.JWTID,
            rsa_private_key_file_sys_path=settings.JWTPATH)

        return Client(oauth)
    except Exception as e:
        reason = 'box upload failed at due to token: ' + str(response)
        kdip_fail(job, kdip, reason)


def parse_response(job, kdip, response, sha1):
    try:
        # FIXME When a new version of file is uploaded, the boxsdk File object
        # returned does not have a attribute for `sha1`. There should be a way
        # to get one. For now, we're just going to skip it. HT will complaine if
        # something went wrong.
        if hasattr(response, 'sha1') == False or sha1 == response.sha1:
            kdip.status = 'uploaded'
            kdip.save()
        else:
            reason = 'Upload to Box failed:\nChecksum mismatch\nExpected {}\nGot {}\n\n{}'.format(
                sha1, response.sha1, response)
            kdip.save()
            print ' ERROR: {}'.format(reason)
            kdip_fail(job, kdip, reason)

    except KeyError:
        trace = traceback.format_exc()
        reason = '{}\nUpload to Box faild with with KeyError\n{}\n{}'.format(kdip.notes, response, trace)
        print 'ERROR: {}'.format(reason)
        kdip_fail(job, kdip, reason)

def upload_file(job, kdip):
    '''
    Method to package and upload KDip to Box.com
    '''
    box_client = refresh_client(job, kdip)
    box_folder = box_client.folder(folder_id=settings.BOXFOLDER)
    htpackage = kdip.kdip_id + '.zip'
    htpackage_path = kdip.process_dir + '.zip'
    zipsize = os.path.getsize(htpackage_path)

    zip_sha1 = sha1()
    local_file = open(htpackage_path, 'rb')
    # Get the checksum of the local file.
    zip_sha1.update(local_file.read())
    # Move the file back to the begining.
    local_file.seek(0)
    local_file.close()

    upload_response = None
    reupload = None
    try:
        # Collect the garbage. This is really just here because we get `MemoryError`s from time to time.
        gc.collect()
        # Upload file to Box
        upload_response = box_folder.upload(
            htpackage_path,
            preflight_check=True,
            preflight_expected_size=zipsize,
            upload_using_accelerator=True
        )
        # Send to function that does more checking and updatas object's status
        parse_response(job, kdip, upload_response, zip_sha1.hexdigest())

    except BoxException.BoxAPIException as e:
        # The API throws and exception with a status of 409 if
        # the file has already been uploaded.
        # Updateing the file is a different API call
        if hasattr(e, 'status') and e.status == 409:
            existing = refresh_client(job, kdip).file(file_id=e.context_info['conflicts']['id'])
            reupload = existing.update_contents(
                htpackage_path,
                preflight_check=True,
                preflight_expected_size=zipsize,
                upload_using_accelerator=True
            )
            parse_response(job, kdip, reupload, zip_sha1.hexdigest())

    except ConnectionError:
        sleep(30)
        upload_file(job, kdip)

    except Exception as e:
        trace = traceback.format_exc()
        reason = 'box upload failed: ' + trace
        kdip_fail(job, kdip, reason)

def zipdir(path, zip):
    """
    Zip up all the files for the volume.
    """
    for root, dirs, files in os.walk(path):
        for vol_file in files:
            zip.write(os.path.join(root, vol_file))


def checksumfile(checkfile, process_dir):
    """
    HT wants a file with checksums for each file we're sending them.
    """
    with open(checkfile, 'rb') as file:
        with open('{}/checksum.md5'.format(process_dir), 'a') as outfile:
            if 'alto' in checkfile:
                checkfile = checkfile.replace('.alto', '')
            filename = checkfile.split('/')
            outfile.write('{} {}\n'.format((md5(file.read()).hexdigest()), filename[-1]))


def checksumverify(checksum, process_dir, file):
    with open('{}/{}'.format(process_dir, file), 'rb') as file:
        if md5(file.read()).hexdigest() == checksum:
            return True
        else:
            return False


@job('high')
def upload_for_ht(job, count=1):
    """
    Task to upload files to Box in the backgroud.
    """
    logger = logging.getLogger(__name__)
    kdip_dir = settings.KDIP_DIR

    for kdip in models.KDip.objects.filter(job__id=job.id).exclude(status='uploaded').exclude(status='upload_fail'):
        # Only create a PID if it doesn't already have one
        if job.upload_attempts == 0:
            if not kdip.pid:
                try:
                    pidman_client = DjangoPidmanRestClient()
                    pidman_domain = settings.PIDMAN_DOMAIN
                    pidman_policy = settings.PIDMAN_POLICY

                    ark = pidman_client.create_ark(domain='{}'.format(pidman_domain),
                                                   target_uri='http://myuri.org',
                                                   policy='{}'.format(pidman_policy),
                                                   name='{}'.format(kdip.kdip_id))

                    noid = parse_ark(ark)['noid']

                    kdip.pid = noid
                    kdip.save()

                    logger.info("Ark {} was created for {}".format(ark, kdip.kdip_id))
                except Exception as e:
                    trace = traceback.format_exc()
                    logger.error("Failed creating an ARK for %s: %s" %
                                 (kdip.kdip_id, e))
                    reason = "Box uplaod failed while making an ARK line 161 " + ' ' + trace
                    print 'ERROR: {}'.format(reason)
                    kdip_fail(job, kdip, reason)

            else:
                logger.info("{} already has pid {}".format(kdip.kdip_id, kdip.pid))

            if not os.path.exists(kdip.process_dir):
                os.makedirs(kdip.process_dir)

            # Gather everything and write the file's checksum to a file via the
            # `checksum` method. The copy the file to the temp directory.
            # HT does not want sub directories in the package.
            tiffs = glob.glob('{}/{}/TIFF/*.tif'.format(kdip.path, kdip.kdip_id))
            for tiff in tiffs:
                checksumfile(tiff, kdip.process_dir)
                shutil.copy(tiff, kdip.process_dir)

            altos = glob.glob('{}/{}/ALTO/*.xml'.format(kdip.path, kdip.kdip_id))
            for alto in altos:
                checksumfile(alto, kdip.process_dir)
                shutil.copy(alto, kdip.process_dir)
                if 'alto' in alto:
                    filename = alto.split('/')
                    page, crap, ext = filename[-1].split('.')
                    shutil.move(alto, '{}/{}.{}'.format(kdip.process_dir, page, ext))

            ocrs = glob.glob('{}/{}/OCR/*.txt'.format(kdip.path, kdip.kdip_id))
            for ocr in ocrs:
                checksumfile(ocr, kdip.process_dir)
                shutil.copy(ocr, kdip.process_dir)

            checksumfile(kdip.meta_yml, kdip.process_dir)
            checksumfile(kdip.marc_xml, kdip.process_dir)
            checksumfile(kdip.mets_xml, kdip.process_dir)

            shutil.copy(kdip.meta_yml, kdip.process_dir)
            shutil.copy(kdip.marc_xml, kdip.process_dir)
            shutil.copy(kdip.mets_xml, kdip.process_dir)

            # After copying all the files to the tmp directory. We verify that
            # the checksum matches the one we made before the move. This is done
            # using the `verify()` method.
            with open('{}/checksum.md5'.format(kdip.process_dir)) as f:
                content = f.readlines()
                for line in content:
                    parts = line.split()
                    verify = checksumverify(parts[0], kdip.process_dir, parts[1])
                    if verify is not True:
                        logger.error('Checksum check failes for %s.' %
                                     kdip.process_dir)

            # Make the zip files
            zipf = zipfile.ZipFile('{}.zip'.format(kdip.process_dir), 'w', zipfile.ZIP_DEFLATED, allowZip64=True)
            os.chdir(kdip.process_dir)
            zipdir('.', zipf)
            zipf.close()

            # Delete the process directory to save space
            # but we keep the zip file
            shutil.rmtree(kdip.process_dir)

        attempts = 0

        while attempts < 5:

            try:
                # Don't upload if no pid
                upload_file(job, kdip) if kdip.pid else kdip_fail(job, kdip, '{} has no pid.'.format(kdip.kdip_id))
                break
            except ConnectionError:
                trace = traceback.format_exc()
                attempts += 1
                sleep(5)
                reason = 'Connection Error, failed to upload {}.'.format(kdip.kdip_id)
                print 'ERROR: {}'.format(reason)
                kdip.status = 'retry'
                kdip.save()
                kdip_fail(job, kdip, reason) if attempts == 5 else logger.error(
                    '{} failed to upload on attempt {} : '.format(kdip.kdip_id, attempts, trace))

            except SysCallError:
                trace = traceback.format_exc()
                attempts = 5
                reason = "SSL Error while uploading {}: {}".format(kdip.kdip_id, trace)
                logger.error(reason)
                kdip_fail(job, kdip, reason)

            except TypeError:
                trace = traceback.format_exc()
                attempts = 5
                reason = "TypeError in upload package for {}: {}".format(kdip.kdip_id, trace)
                logger.error(reason)
                kdip_fail(job, kdip, reason)

            except MemoryError:
                trace = traceback.format_exc()
                attempts = 5
                reason = "MemoryError for " + kdip.kdip_id
                logger.error(reason)
                kdip_fail(job, kdip, reason)

            except Exception as e:
                trace = traceback.format_exc()
                attempts = 5
                reason = "Unexpected error for {}: {}, {}".format(kdip.kdip_id, str(e), trace)
                logger.error(reason)
                kdip_fail(job, kdip, reason)

    # Check to see if all the KDips uploaded.
    job.upload_attempts = job.upload_attempts + 1
    statuses = job.kdip_set.values_list('status', flat=True)
    if ('retry' in statuses) and (job.upload_attempts < 5):
        # job.upload_attempts = job.upload_attempts + 1
        return upload_for_ht(job, count - 1)
    elif ('upload_fail' in statuses) and (job.upload_attempts == 5):
        job.status = 'failed'
        job.save()
    elif job.upload_attempts == 5:
        job.status = 'being processed'
        job.save()
        recipients = settings.HATHITRUST_CONTACTS + settings.EMORY_MANAGERS
        kdip_list = '\n'.join(job.kdip_set.filter(
            status='uploaded').values_list('kdip_id', flat=True))
        logger.info(kdip_list)
        send_to = settings.HATHITRUST_CONTACTS + settings.EMORY_MANAGERS
        send_from = settings.EMORY_CONTACT
        send_mail('New Volumes from Emory have been uploaded', 'The following volumes have been uploaded and are ready:\n\n{}'.format(kdip_list), send_from, send_to, fail_silently=False)
    else:
        return upload_for_ht(job, count - 1)
