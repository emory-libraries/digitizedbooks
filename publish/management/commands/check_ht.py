from django.core.management.base import BaseCommand
from publish.models import KDip
from django.conf import settings
import requests
from os import remove

class Command(BaseCommand):
    """
    Manage command to check if volume is live in HT
    """

    def handle(self, **options):
        """
        HT returns a `200` for volumes that are live.
        If not found, `500` is returned
        """
        kdips = KDip.objects.filter(accepted_by_ht=False)
        ht_stub = getattr(settings, 'HT_STUB', None)

        for kdip in kdips:
            ht_url = '%s%s' % (ht_stub, kdip.kdip_id)
            req = requests.get(ht_url)
            print req.status_code
            if req.status_code == 200:
                kdip.accepted_by_ht = True
                kdip.save()

                kdip_dir = getattr(settings, 'KDIP_DIR', None)
                try:
                    remove('%sHT/%s.zip' % (kdip_dir, kdip.kdip_id))
                except OSError:
                    pass
