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
import os, re, shutil, sys
from hashlib import md5

from django.conf import settings
from django.db import models
from django.core.mail import send_mail
from django.shortcuts import redirect
from django.http import HttpResponseRedirect

from ValidateTiff import ValidateTiff
import Utils
from SendToZephir import send_to_zephir

from eulxml.xmlmap import XmlObject
from eulxml.xmlmap import load_xmlobject_from_string, load_xmlobject_from_file
from eulxml.xmlmap.fields import StringField, NodeListField, IntegerField, NodeField

from PIL import Image

import logging
import yaml
import glob
from ftplib import FTP_TLS
#import celery
import django_rq
from digitizedbooks.apps.publish.tasks import upload_for_ht
import subprocess

logger = logging.getLogger(__name__)


# @receiver(user_logged_in)
# def _login_actions(sender, **kwargs):
#     "This functions is called at login"
#     KDip.load()


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
    #jp2s = NodeListField('mets:fileSec/mets:fileGrp[@ID="JP2000"]/mets:file', METSFile)
    altos = NodeListField('mets:fileSec/mets:fileGrp[@ID="ALTO"]/mets:file', METSFile)
    # Change due to LIMB 3.3 upgrade.
    # techmd = NodeListField('mets:amdSec/mets:techMD', METStechMD)
    techmd = NodeListField('mets:amdSec/mets:techMD[starts-with(@ID, "AMD_TECHMD_TIF") or starts-with(@ID, "AMD_TECHMD_JPG") or starts-with(@ID, "AMD_TECHMD_JP2")]', METStechMD)


# MARC XML
class MarcBase(XmlObject):
    "Base for MARC objects"
    ROOT_NAMESPACES = {'marc':'http://www.loc.gov/MARC21/slim'}

class MarcSubfield(MarcBase):
    "Single instance of a MARC subfield"
    ROOT_NS = 'http://www.loc.gov/MARC21/slim'
    ROOT_NAME = 'subfield'

    code = StringField('@code')
    "code of subfield"
    text = StringField('text()')
    'text of subfield element'

class MarcDatafield(MarcBase):
    "Single instance of a MARC datafield"
    ROOT_NS = 'http://www.loc.gov/MARC21/slim'
    ROOT_NAME = 'datafield'

    tag = StringField('@tag')
    "tag or type of datafield"
    subfields = NodeListField('marc:subfield', MarcSubfield)
    "list of marc subfields"

class MarcRecord(MarcBase):
    "Single instance of a MARC record"
    ROOT_NS = 'http://www.loc.gov/MARC21/slim'
    ROOT_NAME = 'record'

    tag = StringField('@tag')
    "tag or type of datafield"
    subfields = NodeListField('marc:subfield', MarcSubfield)
    "list of marc subfields"


class Marc(MarcBase):
    "Top level MARC xml object"
    ROOT_NS = 'http://www.loc.gov/MARC21/slim'
    ROOT_NAME = 'collection'

    record = NodeField('marc:record', MarcRecord)

    datafields = NodeListField('marc:record/marc:datafield', MarcDatafield)
    "list of marc datafields"

    tag_583x = StringField('marc:record/marc:datafield[@tag="583"]/marc:subfield[@code="x"]')
    # 583 code5 where a is 'digitized' or 'selected for digitization'
    # this will be for 'capture_agent' in yaml file

    tag_583_5 = StringField('marc:record/marc:datafield[@tag="583"][@ind1="1"]/marc:subfield[@code="5"]/text()')

    tag_583_a = StringField('marc:record/marc:datafield[@tag="583"][@ind1="1"]/marc:subfield[@code="a"]/text()')

    tag_008 = StringField('marc:record/marc:controlfield[@tag="008"]')

    tag_260 = StringField('marc:record/marc:datafield[@tag="260"]')
    tag_261a = StringField('marc:record/marc:datafield[@tag="264"][@ind2="1"]/marc:subfield[@code="a"]/text()')

    tag_999 = NodeListField("marc:record/marc:datafield[@tag='999']", MarcDatafield)

    field_999 = StringField("marc:record/marc:datafield[@tag='999']", MarcDatafield)

    tag_999a = StringField('marc:record/marc:datafield[@tag="999"]/marc:subfield[@code="a"]')

    field_035 = NodeListField('marc:record/marc:datafield[@tag="035"]', MarcDatafield)

    tag_035a = NodeListField('marc:record/marc:datafield[@tag="035"]/marc:subfield[@code="a"]', MarcDatafield)

    alma_number = StringField('marc:record/marc:controlfield[@tag="001"]/text()')

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

