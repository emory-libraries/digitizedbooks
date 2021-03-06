from unittest import skip

from eulxml.xmlmap import load_xmlobject_from_file

from django.test import TestCase
from digitizedbooks.apps.publish.management.commands import check_ht
from django.core import management
from digitizedbooks.apps.publish.models import Marc, KDip, Job, AlmaBibRecord
from django.conf import settings
import re
import Utils
import SendToZephir
from os import system

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
        self.assertEquals(k1.oclc, '50047195')

        k2 = KDip.objects.get(kdip_id = '010002643870')
        self.assertEquals(k2.status, 'new')
        self.assertEquals(k2.job, None)
        self.assertEquals(k2.oclc, '191229673')

        k3 = KDip.objects.get(kdip_id = '10002333054')
        self.assertEquals(k3.status, 'invalid')
        self.assertEquals(k3.job, None)
        self.assertEquals(k3.oclc, '01756136')
        error = k3.validationerror_set.first().error
        self.assertEquals(error, 'Published in 1933')
        error_count = k3.validationerror_set.all().count()
        self.assertEquals(error_count, 1)

        # Test reprocess
        k1.status = 'invalid'
        k1.save()
        self.assertEquals(k1.status, 'invalid')
        KDip.validate(k1)
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
        self.assertEquals(d, 1939)

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

        # Make sure we removed the aleph reference
        marc = '%s/10002333054/marc.xml' % (settings.KDIP_DIR)
        with open(marc, 'r') as marc_rec:
            data=marc_rec.read()
            self.assertNotIn('(Aleph)', data)
            self.assertIn('(GEU)Aleph', data)

class TestMarcUpdate(TestCase):

    def test_check_ht(self):
        test_xml = [
            'digitizedbooks/apps/publish/fixtures/bib1.xml',
            'digitizedbooks/apps/publish/fixtures/bib2.xml',
            'digitizedbooks/apps/publish/fixtures/bib3.xml'
        ]

        job = Job(pk=1)
        job.save()
        kdip0 = KDip.objects.create(kdip_id='10002350302', oclc="12345", note='0', pid='r8d9b', create_date = '2015-12-30 15:43:17', job_id=1)
        kdip1 = KDip.objects.create(kdip_id='10002350304', oclc="12345", note='1', pid='r8d9y', create_date = '2015-12-30 15:43:17', job_id=1)
        kdip2 = KDip.objects.create(kdip_id='10002350306', oclc="67890", note='2', pid='r8d9s', create_date = '2015-12-30 15:43:17', job_id=1)
        text590 = "The online edition of this book in the public domain, i.e., not protected by copyright, has been produced by the Emory University Digital library Publications Program."

        for xml in test_xml:
            index = test_xml.index(xml)
            kdip = KDip.objects.get(note=index)
            marc = load_xmlobject_from_file(xml, AlmaBibRecord)
            marc = check_ht.add_856(marc, kdip)
            marc = Utils.remove_all_999_fields(marc)
            marc = Utils.update_583(marc)


            text_856 = '<datafield tag="856" ind1="4" ind2="1"><subfield code="3">%s</subfield><subfield code="u">http://pid.emory.edu/ark:/25593/%s/HT</subfield><subfiled code="y">HathiTrust version</subfiled></datafield>' % (index, kdip.pid)
            field856s = []
            for tag856 in marc.field856:
                field856s.append(tag856.serialize())

            self.assertIn(text_856, field856s)

            self.assertEqual(len(marc.field999), 0)

            self.assertNotIn(marc.serialize().lower(), text590.lower())

            marc = check_ht.add_590(marc)

            self.assertEqual(marc.field590, text590)

            self.assertEqual(marc.tag583a, 'digitized')

class TestPureAlmaBibRecord(TestCase):
    def test_pure_alma_record(self):
        record = load_xmlobject_from_file('digitizedbooks/apps/publish/fixtures/pure-alma.xml', Marc)
        self.assertTrue(Utils.transform_035(record))

class TestHTMarc(TestCase):
    def test_ht_marc(self):
        rec = Utils.create_ht_marc('010000666241')

        # Only one field for the oclc
        self.assertEqual(len(re.findall('OCoLC|ocm|ocn', rec.serialize())), 1)

        # Only one 999 field for HT
        self.assertEqual(len(rec.tag_999), 1)
        # And that one need the barcode in code i
        self.assertTrue('<subfield code="i">010000666241</subfield>' in rec.tag_999[0].serialize())

        # Need to change Aleph reference from `(Aleph)..` to `(GEU)Aleph...`
        self.assertEqual(len(re.findall('\(Aleph', rec.serialize())), 0)
        # and make sure we did add the new one correctly, this is also check to
        # see if we put it in the right spot
        self.assertTrue('(GEU)Aleph000116142' in rec.field_035[-1].serialize())

class TestZephir(TestCase):
    def test_zephir_upload(self):
        self.assertTrue(SendToZephir.upload_file('digitizedbooks/apps/publish/fixtures/pure-alma.xml'))
        # Clean up the file we just uploadedhost = settings.ZEPHIR_FTP_HOST
        host = settings.ZEPHIR_FTP_HOST
        user = settings.ZEPHIR_LOGIN
        passw = settings.ZEPHIR_PW
        curl_path = settings.CURL_PATH
        delete_cmd = "%s --ssl-reqd --ftp-pasv -u %s:%s %s -Q 'DELE testrecs/pure-alma.xml'" % (curl_path, user, passw, host)
        system(delete_cmd)
        # curl --ftp-ssl-reqd --ftp-pasv -u ht-emory:ht-emory:W2012-emory.v1 ftp://ftps.cdlib.org -Q 'DELE testrecs/pure-alma.xml' -v
