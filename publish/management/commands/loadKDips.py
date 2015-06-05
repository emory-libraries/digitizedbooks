from django.core.management.base import NoArgsCommand
from publish.models import KDip

class Command(NoArgsCommand):

    def handle_noargs(self, **options):
        KDip.load()