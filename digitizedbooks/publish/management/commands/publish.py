# file digitizedbooks/publication/management/commands/publish_to_ia.py
# 
#   Copyright 2013 Emory University General Library
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

from digitizedbooks import settings
from collections import defaultdict
import logging
from optparse import make_option
import sys
import boto.s3
from boto.s3.key import Key
import django.http
import re
import os
import errno

from django.core.management.base import BaseCommand, CommandError

logger = logging.getLogger(__name__)

class Command(BaseCommand):

    args = "archive"
    help = __doc__

    option_list = BaseCommand.option_list + (
        make_option('--oclc',
                    dest = 'oclcnum',
                    help = 'The digitized objects OCLC number (e.g. ocm131687026)'),
        make_option('--digwf',
                    dest = 'digwfid',
                    help = 'The digitized objects digwf id (e.g. 5756)'),
        make_option('--dest',
                    dest = 'destination',
                    help = 'Choose one of Internet Archive (ia), HathiTrust (ht), or OpenEmory (oe)'),
        make_option('--marcxml',
                    dest = 'marcxml',
                    help = 'marcxml record associated with archive'),
    )

    def handle(self, *args, **options):

        self.verbosity = int(options['verbosity'])    # 1 = normal, 0 = minimal, 2 = all
        self.v_normal = 1
        self.v_max = 2

        # check required options
        if not options['destination']:
            raise CommandError('Destination required')
        if not options['oclcnum']:
            raise CommandError('oclc_required')
        if not options['digwfid']:
            raise CommandError('digwf required')

        if len(args) == 1:
            archive = args[0]
        else:
            raise CommandError('expecting exactly one file')

        if not self.validate_archive(archive):
            raise CommandError('Invalid archive file')

        if options.get('destination') == 'ia':
            self.push_to_ia(archive, options.get('marcxml'), options.get('oclcnum'), options.get('digwfid'))
        else:
            self.stdout.write('Unknown destination - exiting.\n')
            sys.exit()

        # summarize what was done
        self.stdout.write('\n')


    #TODO: support multipart upload for large files
    def push_to_ia(self, archive, marcxml, oclcnum, digwfid):
        try:
            cxn = boto.connect_ia(settings.IA_S3_ACCESS_KEY, settings.IA_S3_SECRET_KEY)
        except Exception as e:
            raise(CommandError('failed to connect: ' + e))

        bucket_name = '%s.%s.%s' % (re.sub('\D', '', oclcnum), digwfid, settings.IA_S3_NAMESPACE_SUFFIX)
        bucket = ''

        if not cxn.lookup(bucket_name):
            bucket = self.__create_bucket(cxn, bucket_name)

        else:
            prompt = ('%s exists.  Replace, Add to, or Exit (R/A/E) ? ') % bucket_name
            choice = raw_input(prompt)
            while not (choice == 'R' or choice == 'A' or choice == 'E'):
                choice = raw_input(prompt)

            bucket = cxn.get_bucket(bucket_name)

            if choice == 'R':
                for key in bucket.list():
                    self.output(self.v_max, 'deleting key: ' + key.name)
                    key.delete()
            elif choice == 'E':
                sys.exit()
            #if choice is A, simply proceed

        k = Key(bucket)
        if not self.validate_marcxml(marcxml):
            raise(CommandError('marcxml not valid'))
        elif not self.validate_archive(archive):
            raise(CommandError('archive not valid'))
        else:
            self.output(self.v_max, ('pushing %s' % marcxml))
            k.key = marcxml
            k.set_metadata('x-archive-meta-mediatype','texts')
            #k.set_metadata('x-archive-meta03-collection','emory')
            k.set_metadata('x-archive-meta-sponsor','Emory University, Robert W. Woodruff Library')
            k.set_metadata('x-archive-meta-contributor','Emory University, Robert W. Woodruff Library')
            k.set_contents_from_filename(marcxml, cb=self.__percent_cb, num_cb=10)
            self.output(self.v_max, ('done'))

            self.output(self.v_max, ('pushing %s' % archive))
            k.key = archive
            k.set_contents_from_filename(archive, cb=self.__percent_cb, num_cb=10)
            self.output(self.v_max, ('done'))

    def validate_archive(self, archive):
        is_valid = os.path.isfile(archive)
        return is_valid

    def validate_marcxml(self, marcxml):
        is_valid = os.path.isfile(marcxml)
        return is_valid

    def __percent_cb(self, complete, total):
        sys.stdout.write('.')
        sys.stdout.flush()

    def __create_bucket(self, cxn, bucket_name):
        self.output(self.v_max, ('creating bucket %s' % (bucket_name)))
        try:
            bucket = cxn.create_bucket(bucket_name, location=boto.s3.connection.Location.DEFAULT)
            #bucket = cxn.create_bucket(bucket_name, location='s3.us.archive.org')
        except Exception as e:
            raise(CommandError('failed to create bucket: %s\n' % (e)))

        return bucket

    def output(self, v, msg):
        '''simple function to handle logging output based on verbosity'''
        if self.verbosity >= v:
            self.stdout.write("%s\n" % msg)
