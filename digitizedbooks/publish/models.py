# file digitizedbooks/publication/models.py
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

from datetime import datetime
import requests
import os, re

from django.conf import settings
from django.contrib.auth import user_logged_in
from django.db import models
from django.dispatch import receiver


from eulxml.xmlmap import XmlObject
from eulxml.xmlmap import load_xmlobject_from_string
from eulxml.xmlmap.fields import StringField, NodeField, NodeListField, IntegerField



import logging

logger = logging.getLogger(__name__)


@receiver(user_logged_in)
def _login_actions(sender, **kwargs):
    "This functions is called at login"
    KDip.load()


# Configure  KDIP_DIR
kdip_dir = getattr(settings, 'KDIP_DIR', None)
if not kdip_dir:
    msg = "Failed to configure KDIP_DIR in localsettings. Please do so now otherwise most things will not work."
    logger.error(msg)
    raise Exception (msg)

# METS XML
class METSFile(XmlObject):
    ROOT_NAME = 'file'
    ROOT_NAMESPACES = {
         'xlink' : "http://www.w3.org/1999/xlink",
        'mets': 'http://www.loc.gov/METS/'
    }

    id = StringField('@ID')
    admid = StringField('@ADMID')
    mimetype = StringField('@MIMETYPE')
    loctype = StringField('mets:FLocat/@LOCTYPE')
    href = StringField('mets:FLocat/@xlink:href')

#TODO make schemas and namespaces local
class METStechMD(XmlObject):
    ROOT_NAME = 'techMD'
    ROOT_NAMESPACES = {
        'mix': 'http://www.loc.gov/mix/v20',
        'mets': 'http://www.loc.gov/METS/'
    }


    id = StringField('@ID')
    href = StringField('mets:mdWrap/mets:xmlData/mix:mix/mix:BasicDigitalObjectInformation/mix:ObjectIdentifier/mix:objectIdentifierValue')
    size = IntegerField('mets:mdWrap/mets:xmlData/mix:mix/mix:BasicDigitalObjectInformation/mix:fileSize')
    mimetype = StringField('mets:mdWrap/mets:xmlData/mix:mix/mix:BasicDigitalObjectInformation/mix:FormatDesignation/mix:formatName')
    checksum = StringField('mets:mdWrap/mets:xmlData/mix:mix/mix:BasicDigitalObjectInformation/mix:Fixity/mix:messageDigest')

class Mets(XmlObject):
    XSD_SCHEMA = 'http://www.loc.gov/standards/mets/version191/mets.xsd'
    ROOT_NAME = 'mets'
    ROOT_NAMESPACES = {'mets': 'http://www.loc.gov/METS/'}

    #x = NodeListField('mets:fileSec/mets:fileGrp', METSFile)
    tiffs = NodeListField('mets:fileSec/mets:fileGrp[@ID="TIFF"]/mets:file', METSFile)
    jpegs = NodeListField('mets:fileSec/mets:fileGrp[@ID="JPEG"]/mets:file', METSFile)
#    jp2s = NodeListField('mets:fileSec/mets:fileGrp[@ID="JP2000"]/mets:file', METSFile)
    altos = NodeListField('mets:fileSec/mets:fileGrp[@ID="ALTO"]/mets:file', METSFile)
    techmd = NodeListField('mets:amdSec/mets:techMD', METStechMD)


# MARC XML
class MarcBase(XmlObject):
    "Base for MARC objects"
    ROOT_NAMESPACES = {'marc':'http://www.loc.gov/MARC21/slim'}


class MarcSubfield(MarcBase):
    "Single instance of a MARC subfield"
    ROOT_NAME = 'marc:subfield'

    code = StringField('@code')
    "code of subfield"
    text = StringField('text()')
    'text of subfield element'

class MarcDatafield(MarcBase):
    "Single instance of a MARC datafield"
    ROOT_NAME = 'marc:datafield'

    tag = StringField('@tag')
    "tag or type of datafield"
    subfields = NodeListField('marc:subfield', MarcSubfield)
    "list of marc subfields"


class Marc(MarcBase):
    "Top level MARC xml object"
    ROOT_NAME = 'marc:collection'

    datafields = NodeListField('marc:record/marc:datafield', MarcDatafield)
    "list of marc datafields"


    def note(self, barcode):
        """
        :param: barcode aka item_id that is used to lookup the note field
        Finds parent of subfiled where text() = barcode and @code=i.
        Then finds subfield@code=a

        Returns the note field or '' if it can not be looked up
        """

        try:
            parent = self.node.xpath('marc:record/marc:datafield[@tag="999"]/marc:subfield[@code="i" and text()="%s"]/..' % barcode, namespaces=self.ROOT_NAMESPACES)[0]
            note = parent.xpath('marc:subfield[@code="a"]', namespaces=self.ROOT_NAMESPACES)[0].text
        except Exception as e:
            note = ''
        return note


# DB Models
class KDip(models.Model):
    "Class to describe Kirtas output directories"
    KDIP_STATUSES = (
        ('new', 'New'),
        ('processed', 'Processed'),
        ('archived', 'Archived'),
        ('invalid', 'Invalid'),
       ('do not process', 'Do Not Process')
    )

    kdip_id = models.CharField(max_length=100, unique=True)
    'This is the same as the directory name'
    create_date = models.DateTimeField()
    'Create time of the directory'
    status = models.CharField(max_length=20, choices=KDIP_STATUSES, default='new')
    'status of the KDip'
    note = models.CharField(max_length=200, blank=True)
    'Notes about this packagee, initially looked up from bib record'
    job = models.ForeignKey('Job', null=True, blank=True, on_delete=models.SET_NULL)
    ':class:`Job` of which it is a part'


    def _validate(self):
        logger.info("VALIDATING %s" % self.kdip_id)


    @classmethod
    def load(self):
        "Class method to scan data directory specified in the ``localsettings`` **KDIP_DIR** and create new KDIP objects in the database."

        # find all KDIP directories
        kdip_reg = re.compile(r"^[0-9]+$")
        kdips = filter(lambda f: kdip_reg.search(f), os.listdir(kdip_dir))
        kdip_list = [k for k in kdips if os.path.isdir('%s/%s' % (kdip_dir, k))]

        # create the KDIP is it does not exits
        for k in kdip_list:
            try:
                # lookkup bib record for note field
                r = requests.get('http://library.emory.edu/uhtbin/get_bibrecord', params={'item_id': k})
                bib_rec = load_xmlobject_from_string(r.text.encode('utf-8'), Marc)
                defaults={
                   'create_date': datetime.fromtimestamp(os.path.getctime('%s/%s' % (kdip_dir, k))),
                    'note': bib_rec.note(k)
                }
                kdip, created = self.objects.get_or_create(kdip_id=k, defaults = defaults)
                if created:
                    logger.info("Created KDip %s" % kdip.kdip_id)
                    kdip._validate()
            except Exception as e:
                logger.error("Error creating KDip %s : %s" % (k, e.message))
                pass



    def __unicode__(self):
        return self.kdip_id

    class Meta:
        ordering = ['create_date']

class Job(models.Model):
    "This class collects :class:`KDip` objects into logical groups for later processing"

    JOB_STATUSES = (
        ('new', "New"),
        ('ready to process', 'Ready To Process'),
        ('processed', 'Processed')
    )

    name = models.CharField(max_length=100, unique=True)
    'Human readable name of job'
    status = models.CharField(max_length=20, choices=JOB_STATUSES, default='new')

    def __unicode__(self):
        return self.name

    class Meta:
        ordering = ['id']
