import models
import os, re
import subprocess
from django.core.mail import send_mail
from django.conf import settings
from eulxml.xmlmap import load_xmlobject_from_string, load_xmlobject_from_file

def upload_file(zephir_file):
    host = settings.ZEPHIR_FTP_HOST
    user = settings.ZEPHIR_LOGIN
    passw = settings.ZEPHIR_PW
    ftp_dir = settings.ZEPHIR_UPLOAD_DIR
    curl_path = settings.CURL_PATH

    # FTP the file
    try:
        upload_cmd = '%s -k -u %s:%s -T %s --ssl-reqd --ftp-pasv %s/%s/' % (curl_path, user, passw, zephir_file, host, ftp_dir)
        upload_to_z = subprocess.check_output(upload_cmd, shell=True)
        return True
    except:
        # Bail out if something goes wrong and return an error status.
        return False

def send_to_zephir(job):
    kdip_dir = settings.KDIP_DIR
    kdips = models.KDip.objects.filter(job=job.id)
    # Tmp file for combined MARC XML. The eulxml output includes the namespace in the
    # <record>. We will be getting rid of that then deleting this file.
    zephir_tmp_file = '%s/Zephir/%s.tmp' % (kdip_dir, job.name)
    # File for the combined MARC XML.
    zephir_file = '%s/Zephir/%s.xml' % (kdip_dir, job.name)

    # Remove zephir file if it is already there so we can start from scratch.
    try:
        os.remove(zephir_file)
    except OSError:
        pass

    # Opening line for MARC XML
    open(zephir_tmp_file, 'a').write('<collection xmlns="http://www.loc.gov/MARC21/slim">\n')

    # Loop through the KDips to the the MARC XML
    for kdip in kdips:
        marc_file = '%s/%s/marc.xml' %(kdip.path, kdip.kdip_id)

        # Load the MARC XML
        marc = load_xmlobject_from_file(marc_file, models.Marc)

        # Serialize the XML into the tmp file
        open(zephir_tmp_file, 'a').write('\t' + marc.record.serialize(pretty=True))

    # Write the final line
    open(zephir_tmp_file, 'a').write('</collection>')

    # Now copy the contents of the tmp file to the real file and strip out the
    # namespace from the record tag.
    with open(zephir_tmp_file, 'r') as input_file, open(zephir_file, 'a') as output_file:
        for line in input_file:
            if len(line) > 1:
                new_line = re.sub('<record.*>', '<record>', line)
                output_file.write(new_line)

    # Delete tmp file
    os.remove(zephir_tmp_file)

    upload = upload_file(zephir_file)

    if upload:
        send_from = settings.EMORY_CONTACT
        zephir_contact = settings.ZEPHIR_CONTACT

        # Create the body of the email
        body = 'file name=%s.xml\n' % job.name
        body += 'file size=%s\n' % os.path.getsize(zephir_file)
        body += 'record count=%s\n' % job.volume_count
        body += 'notification email=%s' % send_from

        # Send email to Zephir. Zephir contact is defined in the loacal settings.
        send_mail('File sent to Zephir', body, send_from, [zephir_contact], fail_silently=False)

        return 'waiting on zephir'

    else:
        return 'zephir upload error'
