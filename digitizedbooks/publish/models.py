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
from background_task import background

from eulxml.xmlmap import XmlObject
from eulxml.xmlmap import load_xmlobject_from_string, load_xmlobject_from_file
from eulxml.xmlmap.fields import StringField, NodeListField, IntegerField
from pidservices.clients import parse_ark
from pidservices.djangowrapper.shortcuts import DjangoPidmanRestClient

from PIL import Image

import logging
import zipfile
import yaml
import glob
import box
import json
import subprocess
import hashlib

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

def get_rights(self):
    """
    Get the Marc 21 bib record
    Rights validation is based on HT's Automated Bibliographic Rights Determination
    http://www.hathitrust.org/bib_rights_determination
    """
    rights = ''
    reason = ''
    try:
        r = requests.get('http://library.emory.edu/uhtbin/get_bibrecord', params={'item_id': self.barcode})
        bib_rec = load_xmlobject_from_string(r.text.encode('utf-8'), Marc)

        if not bib_rec.tag_583_5:
            reason = 'No 583 tag in marc record.'
            error = ValidationError(kdip=self, error=reason, error_type="Inadequate Rights")
            error.save()
            #return 'No 583 tag in marc record.'

        tag_008 = bib_rec.tag_008
        data_type = tag_008[6]
        date1 = tag_008[7:11]
        date1 = int(date1)
        date2 = tag_008[11:15]
        pub_place = tag_008[15:18]
        pub_place17 = tag_008[17]
        govpub = tag_008[28]

        # This is not really needed now but will be needed for Gov Docs
        imprint = ''
        if bib_rec.tag_260:
            imprint = bib_rec.tag_260
        elif bib_rec.tag_261a:
            imprint = bib_rec.tag_261a
        else:
            imprint = 'mult_260a_non_us'
            logger.warn('%s flaged as %s' % (self.kdip_id, imprint))

        # Check to see if Emory thinks it is public domain
        #if bib_rec.tag_583x == 'public domain':
        # Now we go through HT's algorithm to determin rights
        # US Docs
        if pub_place17 == 'u':
            # Gov Docs
            if govpub == 'f':
                logger.info('This is a government doc.')
            #    if 'ntis' in inprint:
            #        rights = 'ic'
            #    elif 'smithsonian' in tag_110 and date1 >= 1923: # or 130, 260 or 710
            #        rights = 'ic'
            #    #elif NIST-NSRDS (series field 400|410|411|440|490|800|810|811|830 contains 'nsrds' or 'national standard reference data series')
            #    #    or Federal Reserve (author field 100|110|111|700|710|711 contains "federal reserve")
            #    #    and pub_date >= 1923
            #    else:
            #        rights = 'pd'
            ## Non gov docs
            else:
                if date1 >= 1873 and date1 <= 1922:
                    rights = 'pdus'
                elif date1 < 1923:
                    rights = 'pd'
                else:
                    reason = ('%s was published in %s' % (self.kdip_id, date1))
                    logger.error(reason)
                    rights = 'ic'

        # Non-US docs
        else:
            logger.info('%s is not a US publication' % (self.kdip_id))
            if date1 < 1873:
                rights = 'pd'
            elif date1 >= 1873 and date1 < 1923:
                rights = 'pdus'
            else:
                reason = '%s is non US and was published in %s' % (self.kdip_id, date1)
                logger.error(reason)
                rights = 'ic'

        if bib_rec.tag_583x != 'public domain':
            rights = 'ic'
            reason = '583X does not equal "public domain" for %s' % (self.kdip_id)

    except Exception as e:
        reason = 'Could not determine rights for %s' % (self.kdip_id)
        error = ValidationError(kdip=self, error=reason, error_type="Inadequate Rights")
        error.save()
        #return reason
    if rights is not 'ic':
        logger.info('%s rights set to %s' % (self.kdip_id, rights))
        #return 'public'
    else:
        error = ValidationError(kdip=self, error=reason, error_type="Inadequate Rights")
        error.save()
        #return reason

