from __future__ import absolute_import

from digitizedbooks.celery import app
from django.conf import settings
from django.core.mail import send_mail
from publish.models import Job, KDip, BoxToken
import os, shutil
from hashlib import md5, sha1
import logging
from pidservices.clients import parse_ark
from pidservices.djangowrapper.shortcuts import DjangoPidmanRestClient
import zipfile
import box
import json
import subprocess
import glob


@app.task
def upload_for_ht(kdips, job_id):
    """
    Task to upload files to Box in the backgroud.
    """
    print "oh hello there"
    logger = logging.getLogger(__name__)
    kdip_dir = getattr(settings, 'KDIP_DIR', None)

    def zipdir(path, zip):
        """
        Zip up all the files for the volume.
        """
        for root, dirs, files in os.walk(path):
            for vol_file in files:
                zip.write(os.path.join(root, vol_file))

    def checksumfile(checkfile, process_dir):
        with open(checkfile, 'rb') as file:
            with open('%s/checksum.md5' % (process_dir), 'a') as outfile:
                if 'alto' in checkfile:
                    checkfile = checkfile.replace('.alto', '')
                filename = checkfile.split('/')
                outfile.write('%s %s\n' % ((md5(file.read()).hexdigest()), filename[-1]))

    def checksumverify(checksum, process_dir, file):
        with open('%s/%s' % (process_dir, file), 'rb') as file:
            if md5(file.read()).hexdigest() == checksum:
                return True
            else:
                return False

    job = Job.objects.get(id=job_id)

    uploaded_files = []
    status = ''

    for process_kdip in kdips:
        kdip = KDip.objects.get(id=process_kdip)

        client = DjangoPidmanRestClient()
        pidman_domain = getattr(settings, 'PIDMAN_DOMAIN', None)
        pidman_policy = getattr(settings, 'PIDMAN_POLICY', None)

        ark = client.create_ark(domain='%s' % pidman_domain, target_uri='http://myuri.org', policy='%s' % pidman_policy, name='%s' % kdip.kdip_id)
        #naan = parse_ark(ark)['naan']
        noid = parse_ark(ark)['noid']

        kdip.pid = noid
        kdip.save()

        logger.info("Ark %s was created for %s" % (ark, kdip.kdip_id))

        #process_dir = '%s/ark+=%s=%s' % (kdip.path, naan, noid)
        if not os.path.exists('%s/HT' % kdip_dir):
            os.mkdir('%s/HT' % kdip_dir)
        process_dir = '%s/HT/%s' % (kdip_dir, kdip.kdip_id)

        if not os.path.exists(process_dir):
            os.makedirs(process_dir)



        tiffs = glob.glob('%s/%s/TIFF/*.tif' % (kdip.path, kdip.kdip_id))
        for tiff in tiffs:
            checksumfile(tiff, process_dir)
            shutil.copy(tiff, process_dir)

        altos = glob.glob('%s/%s/ALTO/*.xml' % (kdip.path, kdip.kdip_id))
        for alto in altos:
            checksumfile(alto, process_dir)
            shutil.copy(alto, process_dir)
            if 'alto' in alto:
                filename = alto.split('/')
                page,crap,ext = filename[-1].split('.')
                shutil.move(alto, '%s/%s.%s' % (process_dir, page, ext))
        #
        #new_altos = glob.glob('%s/*.alto.xml' % (process_dir))
        #for new_alto in new_altos:
        #    page,crap,ext = new_alto.split('.')
        #    shutil.move('%s' % (new_alto), '%s.%s' % (page, ext))

        ocrs = glob.glob('%s/%s/OCR/*.txt' % (kdip.path, kdip.kdip_id))
        for ocr in ocrs:
            checksumfile(ocr, process_dir)
            shutil.copy(ocr, process_dir)


        meta_yml = '%s/%s/meta.yml' % (kdip.path, kdip.kdip_id)
        marc_xml = '%s/%s/marc.xml' % (kdip.path, kdip.kdip_id)
        mets_xml = '%s/%s/METS/%s.mets.xml' % (kdip.path, kdip.kdip_id, kdip.kdip_id)

        checksumfile(meta_yml, process_dir)
        checksumfile(marc_xml, process_dir)
        checksumfile(mets_xml, process_dir)

        shutil.copy(meta_yml, process_dir)

        shutil.copy(marc_xml, process_dir)

        shutil.copy(mets_xml, process_dir)

        with open('%s/checksum.md5' % process_dir) as f:
            content = f.readlines()
            for line in content:
                parts = line.split()
                verify = checksumverify(parts[0], process_dir, parts[1])
                if verify is not True:
                    logger.error('Checksum check failes for %s.' % process_dir  )

        zipf = zipfile.ZipFile('%s.zip' % (process_dir), 'w', allowZip64=True)
        os.chdir('%s' % (process_dir))
        zipdir('.', zipf)
        zipf.close()
        # Delete the process directory to save space
        shutil.rmtree(process_dir)

        token = BoxToken.objects.get(id=1)

        response = box.refresh_v2_token(token.client_id, token.client_secret, token.refresh_token)

        token.refresh_token = response['refresh_token']
        token.save()

        logger.info('New refresh token: %s' % (response['refresh_token']))

        box_folder = getattr(settings, 'BOXFOLDER', None)

        url = 'https://upload.box.com/api/2.0/files/content -H "Authorization: Bearer %s" -F filename=@%s.zip -F parent_id=%s' % (response['access_token'], process_dir, box_folder)

        upload_result = subprocess.check_output('curl %s' % (url), shell=True)

        upload_response = json.loads(upload_result)

        try:
            zip_sha1 = sha1()
            local_file = open('%s.zip' % (process_dir), 'rb')
            zip_sha1.update(local_file.read())
            local_file.close()

            if zip_sha1.hexdigest() == upload_response['entries'][0]['zip_sha1']:
                status = 'being processed'
                #uploaded_files.append('ark+=%s=%s' % (naan, noid))
                uploaded_files.append(kdip.kdip_id)

        except Exception as e:
            resposne_message = upload_response['message']
            if resposne_message == 'Item with the same name already exists':
                logger.info('%s.zip already exists on Box.' % (process_dir))
                status = 'being processed'
            elif resposne_message:
                logger.error('Uploading %s.zip failed with message: %s' % (process_dir, resposne_message))
                status = 'failed'
            else:
                logger.error('Uploading %s.zip failed with unknown message' % (process_dir))
                status = 'failed'

    if status == 'being processed':
        job.status = 'being processed'
        job.save()
        kdip_list = '\n'.join(map(str, uploaded_files))
        send_to = getattr(settings, 'HATHITRUST_CONTACT', None)
        send_from = getattr(settings, 'EMORY_CONTACT', None)
        send_mail('New Volumes from Emory have been uploaded', 'The following volumes have been uploaded and are ready:\n\n%s' % kdip_list, send_from, [send_to], fail_silently=False)
    elif status == 'failed':
        job.status = status
        job.save()
