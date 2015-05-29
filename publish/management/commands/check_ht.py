"""
Manage command to check if the volume is live in HatiTrust. If it is
we will updete the KDip making the attribute `accepted_by_ht`
`True` and then update the PID with the ht_url
"""
from django.core.management.base import BaseCommand
from publish.models import KDip, remove_all_999_fields, load_bib_record, update_583
from django.conf import settings
from pidservices.djangowrapper.shortcuts import DjangoPidmanRestClient
import requests
from os import remove
from time import strftime
from pysftp import Connection

class Command(BaseCommand):
    """
    Manage command to check if volume is live in HT
    """

    def handle(self, **options):
        """
        HT returns a `200` for volumes that are live.
        If not found, `404` is returned.
        """
        kdips = KDip.objects.filter(accepted_by_ht=False)
        ht_stub = getattr(settings, 'HT_STUB', None)

        client = DjangoPidmanRestClient()

        for kdip in kdips:
            ht_url = '%s%s' % (ht_stub, kdip.kdip_id)
            req = requests.get(ht_url)
            # If we get 200, we call it good and updte the KDip.
            if req.status_code == 200:
                kdip.accepted_by_ht = True
                kdip.save()

                if kdip.pid:
                    # Update the PID in pidman the the HathiTrust URL.
                    client.update_target( \
                        type="ark", noid=kdip.pid, target_uri=ht_url)
                    # Add a new qualifier for HathiTrust.
                    client.update_target( \
                        type="ark", noid=kdip.pid, qualifier="HT", \
                        target_uri=ht_url)

                # Try to remove the zip file that had been sent the HT.
                # We except the `OSError` because the file might have
                # already been cleaned out.
                kdip_dir = settings.KDIP_DIR
                try:
                    remove('%s/HT/%s.zip' % (kdip_dir, kdip.kdip_id))
                except OSError:
                    pass

                marc_rec = load_bib_record(kdip.kdip_id)

                marc_rec = remove_all_999_fields(marc_rec)

                marc_rec = update_583(marc_rec)

                today = strftime("%Y%m%d")

                # Path for new MACR record
                aleph_marc = '%s/%s/digitize_%s_%s.xml' % \
                    (kdip.path, kdip.kdip_id, today, kdip.kdip_id)

                print aleph_marc

                # Write the marc.xml to disk.
                with open(aleph_marc, 'w') as marcxml:
                    marcxml.write(marc_rec.serialize(pretty=True))

                with Connection( \
                        settings.ALEPH_SFTP_HOST, \
                        username=settings.ALEPH_SFTP_USER, \
                        password=settings.ALEPH_SFTP_PW,\
                    ) as sftp:

                    with sftp.cd(settings.ALEPH_SFTP_DIR):
                        sftp.put(aleph_marc)