def validate_tiffs(tiff_file, kdip, kdip_dir, kdipID):
    '''
    Method to validate the Tiff files.
    Site for looking up Tiff tags: http://www.awaresystems.be/imaging/tiff/tifftags/search.html
    '''
    tif_tags = {
        'ImageWidth': 256,
        'ImageLength': 257,
        'BitsPerSample': 258,
        'Compression': 259,
        'PhotometricInterpretation': 262,
        'DocumentName': 269,
        'Make': 271,
        'Model': 272,
        'Orientation': 274,
        'XResolution': 282,
        'YResolution': 283,
        'ResolutionUnit': 296,
        'DateTime': 306,
        'ImageProducer': 315,
        #'BitsPerPixel': 37122,
        'ColorSpace': 40961,
        'SamplesPerPixel': 277
    }

    bittsPerSample = {
        '1': 'Bitonal',
        '3': 'Color-3',
        '8': 'Grayscale',
        '888': 'Color-888',
        '88': 'Two channel grayscale'
    }

    compressions = {
        'Uncompressed': (1,),
        'T6/Group 4 Fax': (4,),
        'LZW': (5,)
    }

    photometricInterpretation = {
        'WhiteIsZero': (0,),
        'BlackIsZero': (1,),
        'RGB': (2,)
    }

    samplesPerPixel = {
        'Grayscale': '(1,)',
        'RGB': '(3,)'
    }

    missing = []
    found = {}
    skipalbe = ['ImageProducer', 'DocumentName', 'Make', 'Model', 'ColorSpace']
    yaml_data = {}

    image = ''
    logger.info('Checking %s' % tiff_file)
    try:
        image = Image.open(tiff_file)

        tags = image.tag
        for tif_tag in tif_tags:
            valid = tags.has_key(tif_tags[tif_tag])
            if valid is False:
                found[tif_tag] = False

            if valid is True:
                found[tif_tag] = tags.get(tif_tags[tif_tag])


        dt = datetime.strptime(found['DateTime'], '%Y:%m:%d %H:%M:%S')
        yaml_data['capture_date'] = dt.isoformat('T')
        with open('%s/%s/meta.yml' % (kdip_dir, kdip), 'a') as outfile:
            outfile.write( yaml.dump(yaml_data, default_flow_style=False) )
        logger.info('Yaml written')

        ## START REAL VALIDATION
        if found['ImageWidth'] <= 0:
            logger.error('Image Width = %s for %s' %(found['ImageWidth'], tiff_file))
            status = 'Invalid value for ImageWidth in %s' % (tiff_file)
            error = ValidationError(kdip=kdipID, error=status, error_type="Invalid Tiff")
            error.save()
            #return status
        else:
            logger.debug('Image width for %s is %s' % (tiff_file, found['ImageWidth']))

        if found['ImageLength']  <= 0:
            logger.error('ImageLength = %s for %s' %(found['ImageLength'], tiff_file))
            status = 'Invalid value for ImageLength in %s' % (tiff_file)
            error = ValidationError(kdip=kdipID, error=status, error_type="Invalid Tiff")
            error.save()
            #return status
        else:
            logger.debug('ImageLength = %s for %s' %(found['ImageLength'], tiff_file))

        if not found['Make']:
            logger.error('Make = %s for %s' %(found['Make'], tiff_file))
            status = 'Invalid value for Make in %s' % (tiff_file)
            error = ValidationError(kdip=kdipID, error=status, error_type="Invalid Tiff")
            error.save()
            #return status
        else:
            logger.debug('Make = %s for %s' %(found['Make'], tiff_file))

        if not found['Model']:
            logger.error('Model = %s for %s' %(found['Model'], tiff_file))
            status = 'Invalid value for Make in %s' % (tiff_file)
            error = ValidationError(kdip=kdipID, error=status, error_type="Invalid Tiff")
            error.save()
            #return status
        else:
            logger.debug('Model = %s for %s' %(found['Model'], tiff_file))

        if found['Orientation'] != (1,):
            logger.error('Orientation = %s for %s' %(found['Orientation'], tiff_file))
            status = 'Invalid value for Orientation in %s' % (tiff_file)
            error = ValidationError(kdip=kdipID, error=status, error_type="Invalid Tiff")
            error.save()
            #return status
        else:
            logger.debug('Orientation = %s for %s' %(found['Orientation'], tiff_file))

        #if found['ColorSpace'] != 1:
        #    status = 'Invalid value for ColorSpace in %s' % (file)
        #    return status

        if found['ResolutionUnit'] != (2,):
            logger.error('ResolutionUnit = %s for %s' %(found['ResolutionUnit'], tiff_file))
            status = 'Invalid value for ResolutionUnit in %s' % (tiff_file)
            error = ValidationError(kdip=kdipID, error=status, error_type="Invalid Tiff")
            error.save()
            #return status
        else:
            logger.debug('ResolutionUnit = %s for %s' %(found['ResolutionUnit'], tiff_file))

        if not found['DateTime']:
            logger.error('DateTime = %s for %s' %(found['DateTime'], tiff_file))
            status = 'Invalid value for DateTime in %s' % (tiff_file)
            error = ValidationError(kdip=kdipID, error=status, error_type="Invalid Tiff")
            error.save()
            #return status
        else:
            logger.debug('DateTime = %s for %s' %(found['DateTime'], tiff_file))

        image_code = re.sub("[^0-9]", "", str(found['BitsPerSample']))
        image_type = bittsPerSample[image_code]

        ## Check if Two channel grayscale
        #if imgtype == bittsPerSample['Two channel grayscale']:
        #    status = 'Two channel grayscale, needs conversion'
        #    return status

        # GRAYSCALE OR BITONAL
        logger.info('Checking type')
        if image_type is 'Bitonal' or image_type is 'Grayscale':

            logger.info('%s is Bitonal' % tiff_file)

            if found['Compression'] == compressions['Uncompressed'] or found['Compression'] == compressions['T6/Group 4 Fax']:
                logger.debug('Compression is %s for %s' % (found['Compression'], tiff_file))
            else :
                status = 'Invalid value for PhotometricInterpretation in %s' % (tiff_file)
                error = ValidationError(kdip=kdipID, error=status, error_type="Invalid Tiff")
                error.save()

            if str(found['SamplesPerPixel']) != samplesPerPixel['Grayscale']:
                status = 'Invalid value for SamplesPerPixel in %s' % (tiff_file)
                error = ValidationError(kdip=kdipID, error=status, error_type="Invalid Tiff")
                error.save()
            else:
                logger.debug('SamplesPerPixel is %s for %s' % (found['SamplesPerPixel'], tiff_file))

            if found['XResolution'] < 600:
                logger.error('XResolution is %s for %s' %(found['XResolution'], tiff_file))
                status = 'Invalid value for XResolution in %s' % (tiff_file)
                error = ValidationError(kdip=kdipID, error=status, error_type="Invalid Tiff")
                error.save()
            else:
                logger.debug('XResoloution is %s for %s' % (found['XResolution'], tiff_file))

            if found['YResolution'] < 600:
                logger.error('YResolution is %s for %s' % (found['YResolution'], tiff_file))
                status = 'Invalid value for YResolution in %s' % (tiff_file)
                error = ValidationError(kdip=kdipID, error=status, error_type="Invalid Tiff")
                error.save()
            else:
                logger.debug('YResolution is %s for %s' % (found['YResolution'], tiff_file))

        # COLOR
        elif image_type is 'Color-3' or image_type is 'Color-888':

            logger.info('%s is Color' % tiff_file)

            if found['Compression'] == compressions['Uncompressed'] or found['Compression'] == compressions['LZW']:
                logger.debug('Compression is %s for %s' % (found['Compression'], tiff_file))
            else:
                status = 'Invalid value for Compression in %s' % (tiff_file)
                error = ValidationError(kdip=kdipID, error=status, error_type="Invalid Tiff")
                error.save()

            if found['PhotometricInterpretation'] != photometricInterpretation['RGB']:
                status = 'Invalid value for PhotometricInterpretation in %s' % (tiff_file)
                error = ValidationError(kdip=kdipID, error=status, error_type="Invalid Tiff")
                error.save()
            else:
                logger.debug('PhotometricInterpretation is %s for %s' % (found['PhotometricInterpretation'], tiff_file))

            if str(found['SamplesPerPixel']) != samplesPerPixel['RGB']:
                logger.error('SamplesPerPixel is %s for %s' % (found['SamplesPerPixel'], tiff_file))
                status = 'Invalid value for SamplesPerPixel in %s' % (tiff_file)
                error = ValidationError(kdip=kdipID, error=status, error_type="Invalid Tiff")
                error.save()
            else:
                logger.debug('SamplesPerPixel is %s for %s' % (found['SamplesPerPixel'], tiff_file))

            if found['XResolution'] < 300:
                status = 'Invalid value for XResolution in %s' % (tiff_file)
                error = ValidationError(kdip=kdipID, error=status, error_type="Invalid Tiff")
                error.save()
            else:
                logger.debug('XResolution is %s for %s' % (found['XResolution'], tiff_file))

            if found['YResolution'] < 300:
                status = 'Invalid value for YResolution in %s' % (tiff_file)
                error = ValidationError(kdip=kdipID, error=status, error_type="Invalid Tiff")
                error.save()
            else:
                logger.debug('YResolution is %s for %s' % (found['YResolution'], tiff_file))

        else:
            status = 'Cannot determine type for %s' % (tiff_file)
            error = ValidationError(kdip=kdipID, error=status, error_type="Invalid Tiff")
            error.save()

    except:
        status = 'Error \'%s\' while validating %s' % (sys.exc_info()[1], tiff_file)
        logger.error(status)
        error = ValidationError(kdip=kdipID, error=status, error_type='Bad Tiff File')
        error.save()



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
    techmd = NodeListField('mets:amdSec/mets:techMD', METStechMD)


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