class Marc035Field(XmlObject):
    ROOT_NAME = 'datafield'
    ind1 = StringField("@ind1")
    ind2 = StringField("@ind2")
    tag = StringField("@tag")
    code_z = StringField('subfield[@code="z"]')

    def __init__(self, *args, **kwargs):
        super(Marc035Field, self).__init__(*args, **kwargs)
        self.ind1 = " "
        self.ind2 = " "
        self.tag = '035'

# Alma item record
class AlmaBibItem(XmlObject):
    mms_id = StringField('bib_data/mms_id')

# Alma item record
class AlmaBibData856Field(XmlObject):
    ROOT_NAME = 'datafield'
    ind1 = StringField("@ind1")
    ind2 = StringField("@ind2")
    tag = StringField("@tag")
    code_3 = StringField('subfield[@code="3"]')
    code_u = StringField('subfield[@code="u"]')
    code_y = StringField('subfiled[@code="y"]')

    def __init__(self, *args, **kwargs):
        super(AlmaBibData856Field, self).__init__(*args, **kwargs)
        self.tag = '856'
        self.ind1 = "4"
        self.ind2 = "1"
        self.code_y = "HathiTrust version"

class AlmaField(XmlObject):
    ROOT_NAME = 'datafield'

class AlmaBibData590Field(XmlObject):
    ROOT_NAME = 'datafield'
    ind1 = StringField("@ind1")
    ind2 = StringField("@ind2")
    tag = StringField("@tag")
    code_a = StringField('subfield[@code="a"]')

class AlmaBibRecord(XmlObject):
    field856 = NodeListField('record/datafield[@tag="856"]', AlmaBibData856Field)
    field590 = StringField('record/datafield[@tag="590"][@ind1=" "][@ind2=" "]/subfield[@code="a"]/text()')
    field999 = NodeListField("record/datafield[@tag='999']", AlmaField)
    tag583a = StringField('record/datafield[@tag="583"][@ind1="1"]/subfield[@code="a"]/text()')
    field_035 = NodeListField('record/datafield[@tag="035"]', AlmaField)
    alma_number = StringField('record/controlfield[@tag="001"]/text()')

class Alto(XmlObject):
    '''
    Instance of ALTO xml object. Currently this is only used for schema validation
    '''
    XSD_SCHEMA = 'http://www.loc.gov/standards/alto/alto-v2.0.xsd'
    ROOT_NAME = 'alto'

