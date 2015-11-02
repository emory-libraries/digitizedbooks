from box import refresh_v2_token
from digitizedbooks.apps.publish.models import Job, KDip
from django.core.management.base import NoArgsCommand
from sys import exit

class Command(NoArgsCommand):

    def handle_noargs(self, **options):
        jobs =  Job.objects.filter(status='being processed')
        for job in jobs:
        	for kdip in job.kdip_set.all():
        		if kdip.accepted_by_ht is False:
        			exit()
        	job.status = 'processed by ht'
        	job.save()