class Marc(MarcBase):
    "Top level MARC xml object"
    ROOT_NS = 'http://www.loc.gov/MARC21/slim'
    ROOT_NAME = 'collection'

    datafields = NodeListField('marc:record/marc:datafield', MarcDatafield)
    "list of marc datafields"

    tag_583x = StringField('marc:record/marc:datafield[@tag="583"]/marc:subfield[@code="x"]')
    # 583 code5 where a is 'digitized' or 'selected for digitization'
    # this will be for 'capture_agent' in yaml file

    tag_583_5 = StringField('marc:record/marc:datafield[@tag="583"][@ind1="1"]/marc:subfield[@code="5"]/text()')

    tag_008 = StringField('marc:record/marc:controlfield[@tag="008"]')

    tag_260 = StringField('marc:record/marc:datafield[@tag="260"]')
    tag_261a = StringField('marc:record/marc:datafield[@tag="264"][@ind2="1"]/marc:subfield[@code="a"]/text()')

    tag_999 = NodeListField("marc:record/marc:datafield[@tag='999']", MarcDatafield)

    tag_999a = StringField('marc:record/marc:datafield[@tag="999"]/marc:subfield[@code="a"]')

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



class Alto(XmlObject):
    '''
    Instance of ALTO xml object. Currently this is only used for schema validation
    '''
    XSD_SCHEMA = 'http://www.loc.gov/standards/alto/alto-v2.0.xsd'
    ROOT_NAME = 'alto'