# DB Models
class KDip(models.Model):
    "Class to describe Kirtas output directories"
    # 1.4.1 Changed the status "new" to read "Valid". "New" was a poor
    # legacy decision.
    KDIP_STATUSES = (
        ('new', 'Valid'),
        ('processed', 'Processed'),
        ('archived', 'Archived'),
        ('invalid', 'Invalid'),
        ('do not process', 'Do Not Process'),
        ('alma_fail', 'Alma Update Failed'),
        ('reprocess', 'Reprocess'),
        ('upload_fail', 'Upload Failed'),
        ('uploaded', 'Uploaded')
    )

    kdip_id = models.CharField(max_length=100, unique=True)
    'This is the same as the directory name'
    create_date = models.DateTimeField()
    'Create time of the directory'
    status = models.CharField(max_length=20, choices=KDIP_STATUSES, default='invalid')
    'status of the KDip'
    note = models.CharField(max_length=200, blank=True, verbose_name='EnumCron')
    'Notes about this packagee, initially looked up from bib record'
    reason = models.CharField(max_length=1000, blank=True)
    'If the KDIP is invalid this will be populated with the first failed condition'
    job = models.ForeignKey('Job', null=True, blank=True, on_delete=models.SET_NULL)
    ':class:`Job` of which it is a part'
    path = models.CharField(max_length=400, blank=True)
    'Path of the KDIP on the file system'
    oclc = models.CharField(max_length=100, blank=True)
    'OCLC number from MARCXML'
    mms_id = models.CharField(max_length=100, blank=True)
    'mms_id from Alma'
    pid = models.CharField(max_length=5, blank=True)
    'Pid that was generated in the pid man'
    notes = models.TextField(blank=True, default='')
    'Notes the user makes on the KDIP'
    accepted_by_ht = models.BooleanField(default=False, verbose_name='HT')
    'Boolean that is set to true by the `check_ht` command when volume is live on HT'
    accepted_by_ia = models.BooleanField(default=False, verbose_name='IA')
    'Boolean set by user if volume is live in IA'
    al_ht = models.BooleanField(default=False, verbose_name="AL-HT")
    'Boolean that is set to true by the `check_al` command when the HT link appears in the MARCXML'

    @property
    def barcode(self):
        return self.kdip_id[:12]

    @property
    def errors(self):
        error_types = self.validationerror_set.values('error_type').distinct()
        errors = []
        for error in error_types:
            errors.append(error['error_type'])
        errors_list = ", ".join(errors)
        return errors_list

    @property
    def ht_url(self):
        if self.accepted_by_ht is True:
            ht_stub = getattr(settings, 'HT_STUB', None)
            return '%s%s' % (ht_stub, self.kdip_id)
        else:
            return None

    @property
    def process_dir(self):
        return '%s/HT/%s' % (settings.KDIP_DIR, self.kdip_id)

    @property
    def meta_yml(self):
        return '%s/%s/meta.yml' % (self.path, self.kdip_id)

    @property
    def marc_xml(self):
        return '%s/%s/marc.xml' % (self.path, self.kdip_id)

    @property
    def mets_xml(self):
        return '%s/%s/METS/%s.mets.xml' % (self.path, self.kdip_id, self.kdip_id)

    @property
    def mets_dir(self):
        return "%s/%s/METS/" % (self.path, self.kdip_id)

    @property
    def tif_dir(self):
        return "%s/%s/TIFF/" % (self.path, self.kdip_id)

    #@classmethod
    def validate(self):
        '''
        Validates mets files, rights, tiff files and marcxml.
        '''

        logger.info('Starting validation of %s' % (self.kdip_id))

        # Create the YAML file for HT. We do it here, instead of on load
        # because we want it to recreate on reporcessing.
        # bib_rec = Utils.load_bib_record(self.kdip_id)
        # capture_agent = bib_rec.tag_583_5
        Utils.create_yaml(self)

        # Check the dates to see if the volume is in copyright.
        try:
            # Load the MARC XML
            bib_rec = Utils.load_bib_record(self)

            # Check if there is a subfied 5 in the 583 tag
            if not bib_rec.tag_583_5:
                reason = 'No 583 tag in marc record.'
                error = ValidationError( \
                    kdip=self, error=reason, error_type="Inadequate Rights")
                error.save()

            # Get the published date
            date = Utils.get_date(bib_rec.tag_008, self.note)

            # If we don't find a date, note the error.
            if date is None:
                reason = 'Could not determine date for %s' % self.kdip_id
                logger.error(reason)

            # Otherwise, see if it is in copyright.
            else:
                rights = Utils.get_rights(date, bib_rec.tag_583x)
                if rights is not None:
                    logger.error(rights)
                    error = ValidationError( \
                        kdip=self, error=rights, error_type="Inadequate Rights")
                    error.save()

        except Exception as rights_error:
            reason = 'Could not determine rights'
            error = ValidationError(kdip=self, error=reason, error_type="Inadequate Rights")
            error.save()

        # Mets file exists
        logger.info('Checking for Mets File.')
        if not os.path.exists(self.mets_xml):
            reason = "Error: %s does not exist" % self.mets_xml
            logger.error(reason)
            error = ValidationError(kdip=self, error=reason, error_type="Missing Mets")
            error.save()

        try:
            logger.info('Loading Mets file into eulxml.')
            mets = load_xmlobject_from_file(self.mets_xml, Mets)

        except:
            reason = 'Error \'%s\' while loading Mets' % (sys.exc_info()[0])
            error = ValidationError(kdip=self, error=reason, error_type="Loading Mets")
            error.save()

        try:
            #mets file validates against schema
            if mets.is_valid() is not True:
                reason = "Error: %s is not valid" % self.mets_xml
                logger.error(reason)
                error = ValidationError(kdip=self, error=reason, error_type="Invalid Mets")
                error.save()
        except:
            error = ValidationError(kdip=self, error='Unable to validate Mets.', error_type="Invalid Mets")
            error.save()

        logger.info('Gathering tiffs.')

        tiffs = glob.glob('%s/*.tif' % self.tif_dir)

        logger.info('Checking tiffs.')
        for tiff in tiffs:
            logger.info('Sending %s for validation' % tiff)
            validate_tif = ValidateTiff(tiff, self)
            validate_tif.validate_tiffs()

        # validate each file of type ALTO and OCR
        for file_ref in mets.techmd:

            # Olny get the Tiffs.
            if '.tif' in file_ref.href.lower():
                file_path = "%s%s" % (self.mets_dir, file_ref.href)

                if not os.path.exists(file_path):
                    reason = "Error: %s does not exist" % file_path
                    logger.error(reason)
                    error = ValidationError(kdip=self, error=reason, error_type="Missing Tiff")
                    error.save()

                # checksum good
                with open(file_path, 'rb') as file_to_check:
                    if not file_ref.checksum == \
                        md5(file_to_check.read()).hexdigest():

                        reason = "Error: checksum does not match for %s" % file_path

                        logger.error(reason)

                        error = ValidationError(kdip=self, error=reason, error_type="Checksum")
                        error.save()

        # if it gets here were are good
        if self.validationerror_set.all():
            self.status = 'invalid'
        else:
            self.status = 'new'
        self.save()
        return True

    @classmethod
    def load(self, *args, **kwargs):
        "Class method to scan data directory specified in the ``localsettings`` **KDIP_DIR** and create new KDIP objects in the database."

        # The only thing that should be sending any args is when the kdip is
        # set to reporcess and the kdip object will be the first (and only) arg.
        if args:
            reproc_kdip = args[0]
            # We need to make sure that we are sending the rights
            # type of object. Just sending `args[0]` had issues.
            # Most noteably with the Mets validation.
            kdip = KDip.objects.get(pk=reproc_kdip.id)
            # Clear out previous validation errors.
            errors = kdip.validationerror_set.all()
            errors.delete()
            kdip.validate()
            Utils.create_ht_marc(kdip)

        else:
            kdip_list = {}
            exclude = ['%s/HT' % kdip_dir, '%s/out_of_scope' % kdip_dir, '%s/test' % kdip_dir]

            for path, subdirs, files in os.walk(kdip_dir):
                for dir in subdirs:
                    kdip = re.search(r"^[0-9]", dir)
                    full_path = os.path.join(path, dir)

                    # Only process new KDips or ones.
                    try:
                        skip = getattr(settings, 'SKIP_DIR', None)
                        if skip not in path:
                            processed_KDip = KDip.objects.get(kdip_id = dir)
                            # Check to see if the a KDip has moved and update the path.
                            if processed_KDip != path:
                                processed_KDip.path = path
                                processed_KDip.save()
                    except KDip.DoesNotExist:
                        if kdip and full_path not in exclude:
                            kdip_list[dir] = path

            # Empty list to gather errant KDips
            bad_kdips = []

            # create the KDIP is it does not exits
            for k in kdip_list:
                try:
                    # lookkup bib record for note field
                    bib_rec = Utils.create_ht_marc(k[:12])
                    # Find the OCLC in the MARCXML
                    # First an empty list to put all the 035 tags in
                    oclc_tags = []
                    for oclc_tag in bib_rec.tag_035a:
                        oclc_search = re.search('<.*>(.*?)</.*>', oclc_tag.serialize())
                        # Make a readable list of 035$a tags
                        oclc_tags.append(oclc_search.group(1))
                    # The oclc filed can have a few patterns. We want the first match
                    oclc = next(oclc_val for oclc_val in oclc_tags \
                        if "(OCoLC)" in oclc_val \
                        or "ocm" in oclc_val \
                        or "ocn" in oclc_val \
                        and bib_rec.alma_number not in oclc_val)
                    # Remove all non-numeric characters
                    oclc = re.sub("[^0-9]", "", oclc)

                    # Set the note field to 'EnumCron not found' if the 999a filed
                    # is empty or missing.
                    note = bib_rec.note(k[:12]) or 'EnumCron not found'

                    defaults={
                       'create_date': datetime.fromtimestamp(os.path.getctime('%s/%s' % (kdip_list[k], k))),
                        'note': note,
                        'path': kdip_list[k],
                        'oclc': oclc
                    }

                    kdip, created = self.objects.get_or_create(kdip_id=k, defaults = defaults)
                    if created:
                        logger.info("Created KDip %s" % kdip.kdip_id)

                        if kwargs.get('kdip_enumcron'):
                            kdip.note = kwargs.get('kdip_enumcron')
                            Utils.update_999a(kdip.path, kdip.kdip_id, kwargs.get('kdip_enumcron'))

                        if kwargs.get('kdip_pid'):
                            kdip.pid = kwargs.get('kdip_pid')

                        kdip.validate()

                        # If the KDip had errors, add it to the list so an email alert can be sent.
                        if kdip.status == 'invalid':
                            bad_kdips.append(kdip.kdip_id)

                    # else:
                    #     kdip.validate()


                except:
                    bad_kdips.append(k)
                    logger.error("Error creating KDip %s : %s" % (k, sys.exc_info()[0]))

            bad_kdip_list = '\n'.join(map(str, bad_kdips))

    def __unicode__(self):
        return self.kdip_id

    class Meta:
        ordering = ['-pk']


    def save(self, *args, **kwargs):

        if self.status == 'reprocess':
            # KDip.objects.filter(id = self.id).delete()
            KDip.load(self)
            #self.validate()
            return HttpResponseRedirect('/admin/publish/kdip/?q=%s' % self.kdip_id)

        else:
            if self.pk is not None:
                # If the note has been updated we need to write that to the Marc file.
                orig = KDip.objects.get(pk=self.pk)
                if orig.note != self.note:
                    Utils.update_999a(self.path, self.kdip_id, self.note)

            super(KDip, self).save(*args, **kwargs)


