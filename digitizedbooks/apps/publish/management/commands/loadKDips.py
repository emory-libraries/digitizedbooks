from django.core.management.base import NoArgsCommand
from digitizedbooks.apps.publish.models import KDip

class Command(NoArgsCommand):

    def handle_noargs(self, **options):
        KDip.load()
