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

from eulxml.xmlmap import XmlObject
from eulxml.xmlmap import load_xmlobject_from_string, load_xmlobject_from_file
from eulxml.xmlmap.fields import StringField, NodeListField, IntegerField, NodeField

from PIL import Image

import logging
import yaml
import glob
from ftplib import FTP_TLS
import celery

#from digitizedbooks.publish.tasks import upload_for_ht
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

        image.close()

    except:
        status = 'Error \'%s\' while validating %s' % (sys.exc_info()[1], tiff_file)
        logger.error(status)
        error = ValidationError(kdip=kdipID, error=status, error_type='Bad Tiff File')
        error.save()
        image.close()



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

    fied_999 = StringField("marc:record/marc:datafield[@tag='999']", MarcDatafield)

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

def date_to_int(date):
    try:
        return int(date)
    except:
        return None

def get_date(tag_008, note):
    '''
    Figure out if we should use Date1, Date2 or the largest date looking
    thing in the EnumCron. This method is based on HathiTrust's docs:
    http://www.hathitrust.org/bib_rights_determination
    '''

    # Try to turn the date into an int. If that fails we will get
    # `None` back. We are also replacing any characters (but not spaces)
    # to `9` as per the HT documation.
    date1 = date_to_int(re.sub(r'[^\d\s]', '9', tag_008[7:11]))
    date2 = date_to_int(re.sub(r'[^\d\s]', '9', tag_008[11:15]))

    date_type = tag_008[6]

    group0 = ['m', 'p', 'q']

    group1 = ['r', 's', 'e']

    group2 = ['t']

    group3 = ['d', 'u', 'c', 'i', 'k']

    if date_type in group0:
        # Return the latest year
        dates = [date1, date2]
        return max(dates)

    elif date_type in group1:
        # Return Date1
        return date1

    elif date_type in group2:
        # if Date2 exists and Date2 > Date1, return Date2
        # otherwise we'll return Date1 whcih might be `None`.
        if date2 is not None:
            return date2
        else:
            return date1

    elif date_type in group3:
        # Look for groups of four digits that start with 1
        # and return the largest one.
        year_pattern = re.compile(r'1\d\d\d')
        dates = year_pattern.findall(note)
        return int(max(dates))

    else:
        # If all fails, return `None`.
        return None
def get_rights(date, tag_583x):
    """
    Method to see if the 593x tag in the MARC is equal to `public domain`
    or if the determined publicatin date is before 1923.
    """
    # Check to see if Emory thinks it is public domain
    if tag_583x != 'public domain':
        return '583X does not equal "public domain"'
    # Based on the HT docs, as long as the volume is before 1923
    # it's a go.
    elif date > 1922:
        return 'Published in %s' % (date)

    else:
        return None

def update_999a(path, kdip_id, enumcron):
    """
    Method to updae the 999a MARC field if/when it is changed
    in the database.
    """
    marc_file = '%s/%s/marc.xml' %(path, kdip_id)
    marc = load_xmlobject_from_file(marc_file, Marc)
    marc.tag_999a = enumcron
    with open(marc_file, 'w') as marcxml:
        marcxml.write(marc.serialize(pretty=True))

def remove_all_999_fields(marc_xml):
    """
    Method used by the check_ht manage command to remove all 999
    fileds from the MARC XML before going to Aleph
    """
    try:
        marc_xml.tag_999 = ''
    except:
        pass
    return marc_xml

def update_583(marc_xml):
    """
    Method used by check_ht manage command to upddate the
    583 filed to `ditigized`.
    """
    try:
        marc_xml.tag_583_a = 'digitized'
    except:
        pass
    return marc_xml

def create_yaml(capture_agent, path, kdip_id):
    """
    Method to create a YAML file with some basic default
    metadata for HathiTrust
    """
    yaml_data = {}
    yaml_data['capture_agent'] = capture_agent
    yaml_data['scanner_user'] = 'Emory University: LITS Digitization Services'
    yaml_data['scanning_order'] = 'left-to-right'
    yaml_data['reading_order'] = 'left-to-right'
    with open('%s/%s/meta.yml' % (path, kdip_id), 'a') as outfile:
        outfile.write(yaml.dump(yaml_data, default_flow_style=False))


