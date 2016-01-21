"""
Manage command to check if the volume is live in HatiTrust. If it is
we will updete the KDip making the attribute `accepted_by_ht`
`True` and then update the PID with the ht_url
"""
from django.core.management.base import BaseCommand
from digitizedbooks.apps.publish.models import KDip, Job, AlmaBibData856Field, AlmaBibRecord
from digitizedbooks.apps.publish.Utils import remove_all_999_fields, load_alma_bib_record, update_583
from django.conf import settings
from pidservices.djangowrapper.shortcuts import DjangoPidmanRestClient
import requests
from os import remove

def update_pid(kdip_pid, ht_url):
    client = DjangoPidmanRestClient()
    # Update the PID in pidman the the HathiTrust URL.
    client.update_target( \
        type="ark", noid=kdip_pid, target_uri=ht_url)
    # Add a new qualifier for HathiTrust.
    client.update_target( \
        type="ark", noid=kdip_pid, qualifier="HT", \
        target_uri=ht_url)


def add_856(record, kdip):
    field856s = []
    for tag856 in record.field856:
        field856s.append(tag856.serialize())

    if 'http://pid.emory.edu/ark:/25593/%s/HT' % kdip.pid not in field856s:
        if kdip.note:
            # We need to see if there are any KDips in a job with the same OCLC.
            # If there are, it means they are multi volume and we need to list
            # each volume in an 856 field.

            volumes = KDip.objects.filter(oclc=kdip.oclc).filter(job=kdip.job.id)
            if len(volumes) > 0:
                for vol in volumes:
                    record.field856.append(AlmaBibData856Field(
                        code_u ='http://pid.emory.edu/ark:/25593/%s/HT' % vol.pid,
                        code_3 = vol.note)
                    )
            else:
                record.field856.append(AlmaBibData856Field(
                    code_u = 'http://pid.emory.edu/ark:/25593/%s/HT' % kdip.pid,
                    code_3 = kdip.note)
                )
        else:
            record.field856.append(AlmaBibData856Field(
                code_u = 'http://pid.emory.edu/ark:/25593/%s/HT' % kdip.pid)
            )
    return record

def add_590(record):
    text = "The online edition of this book in the public domain, i.e., not protected by copyright, has been produced by the Emory University Digital library Publications Program."
    record.field590 = text
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
        kdips = KDip.objects.filter(accepted_by_ht=False).exclude(status='do not process').exclude(job=None)
        ht_stub = getattr(settings, 'HT_STUB', None)

        for kdip in kdips:
            ht_url = '%s%s' % (ht_stub, kdip.kdip_id)
            req = requests.get(ht_url)
            # If we get 200, we call it good and updte the KDip.
            print req.status_code
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

                bib_rec = load_alma_bib_record(kdip)

                # Make a back up of what we got from Alma
                bk_marc_rec = '%s/%s/marc-bk.xml' % (kdip.path, kdip.kdip_id)
                with open(bk_marc_rec, 'w') as bk_marc:
                    bk_marc.write(bib_rec.serialize(pretty=True))


                bib_rec = remove_all_999_fields(bib_rec)

                bib_rec = update_583(bib_rec)

                text_590 = "The online edition of this book in the public domain, i.e., not protected by copyright, has been produced by the Emory University Digital library Publications Program"

                # Check for the text in the 590 field.
                if text_590.lower() not in bib_rec.serialize().lower():
                    bib_rec = add_590(bib_rec)

                # Add some tags based on some conditionals.
                bib_rec = add_856(bib_rec, kdip)

                # Path for new MACR record
                new_marc = '%s/%s/new-marc.xml' % (kdip.path, kdip.kdip_id)

                # Write the marc.xml to disk.
                with open(new_marc, 'w') as marcxml:
                    marcxml.write(bib_rec.serialize(pretty=True))

                put = requests.put('%sbibs/%s' % (settings.ALMA_API_ROOT, kdip.mms_id),
                        data = bib_rec.serialize(),
                        params={'apikey': settings.ALMA_APIKEY},
                        headers={'Content-Type': 'application/xml'}
                )
                if put.status_code != 200:
                    kdip.status = 'alma_fail'
                    kdip.save()