class Job(models.Model):
    "This class collects :class:`KDip` objects into logical groups for later processing"

    JOB_STATUSES = (
        ('new', "New"),
        ('ready for zephir', 'Ready for Zephir'),
        ('waiting on zephir', 'Waiting on Zephir'),
        ('zephir upload error', 'Zephir Upload Error'),
        ('zephir error', 'Zephir Error'),
        ('ready for hathi', 'Ready for Hathi'),
        ('uploading', 'Uploading to HathiTrust'),
        ('retry', 'Retry Upload'),
        ('failed', 'Upload Failed'),
        ('being processed', 'Being Processed'),
        ('processed', 'Processed'),
        ('processed by ht', 'Processed by HT')
    )

    name = models.CharField(max_length=100, unique=True)
    'Human readable name of job'
    status = models.CharField(max_length=20, choices=JOB_STATUSES, default='new')

    @property
    def volume_count(self):
        return self.kdip_set.all().count()

    @property
    def upload_attempts(self):
        return self._upload_attempts

    @property
    def uploaded(self):
        uploaded_count = self.kdip_set.filter(status='uploaded') \
            .count()
        return '%s/%s' % (uploaded_count, self.volume_count)

    _upload_attempts = 0

    @upload_attempts.setter
    def upload_attempts(self, value):
        self._upload_attempts = value

    def __unicode__(self):
        return self.name


    class Meta:
        ordering = ['-pk']

    def save(self, *args, **kwargs):

        if (self.status == 'ready for hathi') or (self.status == 'retry'):
            if self.status == 'retry':
                # Reset the status on the failed KDips so they will be retried.
                for k in self.kdip_set.all():
                    if k.status == 'upload_fail':
                        k.status = 'new'
                        k.save()
            # Send volumes to the upload task.
            self.status = 'uploading'
            # Add the celery task.
            # At this point the work is passed off to rq and executes
            # `tasks.py`
            from tasks import upload_for_ht
            queue = django_rq.get_queue()
            queue.enqueue(upload_for_ht, self)

        elif self.status == 'ready for zephir':
            zephir_status = send_to_zephir(self)
            # Set status
            self.status = zephir_status

        super(Job, self).save(*args, **kwargs)

class ValidationError(models.Model):
    kdip = models.ForeignKey(KDip)
    error = models.CharField(max_length=255)
    error_type = models.CharField(max_length=25)

class BoxToken(models.Model):
    refresh_token = models.CharField(max_length=200, blank=True)
    client_id = models.CharField(max_length=200, blank=True)
    client_secret = models.CharField(max_length=200, blank=True)
