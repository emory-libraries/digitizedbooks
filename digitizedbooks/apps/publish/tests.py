import os
from unittest import skip

from eulxml.xmlmap import load_xmlobject_from_file

from django.test import TestCase

from digitizedbooks.apps.publish.models import Marc, KDip, Job

import Utils

class TestKDip(TestCase):

    def test_KDip_load(self):
        # Show there is nothing up my sleave
        self.assertEquals(len(KDip.objects.all()), 0)

        # load the KDIPs from the directory defined in settings
        KDip.load()
        self.assertEquals(len(KDip.objects.all()), 4)

        k1 = KDip.objects.get(kdip_id = '010000666241')
        self.assertEquals(k1.status, 'new')
        self.assertEquals(k1.job, None)

        k2 = KDip.objects.get(kdip_id = '010002643870')
        self.assertEquals(k2.status, 'new')
        self.assertEquals(k2.job, None)

        k3 = KDip.objects.get(kdip_id = '10002333054')
        self.assertEquals(k3.status, 'invalid')
        self.assertEquals(k3.job, None)

        # Test reprocess
        k1.status = 'invalid'
        k1.save()
        self.assertEquals(k1.status, 'invalid')
        KDip.load(k1)
        self.assertEquals(k1.status, 'new')

        # Many tests for all the date cases.
        d = Utils.get_date('111220m19291931gauar         0    0eng d', '1999')
        self.assertEquals(d, 1931)

        d = Utils.get_date('111220p19291931gauar         0    0eng d', '1999')
        self.assertEquals(d, 1931)

        d = Utils.get_date('111220q19291931gauar         0    0eng d', '1999')
        self.assertEquals(d, 1931)

        d = Utils.get_date('111220r19291931gauar         0    0eng d', '1999')
        self.assertEquals(d, 1929)

        d = Utils.get_date('111220s19291931gauar         0    0eng d', '1999')
        self.assertEquals(d, 1929)

        d = Utils.get_date('111220e19291931gauar         0    0eng d', '1999')
        self.assertEquals(d, 1929)

        d = Utils.get_date('111220t19291931gauar         0    0eng d', '1999')
        self.assertEquals(d, 1931)

        d = Utils.get_date('111220t19391931gauar         0    0eng d', '1999')
        self.assertEquals(d, 1931)

        d = Utils.get_date('111220t    1931gauar         0    0eng d', '1999')
        self.assertEquals(d, 1931)

        d = Utils.get_date('111220d19291931gauar         0    0eng d', '1999')
        self.assertEquals(d, 1999)

        d = Utils.get_date('111220u19291931gauar         0    0eng d', '1999')
        self.assertEquals(d, 1999)

        d = Utils.get_date('111220c19291931gauar         0    0eng d', '1999')
        self.assertEquals(d, 1999)

        d = Utils.get_date('111220i19291931gauar         0    0eng d', '1999')
        self.assertEquals(d, 1999)

        d = Utils.get_date('111220k19291931gauar         0    0eng d', '1982 foo bar 1999')
        self.assertEquals(d, 1999)

        # Test for the get rights
        r = Utils.get_rights(1999, 'public domain')
        self.assertEquals(r, 'Published in 1999')

        r = Utils.get_rights(1900, 'public domain')
        self.assertEquals(r, None)

        r = Utils.get_rights(1900, 'foo bar')
        self.assertEquals(r, '583X does not equal "public domain"')
