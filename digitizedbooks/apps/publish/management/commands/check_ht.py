"""
Manage command to check if the volume is live in HatiTrust. If it is
we will updete the KDip making the attribute `accepted_by_ht`
`True` and then update the PID with the ht_url
"""
from django.core.management.base import BaseCommand
from digitizedbooks.apps.publish.models import KDip
from digitizedbooks.apps.publish.Utils import remove_all_999_fields, load_local_bib_record, update_583
from django.conf import settings
from pidservices.djangowrapper.shortcuts import DjangoPidmanRestClient
import requests
from os import remove
from time import strftime
from pysftp import Connection
from pymarc import parse_xml_to_array, record_to_xml, Field

def update_pid(kdip_pid, ht_url):
    client = DjangoPidmanRestClient()
    # Update the PID in pidman the the HathiTrust URL.
    client.update_target( \
        type="ark", noid=kdip_pid, target_uri=ht_url)
    # Add a new qualifier for HathiTrust.
    client.update_target( \
        type="ark", noid=kdip_pid, qualifier="HT", \
        target_uri=ht_url)

def load_pymarc(tmp_marc):
    records = parse_xml_to_array(tmp_marc)
    return records[0]


def add_856(record, kdip):
    if kdip.note:
        record.add_field(
            Field(
                tag='856',
                indicators=['4', '1'],
                subfields=[
                    '3', kdip.note,
                    'u', 'http://pid.emory.edu/ark:/25593/%s/HT' % kdip.pid,
                    'y', 'HathiTrust version'
                ]))
        return record
    else:
        record.add_field(
            Field(
                tag='856',
                indicators=['4', '1'],
                subfields=[
                    'u', 'http://pid.emory.edu/ark:/25593/%s/HT' % kdip.pid,
                    'y', 'HathiTrust version'
                ]))
        return record

def add_590(record, text):
    record.add_field(
        Field(
            tag='590',
            indicators=['1', '2'],
            subfields=[
                'a', text
            ]))
    return record


class Command(BaseCommand):
    """
    Manage command to check if volume is live in HT
    """

    def handle(self, **options):
        """
        HT returns a `200` for volumes that are live.
        If not found, `404` is returned.
        """
        kdips = KDip.objects.filter(accepted_by_ht=False).exclude(status='do not process')
        ht_stub = getattr(settings, 'HT_STUB', None)

        for kdip in kdips:
            ht_url = '%s%s' % (ht_stub, kdip.kdip_id)
            req = requests.get(ht_url)
            # If we get 200, we call it good and updte the KDip.
            if req.status_code == 200:
                kdip.accepted_by_ht = True
                kdip.save()

                if kdip.pid:
                    update_pid(kdip.pid, ht_url)

                # Try to remove the zip file that had been sent the HT.
                # We except the `OSError` because the file might have
                # already been cleaned out.
                kdip_dir = settings.KDIP_DIR
                try:
                    remove('%s/HT/%s.zip' % (kdip_dir, kdip.kdip_id))
                except OSError:
                    pass

                marc_rec = load_local_bib_record(kdip.kdip_id)

                marc_rec = remove_all_999_fields(marc_rec)

                marc_rec = update_583(marc_rec)

                # Make a tmp MARC record.
                tmp_marc_path = '/tmp/%s.xml' % kdip.kdip_id
                # Write the marc.xml to disk.
                with open(tmp_marc_path, 'w') as tmp_marc:
                    tmp_marc.write(marc_rec.serialize())

                # Load the tmp_marc into pymarc.
                pymarc_record = load_pymarc(tmp_marc_path)

                # Add some tags based on some conditionals.
                pymarc_record = add_856(pymarc_record, kdip)

                # Check for the text in the 590 field.
                text_590 = "The online edition of this book in the public domain, i.e., not protected by copyright, has been produced by the Emory University Digital library Publications Program"

                if text_590.lower() not in marc_rec.serialize().lower():
                    pymarc_record = add_590(pymarc_record, text_590)

                today = strftime("%Y%m%d")

                # Path for new MACR record
                aleph_marc = '%s/%s/digitize_%s_%s.xml' % \
                    (kdip.path, kdip.kdip_id, today, kdip.kdip_id)

                pymarc_xml = record_to_xml(pymarc_record)
                open_tag = '<collection xmlns="http://www.loc.gov/MARC21/slim">'
                close_tag = '</collection>'
                # Write the marc.xml to disk.
                with open(aleph_marc, 'w') as marcxml:
                    marcxml.write(open_tag + pymarc_xml + close_tag)

                # SFTP the file for Aleph
                with Connection( \
                        settings.ALEPH_SFTP_HOST, \
                        username=settings.ALEPH_SFTP_USER, \
                        password=settings.ALEPH_SFTP_PW,\
                    ) as sftp:

                    with sftp.cd(settings.ALEPH_SFTP_DIR):
                        sftp.put(aleph_marc)
