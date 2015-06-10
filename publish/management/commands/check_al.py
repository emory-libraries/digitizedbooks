from django.core.management.base import NoArgsCommand
from publish.models import KDip, load_local_bib_record

class Command(NoArgsCommand):

    def handle_noargs(self, **options):
        kdips = KDip.objects.filter(accepted_by_ht=False).exclude(al_ht=True)

        for kdip in kdips:
            marc_rec = load_local_bib_record(kdip.kdip_id)

            link = 'http://pid.emory.edu/ark:/25593/%s/HT' % kdip.pid

            if link.decode('utf-8').lower() in marc_rec.serialize().decode('utf-8').lower():
                kdip.al_ht = True
                kdip.save()
                