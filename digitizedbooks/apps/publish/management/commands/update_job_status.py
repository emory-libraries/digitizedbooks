from box import refresh_v2_token
from digitizedbooks.apps.publish.models import Job, KDip
from django.core.management.base import NoArgsCommand
from sys import exit
from django.conf import settings
import subprocess
import os

class Command(NoArgsCommand):

    def handle_noargs(self, **options):

        pending_zephir_jobs = Job.objects.filter(status='waiting on zephir')

        host = getattr(settings, 'ZEPHIR_FTP_HOST', None)
        user = getattr(settings, 'ZEPHIR_LOGIN', None)
        passw = getattr(settings, 'ZEPHIR_PW', None)
        ftp_dir = getattr(settings, 'ZEPHIR_REPORT_DIR', None)

        for z_job in pending_zephir_jobs:
            try:
                report = '/tmp/%s.txt' % z_job.name
                download_cmd = 'curl --ftp-ssl-reqd --ftp-pasv -u %s:%s %s/%s/%s.txt --out %s' % (user, passw, host, ftp_dir, z_job.name, report)
                download_to_z = subprocess.check_output(download_cmd, shell=True)
                if '0 items skipped/error' in open(report).read():
                    z_job.status = 'ready for hathi'
                else:
                    z_job.status = 'zephir error'
                z_job.save()
                os.remove(report)
            except:
                pass

        pending_ht_jobs =  Job.objects.filter(status='being processed')
        for job in pending_ht_jobs:
        	for kdip in job.kdip_set.all():
        		if kdip.accepted_by_ht is False:
        			exit()
        	job.status = 'processed by ht'
        	job.save()
