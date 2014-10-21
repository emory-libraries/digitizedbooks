# file digitizedbooks/publication/tests.py
#
#   Copyright 2010 Emory University General Library
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
import os
from unittest import skip

from eulxml.xmlmap import load_xmlobject_from_file

from django.test import TestCase

from digitizedbooks.publish.management.commands.publish import Command
from digitizedbooks.publish.models import Marc, KDip, Job

fixture_dir = os.path.dirname(os.path.abspath(__file__))+"/fixtures"


class TestPublishCommand(TestCase):


    @skip("This logic is currently being revised")
    def test_get_items(self,):
        c = Command()
        c.options = {'dir': 'digitizedbooks/publish/fixtures/METS'}
        result = c.get_items()
        expected = [{'mets': os.path.abspath(c.options['dir']+'/'+'123.mets'),'data_dir': os.path.abspath(c.options['dir']+'/'+'123')},
                    {'mets': os.path.abspath(c.options['dir']+'/'+'0001.mets'),'data_dir': os.path.abspath(c.options['dir']+'/'+'0001')}]
        self.assertEqual(result, expected)


# class TestMarcXml(TestCase):
#
#     def test_parse_marc(self,):
#         marc = load_xmlobject_from_file(fixture_dir+'/MARC/bibrecord.xml', Marc)
#         self.assertEquals(len(marc.datafields), 25)
#         self.assertEquals(marc.datafields[0].tag, '010')
#         self.assertEquals(len(marc.datafields[0].subfields), 1)
#         self.assertEquals(marc.datafields[0].subfields[0].code, 'a')
#         self.assertEquals(marc.datafields[0].subfields[0].text, '   98046370 /AC')
#         self.assertEquals(marc.note('010000603807'), 'PZ7 .R728 H35 1999')

class TestKDip(TestCase):

    def test_KDip_load(self):
        # Show there is nothing up my sleave
        self.assertEquals(len(KDip.objects.all()), 0)

        # load the KDIPs from the directory defined in settings
        KDip.load()
        #self.assertEquals(len(KDip.objects.all()), 4)

        for k in KDip.objects.all():
            print('%s, %s, %s' % (k.kdip_id, k.status, k.reason))

        k1 = KDip.objects.get(kdip_id = '010002426573')
        self.assertEquals(k1.status, 'new')
        self.assertEquals(k1.job, None)

        k2 = KDip.objects.get(kdip_id = '010001059624')
        self.assertEquals(k2.status, 'new')
        self.assertEquals(k2.job, None)

        k3 = KDip.objects.get(kdip_id = '010002588586')
        self.assertEquals(k3.status, 'invalid')
        self.assertEquals(k3.job, None)

        k4 = KDip.objects.get(kdip_id = '010002588587')
        self.assertEquals(k4.status, 'invalid')
        self.assertEquals(k4.job, None)