# DB Models
class KDip(models.Model):
    "Class to describe Kirtas output directories"
    KDIP_STATUSES = (
        ('new', 'New'),
        ('processed', 'Processed'),
        ('archived', 'Archived'),
        ('invalid', 'Invalid'),
        ('do not process', 'Do Not Process'),
        ('reprocess', 'Reprocess')
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
    pid = models.CharField(max_length=5, blank=True)

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


    def validate(self):
        '''
        Validates the mets file and files referenced in the mets.
        '''

        logger.info('Starting validation of %s' % (self.kdip_id))
        # all paths (except for TOC) are relitive to METS dir
        mets_dir = "%s/%s/METS/" % (self.path, self.kdip_id)

        mets_file = "%s%s.mets.xml" % (mets_dir, self.kdip_id)

        toc_file = "%s/%s/TOC/%s.toc" % (self.path, self.kdip_id, self.kdip_id)

        tif_dir = "%s/%s/TIFF/" % (self.path, self.kdip_id)

        rights = get_rights(self)

        #if rights is not 'public':
        #    self.reason = rights
        #    if 'Could not' in rights:
        #        self.status = 'invalid'
        #    else:
        #        self.status = 'do not process'
        #    self.save()
        #    logger.error(rights)
        #    return False

        #Mets file exists
        logger.info('Cheking for Mets File.')
        if not os.path.exists(mets_file):
            reason = "Error: %s does not exist" % mets_file
            #self.reason = reason
            #self.status = 'invalid'
            #self.save()
            logger.error(reason)
            error = ValidationError(kdip=self, error=reason, error_type="Missing Mets")
            error.save()
            #return False

        logger.info('Loading Mets file into eulxml.')
        try:
            mets = load_xmlobject_from_file(mets_file, Mets)

            #mets file validates against schema
            logger.info('Cheking if Mets is valid.')
            if not mets.is_valid():
                reason = "Error: %s is not valid" % mets_file
                #self.reason = reason
                #self.status = 'invalid'
                #self.save()
                logger.error(reason)
                error = ValidationError(kdip=self, error=reason, error_type="Invalid Mets")
                error.save()
                #return False
        except:
            reason = 'Error \'%s\' while loading Mets' % (sys.exc_info()[0])
            error = ValidationError(kdip=self, error=reason, error_type="Loading Mets")
            error.save()

        logger.info('Gathering tiffs.')
        tif_status = None
        tiffs = glob.glob('%s/*.tif' % tif_dir)

        #tif_status = validate_tiffs(tiffs[0], self.kdip_id, self.path)
        logger.info('Checking tiffs.')
        for tiff in tiffs:
            logger.info('Sending %s for validation' % tiff)
            tif_status = validate_tiffs(tiff, self.kdip_id, self.path, self)

        #if tif_status is not None:
        #    self.reason = tif_status
        #    self.status = 'invalid'
        #    self.save()
        #    logger.error(tif_status)
        #    return False

        # validate each file of type ALTO and OCR
        for f in mets.techmd:
            file_path = "%s%s" % (mets_dir, f.href)

            if not os.path.exists(file_path):
                reason = "Error: %s does not exist" % file_path
                #self.reason = reason
                #self.status = 'invalid'
                #self.save()
                logger.error(reason)
                error = ValidationError(kdip=self, error=reason, error_type="Missing Tiff or Alto")
                error.save()
                #return False

            # checksum good
            with open(file_path, 'rb') as file:
                if not f.checksum == md5(file.read()).hexdigest():
                    reason = "Error: checksum does not match for %s" % file_path
                    #logger.error('%s Mets is %s,  file is %s' % (self.kdip_id, f.checksum, md5(file.read()).hexdigest()))
                    #self.reason = reason
                    #self.status = 'invalid'
                    #self.save()
                    logger.error(reason)
                    #return False
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

        kdip_list = {}

        exclude = ['%s/HT' %kdip_dir, '%s/out_of_scope' % kdip_dir, '%s/test' % kdip_dir]

        for path, subdirs, files in os.walk(kdip_dir):
            for dir in subdirs:
                kdip = re.search(r"^[0-9]", dir)
                full_path = os.path.join(path, dir)

                # Only process new KDips or ones.
                try:
                    if path not in exclude:
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
                r = requests.get('http://library.emory.edu/uhtbin/get_bibrecord', params={'item_id': k[:12]})
                bib_rec = load_xmlobject_from_string(r.text.encode('utf-8'), Marc)

                # Remove extra 999 fileds. We only want the one where the 'i' code matches the barcode.
                for datafield in bib_rec.tag_999:
                    i999 = datafield.node.xpath('marc:subfield[@code="i"]', namespaces=Marc.ROOT_NAMESPACES)[0].text
                    if i999 != k[:12]:
                        bib_rec.tag_999.remove(datafield)

                defaults={
                   'create_date': datetime.fromtimestamp(os.path.getctime('%s/%s' % (kdip_list[k], k))),
                    'note': bib_rec.note(k[:12]),
                    'path': kdip_list[k]
                }
                kdip, created = self.objects.get_or_create(kdip_id=k, defaults = defaults)
                if created:
                    logger.info("Created KDip %s" % kdip.kdip_id)


                    with open('%s/%s/marc.xml' % (kdip_list[k], kdip.kdip_id), 'w') as marcxml:
                        marcxml.write(bib_rec.serialize(pretty=True))

                    try:
                        os.remove('%s/%s/meta.yml' % (kdip_list[k], kdip.kdip_id))
                    except OSError:
                        pass

                    yaml_data = {}
                    yaml_data['capture_agent'] = str(bib_rec.tag_583_5)
                    yaml_data['scanner_user'] = 'Emory University: LITS Digitization Services'
                    yaml_data['scanning_order']= 'left-to-right'
                    yaml_data['reading_order'] = 'left-to-right'
                    with open('%s/%s/meta.yml' % (kdip_list[k], kdip.kdip_id), 'a') as outfile:
                        outfile.write( yaml.dump(yaml_data, default_flow_style=False) )

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
        contact = send_from = getattr(settings, 'EMORY_CONTACT', None)
        send_mail('Invalid KDips', 'The following KDips were loaded but are invalid:\n\n%s' % bad_kdip_list, contact, [contact], fail_silently=False)




    def __unicode__(self):
        return self.kdip_id

    class Meta:
        ordering = ['create_date']


    def save(self, *args, **kwargs):

        if self.status == 'reprocess':
            #KDip.objects.filter(id = self.id).delete()
            #KDip.load()
            self.validate()

        else:
            if self.pk is not None:
                # If the note has been updated we need to write that to the Marc file.
                orig = KDip.objects.get(pk=self.pk)
                if orig.note != self.note:
                    marc_file = '%s/%s/marc.xml' %(self.path, self.kdip_id)
                    marc = load_xmlobject_from_file(marc_file, Marc)
                    marc.tag_999a = self.note
                    with open(marc_file, 'w') as marcxml:
                        marcxml.write(marc.serialize(pretty=True))
            super(KDip, self).save(*args, **kwargs)


class Job(models.Model):
    "This class collects :class:`KDip` objects into logical groups for later processing"

    JOB_STATUSES = (
        ('new', "New"),
        ('ready for zephir', 'Ready for Zephir'),
        ('ready for hathi', 'Ready for Hathi'),
        ('failed', 'Upload Failed'),
        ('being processed', 'Being Processed'),
        ('processed', 'Processed')
    )

    name = models.CharField(max_length=100, unique=True)
    'Human readable name of job'
    status = models.CharField(max_length=20, choices=JOB_STATUSES, default='new')

    @property
    def volume_count(self):
        return self.kdip_set.all().count()

    def __unicode__(self):
        return self.name


    @background(schedule=10)
    def upload(kdips, job_id):

        def zipdir(path, zip):
            for root, dirs, files in os.walk(path):
                for file in files:
                    zip.write(os.path.join(root, file))

        def checksumfile(checkfile, process_dir):
            with open(checkfile, 'rb') as file:
                with open('%s/checksum.md5' % (process_dir), 'a') as outfile:
                    if 'alto' in checkfile:
                        checkfile = checkfile.replace('.alto', '')
                    filename = checkfile.split('/')
                    outfile.write('%s %s\n' % ((md5(file.read()).hexdigest()), filename[-1]))

        def checksumverify(checksum, process_dir, file):
            with open('%s/%s' % (process_dir, file), 'rb') as file:
                if md5(file.read()).hexdigest() == checksum:
                    return True
                else:
                    return False

        job = Job.objects.get(id=job_id)

        uploaded_files = []
        status = ''

        for process_kdip in kdips:
            kdip = KDip.objects.get(id=process_kdip)

            client = DjangoPidmanRestClient()
            pidman_domain = getattr(settings, 'PIDMAN_DOMAIN', None)
            pidman_policy = getattr(settings, 'PIDMAN_POLICY', None)

            ark = client.create_ark(domain='%s' % pidman_domain, target_uri='http://myuri.org', policy='%s' % pidman_policy, name='%s' % kdip.kdip_id)
            naan = parse_ark(ark)['naan']
            noid = parse_ark(ark)['noid']

            kdip.pid = noid
            kdip.save()

            logger.info("Ark %s was created for %s" % (ark, kdip.kdip_id))

            #process_dir = '%s/ark+=%s=%s' % (kdip.path, naan, noid)
            if not os.path.exists('%s/HT' % kdip_dir):
                os.mkdir('%s/HT' % kdip_dir)
            process_dir = '%s/HT/%s' % (kdip_dir, kdip.kdip_id)

            if not os.path.exists(process_dir):
                os.makedirs(process_dir)

            

            tiffs = glob.glob('%s/%s/TIFF/*.tif' % (kdip.path, kdip.kdip_id))
            for tiff in tiffs:
                checksumfile(tiff, process_dir)
                shutil.copy(tiff, process_dir)

            altos = glob.glob('%s/%s/ALTO/*.xml' % (kdip.path, kdip.kdip_id))
            for alto in altos:
                checksumfile(alto, process_dir)
                shutil.copy(alto, process_dir)
                if 'alto' in alto:
                    filename = alto.split('/')
                    page,crap,ext = filename[-1].split('.')
                    shutil.move(alto, '%s/%s.%s' % (process_dir, page, ext))
            #
            #new_altos = glob.glob('%s/*.alto.xml' % (process_dir))
            #for new_alto in new_altos:
            #    page,crap,ext = new_alto.split('.')
            #    shutil.move('%s' % (new_alto), '%s.%s' % (page, ext))

            ocrs = glob.glob('%s/%s/OCR/*.txt' % (kdip.path, kdip.kdip_id))
            for ocr in ocrs:
                checksumfile(ocr, process_dir)
                shutil.copy(ocr, process_dir)


            meta_yml = '%s/%s/meta.yml' % (kdip.path, kdip.kdip_id)
            marc_xml = '%s/%s/marc.xml' % (kdip.path, kdip.kdip_id)
            mets_xml = '%s/%s/METS/%s.mets.xml' % (kdip.path, kdip.kdip_id, kdip.kdip_id)

            checksumfile(meta_yml, process_dir)
            checksumfile(marc_xml, process_dir)
            checksumfile(mets_xml, process_dir)

            shutil.copy(meta_yml, process_dir)

            shutil.copy(marc_xml, process_dir)

            shutil.copy(mets_xml, process_dir)

            with open('%s/checksum.md5' % process_dir) as f:
                content = f.readlines()
                for line in content:
                    parts = line.split()
                    verify = checksumverify(parts[0], process_dir, parts[1])
                    if verify is not True:
                        logger.error('Checksum check failes for %s.' % process_dir  )

            zipf = zipfile.ZipFile('%s.zip' % (process_dir), 'w', allowZip64=True)
            os.chdir('%s' % (process_dir))
            zipdir('.', zipf)
            zipf.close()
            # Delete the process directory to save space
            shutil.rmtree(process_dir)

            token = BoxToken.objects.get(id=1)

            response = box.refresh_v2_token(token.client_id, token.client_secret, token.refresh_token)

            token.refresh_token = response['refresh_token']
            token.save()

            logger.info('New refresh token: %s' % (response['refresh_token']))

            box_folder = getattr(settings, 'BOXFOLDER', None)

            url = 'https://upload.box.com/api/2.0/files/content -H "Authorization: Bearer %s" -F filename=@%s.zip -F parent_id=%s' % (response['access_token'], process_dir, box_folder)

            upload = subprocess.check_output('curl %s' % (url), shell=True)

            upload_response = json.loads(upload)

            try:
                sha1 = hashlib.sha1()
                local_file = open('%s.zip' % (process_dir), 'rb')
                sha1.update(local_file.read())
                local_file.close()

                if sha1.hexdigest() == upload_response['entries'][0]['sha1']:
                    status = 'being processed'
                    #uploaded_files.append('ark+=%s=%s' % (naan, noid))
                    uploaded_files.append(kdip.kdip_id)

            except Exception as e:
                logger.error('Uploading %s.zip failed with message %s' % (process_dir, upload_response['message']))
                status = 'failed'

        if status == 'being processed':
            job.status = 'being processed'
            job.save()
            kdip_list = '\n'.join(map(str, uploaded_files))
            send_to = getattr(settings, 'HATHITRUST_CONTACT', None)
            send_from = getattr(settings, 'EMORY_CONTACT', None)
            send_mail('New Volumes from Emory have been uploaded', 'The following volumes have been uploaded and are ready:\n\n%s' % kdip_list, send_from, [send_to], fail_silently=False)


    class Meta:
        ordering = ['id']

    def save(self, *args, **kwargs):

        if self.status == 'ready for hathi':
            uploaded_files = []
            kdips = KDip.objects.filter(job=self.id)

            for kdip in kdips:
                uploaded_files.append(kdip.id)

            self.upload(uploaded_files, self.id)

        super(Job, self).save(*args, **kwargs)

class ValidationError(models.Model):
    kdip = models.ForeignKey(KDip)
    error = models.CharField(max_length=255)
    error_type = models.CharField(max_length=25)

class BoxToken(models.Model):
    refresh_token = models.CharField(max_length=200, blank=True)
    client_id = models.CharField(max_length=200, blank=True)
    client_secret = models.CharField(max_length=200, blank=True)