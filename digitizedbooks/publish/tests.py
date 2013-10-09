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

from django.test import TestCase
from digitizedbooks.publish.management.commands.publish import Command
import os


class TestPublish(TestCase):


    def test_get_items(self,):
        c = Command()
        c.options = {'dir': 'digitizedbooks/publish/fixtures/METS'}
        result = c.get_items()
        expected = [{'mets': os.path.abspath(c.options['dir']+'/'+'123.mets'),'data_dir': os.path.abspath(c.options['dir']+'/'+'123')},
                    {'mets': os.path.abspath(c.options['dir']+'/'+'0001.mets'),'data_dir': os.path.abspath(c.options['dir']+'/'+'0001')}]
        self.assertEqual(result, expected)
        