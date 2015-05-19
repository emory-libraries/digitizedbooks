from django.core.management.base import NoArgsCommand
from publish.models import KDip
from django.conf import settings
import requests
from os import remove

class Command(NoArgsCommand):
    """
    Manage command to check if volume is live in HT
    """

    def handle_noargs(self, **options):
        """
        HT returns a `200` for volumes that are live.
        If not found, `500` is returned
        """
        kdips = KDip.objects.filter(accepted_by_ht=False)
        ht_stub = getattr(settings, 'HT_STUB', None)

        for kdip in kdips:
            print "what"

            req = requests.get('%s%s' % (ht_stub, kdip.kdip_id))
            if req.status_code is 200:
                kdip.accepted_by_ht = True
                kdip.save()

                kdip_dir = getattr(settings, 'KDIP_DIR', None)
                try:
                    remove('%sHT/%s.zip' % (kdip_dir, kdip.kdip_id))
                except OSError:
                    pass