def load_bib_record(barcode):
    """
    Method to load MARC XML from Aleph
    """
    get_bib_rec = requests.get( \
        'http://library.emory.edu/uhtbin/get_bibrecord', \
        params={'item_id': barcode})

    return load_xmlobject_from_string( \
        get_bib_rec.text.encode('utf-8'), Marc)

def load_local_bib_record(barcode):
    """
    Method to load local version of MARC XML from Aleph
    """
    get_bib_rec = requests.get( \
        'http://library.emory.edu/uhtbin/get_aleph_bibrecord', \
        params={'item_id': barcode})

    return load_xmlobject_from_string( \
        get_bib_rec.text.encode('utf-8'), Marc)

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
    notes = models.TextField(blank=True, default='')
    accepted_by_ht = models.BooleanField(default=False, verbose_name='HT')
    accepted_by_ia = models.BooleanField(default=False, verbose_name='IA')
    al_ht = models.BooleanField(default=False, verbose_name="AL-HT")

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

    #@classmethod
    def validate(self):
        '''
        Validates mets files, rights, tiff files and marcxml.
        '''

        logger.info('Starting validation of %s' % (self.kdip_id))

        # Check the dates to see if the volume is in copyright.
        try:
            # Load the MARC XML
            bib_rec = load_bib_record(self.barcode)

            # Check if there is a subfied 5 in the 583 tag
            if not bib_rec.tag_583_5:
                reason = 'No 583 tag in marc record.'
                error = ValidationError( \
                    kdip=self, error=reason, error_type="Inadequate Rights")
                error.save()

            # Get the published date
            date = get_date(bib_rec.tag_008, self.note)

            # If we don't find a date, note the error.
            if date is None:
                reason = 'Could not determine date for %s' % self.kdip_id
                logger.error(reason)

            # Otherwise, see if it is in copyright.
            else:
                rights = get_rights(date, bib_rec.tag_583x)
                if rights is not None:
                    logger.error(rights)
                    error = ValidationError( \
                        kdip=self, error=rights, error_type="Inadequate Rights")
                    error.save()

        except Exception as rights_error:
            reason = 'Could not determine rights'
            error = ValidationError(kdip=self, error=reason, error_type="Inadequate Rights")
            error.save()

        # all paths are relitive to METS dir
        mets_dir = "%s/%s/METS/" % (self.path, self.kdip_id)

        mets_file = "%s%s.mets.xml" % (mets_dir, self.kdip_id)

        tif_dir = "%s/%s/TIFF/" % (self.path, self.kdip_id)

        # Mets file exists
        logger.info('Cheking for Mets File.')
        if not os.path.exists(mets_file):
            reason = "Error: %s does not exist" % mets_file
            logger.error(reason)
            error = ValidationError(kdip=self, error=reason, error_type="Missing Mets")
            error.save()

        logger.info('Loading Mets file into eulxml.')
        try:
            mets = load_xmlobject_from_file(mets_file, Mets)

            #mets file validates against schema
            logger.info('Cheking if Mets is valid.')
            if not mets.is_valid():
                reason = "Error: %s is not valid" % mets_file
                logger.error(reason)
                error = ValidationError(kdip=self, error=reason, error_type="Invalid Mets")
                error.save()

        except:
            reason = 'Error \'%s\' while loading Mets' % (sys.exc_info()[0])
            error = ValidationError(kdip=self, error=reason, error_type="Loading Mets")
            error.save()

        logger.info('Gathering tiffs.')
        #tif_status = None
        tiffs = glob.glob('%s/*.tif' % tif_dir)

        logger.info('Checking tiffs.')
        for tiff in tiffs:
            logger.info('Sending %s for validation' % tiff)
            tif_status = validate_tiffs(tiff, self.kdip_id, self.path, self)

        # validate each file of type ALTO and OCR
        for file_ref in mets.techmd:

            # Olny get the Tiffs.
            if '.tif' in file_ref.href.lower():
                file_path = "%s%s" % (mets_dir, file_ref.href)

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

        kdip_list = {}

        if kwargs.get('kdip'):
            kdip_list[kwargs.get(('kdip_id'))] = kwargs.get('kdip_path')

        else:
            exclude = ['%s/HT' % kdip_dir, '%s/out_of_scope' % kdip_dir, '%s/test' % kdip_dir]

            for path, subdirs, files in os.walk(kdip_dir):
                for dir in subdirs:
                    kdip = re.search(r"^[0-9]", dir)
                    full_path = os.path.join(path, dir)

                    # Only process new KDips or ones.
                    try:
                        if 'test' not in path:
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
        print kdip_list
        for k in kdip_list:

            try:
                # lookkup bib record for note field
                bib_rec = load_bib_record(k[:12])

                # Remove extra 999 fileds. We only want the one where the 'i' code matches the barcode.
                for field_999 in bib_rec.tag_999:
                    i999 = field_999.node.xpath('marc:subfield[@code="i"]', \
                        namespaces=Marc.ROOT_NAMESPACES)[0].text
                    if i999 != k[:12]:
                        bib_rec.tag_999.remove(field_999)

                defaults={
                   'create_date': datetime.fromtimestamp(os.path.getctime('%s/%s' % (kdip_list[k], k))),
                    'note': bib_rec.note(k[:12]),
                    'path': kdip_list[k]
                }

                kdip, created = self.objects.get_or_create(kdip_id=k, defaults = defaults)
                if created:
                    logger.info("Created KDip %s" % kdip.kdip_id)

                    # Write the marc.xml to disk.
                    with open('%s/%s/marc.xml' % (kdip_list[k], kdip.kdip_id), 'w') as marcxml:
                        marcxml.write(bib_rec.serialize(pretty=True))

                    if kwargs.get('kdip_enumcron'):
                        kdip.note = kwargs.get('kdip_enumcron')
                        update_999a(kdip.path, kdip.kdip_id, kwargs.get('kdip_enumcron'))

                    if kwargs.get('kdip_pid'):
                        kdip.pid = kwargs.get('kdip_pid')

                    try:
                        os.remove('%s/%s/meta.yml' % (kdip_list[k], kdip.kdip_id))
                    except OSError:
                        pass

                    create_yaml(str(bib_rec.tag_583_5), kdip_list[k], kdip.kdip_id)

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
        contact = getattr(settings, 'EMORY_CONTACT', None)
        #send_mail('Invalid KDips', 'The following KDips were loaded but are invalid:\n\n%s' % bad_kdip_list, contact, [contact], fail_silently=False)




    def __unicode__(self):
        return self.kdip_id

    class Meta:
        ordering = ['create_date']


    def save(self, *args, **kwargs):

        if self.status == 'reprocess':
            KDip.objects.filter(id = self.id).delete()
            KDip.load(kdip_id=self.id, \
                        kdip_path=self.path, \
                        kdip_enumcron=self.note, \
                        kdip_pid=self.pid)
            #self.validate()
            return HttpResponseRedirect('/admin/publish/kdip/?q=%s' % self.kdip_id)

        else:
            if self.pk is not None:
                # If the note has been updated we need to write that to the Marc file.
                orig = KDip.objects.get(pk=self.pk)
                if orig.note != self.note:
                    update_999a(self.path, self.kdip_id, self.note)

            super(KDip, self).save(*args, **kwargs)


