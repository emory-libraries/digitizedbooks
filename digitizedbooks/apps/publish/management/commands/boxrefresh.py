from box import refresh_v2_token
from digitizedbooks.apps.publish.models import BoxToken
from django.core.management.base import NoArgsCommand

class Command(NoArgsCommand):

    def handle_noargs(self, **options):
        token = BoxToken.objects.get(id=1)
        response = refresh_v2_token(token.client_id, token.client_secret, token.refresh_token)
        print response['refresh_token']
        token.refresh_token = response['refresh_token']
        token.save()
