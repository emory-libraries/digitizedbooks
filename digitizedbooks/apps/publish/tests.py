import os
from unittest import skip

from eulxml.xmlmap import load_xmlobject_from_file

from django.test import TestCase

from digitizedbooks.apps.publish.models import Marc, KDip, Job

class TestKDip(TestCase):

    def test_KDip_load(self):
        # Show there is nothing up my sleave
        self.assertEquals(len(KDip.objects.all()), 0)

        # load the KDIPs from the directory defined in settings
        KDip.load()
        #self.assertEquals(len(KDip.objects.all()), 4)

        for k in KDip.objects.all():
            print('%s, %s, %s' % (k.kdip_id, k.status, k.reason))

        k1 = KDip.objects.get(kdip_id = '010000666241')
        self.assertEquals(k1.status, 'new')
        self.assertEquals(k1.job, None)

        k2 = KDip.objects.get(kdip_id = '010002643870')
        self.assertEquals(k2.status, 'new')
        self.assertEquals(k2.job, None)

        k3 = KDip.objects.get(kdip_id = '10002333054')
        self.assertEquals(k3.status, 'invalid')
        self.assertEquals(k3.job, None)