class Job(models.Model):
    "This class collects :class:`KDip` objects into logical groups for later processing"

    JOB_STATUSES = (
        ('new', "New"),
        ('ready for zephir', 'Ready for Zephir'),
        ('waiting on zephir', 'Waiting on Zephir'),
        ('ready for hathi', 'Ready for Hathi'),
        ('uploading', 'Uploading to HathiTrust'),
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

    def __unicode__(self):
        return self.name


    class Meta:
        ordering = ['id']

    def save(self, *args, **kwargs):

        if self.status == 'ready for hathi':
            uploaded_files = []
            kdips = KDip.objects.filter(job=self.id)

            for kdip in kdips:
                uploaded_files.append(kdip.id)

            # Semd volumes to the upload task.
            self.status = 'uploading'
            #celery.current_app.send_task('digitizedbooks.publish.tasks.upload_for_ht', (uploaded_files, self.id))
            from publish.tasks import upload_for_ht
            upload_for_ht.delay(uploaded_files, self.id)

        elif self.status == 'ready for zephir':
            kdips = KDip.objects.filter(job=self.id)
            # Tmp file for combined MARC XML. The eulxml output includes the namespace in the
            # <record>. We will be getting rid of that then deleting this file.
            zephir_tmp_file = '%s/Zephir/%s.tmp' % (kdip_dir, self.name)
            # File for the combined MARC XML.
            zephir_file = '%s/Zephir/%s.xml' % (kdip_dir, self.name)

            # Remove zephir file if it is already there so we can start from scratch.
            try:
                os.remove(zephir_file)
            except OSError:
                pass

            # Opening line for MARC XML
            open(zephir_tmp_file, 'a').write('<collection xmlns="http://www.loc.gov/MARC21/slim">\n')

            # Loop through the KDips to the the MARC XML
            for kdip in kdips:
                marc_file = '%s/%s/marc.xml' %(kdip.path, kdip.kdip_id)

                # Load the MARC XML
                marc = load_xmlobject_from_file(marc_file, Marc)

                # Serialize the XML into the tmp file
                open(zephir_tmp_file, 'a').write('\t' + marc.record.serialize(pretty=True))

            # Write the final line
            open(zephir_tmp_file, 'a').write('</collection>')

            # Now copy the contents of the tmp file to the real file and strip out the
            # namespace from the record tag.
            with open(zephir_tmp_file, 'r') as input_file, open(zephir_file, 'a') as output_file:
                for line in input_file:
                    if len(line) > 1:
                        new_line = re.sub('<record.*>', '<record>', line)
                        output_file.write(new_line)

            # Delete tmp file
            os.remove(zephir_tmp_file)

            send_from = getattr(settings, 'EMORY_CONTACT', None)
            zephir_contact = getattr(settings, 'ZEPHIR_CONTACT', None)
            host = getattr(settings, 'ZEPHIR_FTP_HOST', None)
            user = getattr(settings, 'ZEPHIR_LOGIN', None)
            passw = getattr(settings, 'ZEPHIR_PW', None)

            # FTP the file
            upload_cmd = 'curl -k -u %s:%s -T %s --ftp-ssl-control --ftp-pasv %s' % (user, passw, zephir_file, host)
            upload_to_z = subprocess.check_output(upload_cmd, shell=True)

            # Create the body of the email
            body = 'file name=%s.xml\n' % self.name
            body += 'file size=%s\n' % os.path.getsize(zephir_file)
            body += 'record count=%s\n' % self.volume_count
            body += 'notification email=%s' % send_from

            # Send email to Zephir. Zephir contact is defined in the loacal settings.
            send_mail('File sent to Zephir', body, send_from, [zephir_contact], fail_silently=False)

            # Set status
            self.status = 'waiting on zephir'

        super(Job, self).save(*args, **kwargs)

class ValidationError(models.Model):
    kdip = models.ForeignKey(KDip)
    error = models.CharField(max_length=255)
    error_type = models.CharField(max_length=25)

class BoxToken(models.Model):
    refresh_token = models.CharField(max_length=200, blank=True)
    client_id = models.CharField(max_length=200, blank=True)
    client_secret = models.CharField(max_length=200, blank=True)
