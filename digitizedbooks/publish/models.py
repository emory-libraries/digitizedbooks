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
import os, re, shutil
from hashlib import md5

from django.conf import settings
from django.db import models
from django.core.mail import send_mail

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
        r = requests.get('http://library.emory.edu/uhtbin/get_bibrecord', params={'item_id': self.kdip_id})
        bib_rec = load_xmlobject_from_string(r.text.encode('utf-8'), Marc)

        if not bib_rec.tag_583_5:
            return 'No 583 tag in marc record.'

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
                print('It is gov')
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
        logger.error(reason)
        return reason
    if rights is not 'ic':
        logger.info('%s rights set to %s' % (self.kdip_id, rights))
        return 'public'
    else:
        return reason

def validate_tiffs(tiff_file, kdip, kdip_dir):
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
    missing = []
    found = {}
    skipalbe = ['ImageProducer', 'DocumentName', 'Make', 'Model', 'ColorSpace']
    yaml_data = {}

    image = Image.open(tiff_file)
    tags = image.tag

    for tif_tag in tif_tags:
        valid = tags.has_key(tif_tags[tif_tag])
        if valid is False:
            found[tif_tag] = False

        if valid is True:
            found[tif_tag] = tags.get(tif_tags[tif_tag])


    #print(found['DateTime'])
    dt = datetime.strptime(found['DateTime'], '%Y:%m:%d %H:%M:%S')
    yaml_data['capture_date'] = dt.isoformat('T')
    with open('%s/%s/meta.yml' % (kdip_dir, kdip), 'a') as outfile:
        outfile.write( yaml.dump(yaml_data, default_flow_style=False) )

    ## START REAL VALIDATION
    if found['ImageWidth'] <= 0:
        status = 'Invalid value for ImageWidth in %s' % (tiff_file)
        return status

    if found['ImageLength']  <= 0:
        status = 'Invalid value for ImageLength in %s' % (tiff_file)
        return status

    if not found['Make']:
        status = 'Invalid value for Make in %s' % (tiff_file)
        return status

    if not found['Model']:
        status = 'Invalid value for Make in %s' % (tiff_file)
        return status

    if found['Orientation'] != (1,):
        status = 'Invalid value for Orientation in %s' % (tiff_file)
        return status

    #if found['ColorSpace'] != 1:
    #    status = 'Invalid value for ColorSpace in %s' % (file)
    #    return status

    if found['ResolutionUnit'] != (2,):
        status = 'Invalid value for ResolutionUnit in %s' % (tiff_file)
        return status

    if not found['DateTime']:
        status = 'Invalid value for DateTime in %s' % (tiff_file)
        return status

    imgtype = re.sub("[^0-9]", "", str(found['BitsPerSample']))
    if imgtype == '1':

        if found['Compression'] != (4,):
            status = 'Invalid value for Compression in %s' % (tiff_file)
            return status

        if found['PhotometricInterpretation'] != (0,):
            status = 'Invalid value for PhotometricInterpretation in %s' % (tiff_file)
            return status

        if found['SamplesPerPixel'] != (1,):
            status = 'Invalid value for SamplesPerPixel in %s' % (tiff_file)
            return status

        if found['XResolution'] < 600:
            status = 'Invalid value for XResolution in %s' % (tiff_file)
            return status

        if found['YResolution'] < 600:
            status = 'Invalid value for YResolution in %s' % (tiff_file)
            return status

    elif imgtype is '888' or '3':

        if found['Compression'] != (1,):
            if found['Compression'] != (5,):
                status = 'Invalid value for Compression in %s' % (tiff_file)
                return status

        if found['PhotometricInterpretation'] != (2,):
            status = 'Invalid value for PhotometricInterpretation in %s' % (tiff_file)
            return status

        if found['SamplesPerPixel'] != (3,):
            status = 'Invalid value for SamplesPerPixel in %s' % (tiff_file)
            return status

        if found['XResolution'] < 300:
            status = 'Invalid value for XResolution in %s' % (tiff_file)
            return status

        if found['YResolution'] < 300:
            status = 'Invalid value for YResolution in %s' % (tiff_file)
            return status

    else:
        status = 'cannot determine type for %s' % (tiff_file)


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


    def validate(self):
        '''
        Validates the mets file and files referenced in the mets.
        '''

        logger.info('Starting validation of %s' % (self.kdip_id))
        # all paths (except for TOC) are relitive to METS dir
        mets_dir = "%s/%s/METS/" % (self.path, self.kdip_id)

        mets_file = "%s%s.mets.xml" % (mets_dir, self.kdip_id)
        logger.info('Mets file is %s' % mets_file)

        toc_file = "%s/%s/TOC/%s.toc" % (self.path, self.kdip_id, self.kdip_id)

        tif_dir = "%s/%s/TIFF/" % (self.path, self.kdip_id)

        rights = get_rights(self)

        if rights is not 'public':
            self.reason = rights
            if 'Could not' in rights:
                self.status = 'invalid'
            else:
                self.status = 'do not process'
            self.save()
            logger.error(rights)
            return False

        #Mets file exists
        if not os.path.exists(mets_file):
            reason = "Error: %s does not exist" % mets_file
            self.reason = reason
            self.status = 'invalid'
            self.save()
            logger.error(reason)
            return False

        mets = load_xmlobject_from_file(mets_file, Mets)

        #mets file validates against schema
        if not mets.is_valid():
            reason = "Error: %s is not valid" % mets_file
            self.reason = reason
            self.status = 'invalid'
            self.save()
            logger.error(reason)
            return False

        tif_status = None
        tiffs = glob.glob('%s/*.tif' % tif_dir)

        tif_status = validate_tiffs(tiffs[0], self.kdip_id, self.path)

        if tif_status is not None:
            self.reason = tif_status
            self.status = 'invalid'
            self.save()
            logger.error(tif_status)
            return False

        # validate each file of type ALTO and OCR
        for f in mets.techmd:
            file_path = "%s%s" % (mets_dir, f.href)

            # file exists
            if not os.path.exists(file_path):
                reason = "Error: %s does not exist" % file_path
                self.reason = reason
                self.status = 'invalid'
                self.save()
                logger.error(reason)
                return False

            # checksum good
            with open(file_path, 'rb') as file:
                if not f.checksum == md5(file.read()).hexdigest():
                    #reason = "Error: checksum does not match for %s" % file_path
                    reason = '%s Mets is is %s,  file is %s' % (self.kdip_id, f.checksum, md5(file.read()).hexdigest())
                    self.reason = reason
                    self.status = 'invalid'
                    self.save()
                    logger.error(reason)
                    return False

        # if it gets here were are good
        self.status = 'new'
        self.save()
        return True


    @classmethod
    def load(self, *args, **kwargs):
        "Class method to scan data directory specified in the ``localsettings`` **KDIP_DIR** and create new KDIP objects in the database."

        kdip_list = {}

        if len(args) == 2:
            kdip_list[args[0]] = args[1]

        else:
            for path, subdirs, files in os.walk(kdip_dir):
                for dir in subdirs:
                    kdip = re.search(r"^[0-9]+$", dir)
                    full_path = os.path.join(path, dir)
                    if kdip and 'out_of_scope' not in full_path:
                        kdip_list[dir] = path

        # create the KDIP is it does not exits
        for k in kdip_list:
            try:
                # lookkup bib record for note field
                r = requests.get('http://library.emory.edu/uhtbin/get_bibrecord', params={'item_id': k})
                bib_rec = load_xmlobject_from_string(r.text.encode('utf-8'), Marc)
                
                # Remove extra 999 fileds. We only want the one where the 'i' code matches the barcode.
                for datafield in bib_rec.tag_999:
                    i999 = datafield.node.xpath('marc:subfield[@code="i"]', namespaces=Marc.ROOT_NAMESPACES)[0].text
                    if i999 != k:
                        bib_rec.tag_999.remove(datafield)

                defaults={
                   'create_date': datetime.fromtimestamp(os.path.getctime('%s/%s' % (kdip_list[k], k))),
                    'note': bib_rec.note(k),
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
                else:
                    kdip.validate()

            except Exception as e:
                logger.error("Error creating KDip %s : %s" % (k, e.message))
                pass



    def __unicode__(self):
        return self.kdip_id

    class Meta:
        ordering = ['create_date']

    def save(self, *args, **kwargs):

        if self.status == 'reprocess':
            KDip.objects.filter(id = self.id).delete()
            KDip.load(self.kdip_id, self.path)

        else:
            super(KDip, self).save(*args, **kwargs)


class Job(models.Model):
    "This class collects :class:`KDip` objects into logical groups for later processing"

    JOB_STATUSES = (
        ('new', "New"),
        ('ready to process', 'Ready To Process'),
        ('failed', 'Upload Failed'),
        ('being processed', 'Being Processed'),
        ('processed', 'Processed')
    )

    name = models.CharField(max_length=100, unique=True)
    'Human readable name of job'
    status = models.CharField(max_length=20, choices=JOB_STATUSES, default='new')

    def __unicode__(self):
        return self.name

    class Meta:
        ordering = ['id']

    def save(self, *args, **kwargs):

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

        if self.status == 'ready to process':
            uploaded_files = []
            kdips = KDip.objects.filter(job=self.id)
            for kdip in kdips:

                client = DjangoPidmanRestClient()
                pidman_domain = getattr(settings, 'PIDMAN_DOMAIN', None)
                pidman_policy = getattr(settings, 'PIDMAN_POLICY', None)
                ark = client.create_ark(domain='%s' % pidman_domain, target_uri='http://myuri.org', policy='%s' % pidman_policy, name='%s' % kdip.kdip_id)
                naan = parse_ark(ark)['naan']
                noid = parse_ark(ark)['noid']

                logger.info("Ark %s was created for %s" % (ark, kdip.kdip_id))

                process_dir = '%s/ark+=%s=%s' % (kdip.path, naan, noid)

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
                        self.status = 'being processed'
                        uploaded_files.append('ark+=%s=%s' % (naan, noid))

                except Exception as e:
                    logger.error('Uploading %s.zip failed with message %s' % (process_dir, upload_response['message']))
                    self.status = 'failed'
                    pass

            if self.status == 'being processed':
                kdip_list = '\n'.join(map(str, uploaded_files))
                send_to = getattr(settings, 'HATHITRUST_CONTACT', None)
                send_from = getattr(settings, 'EMORY_CONTACT', None)
                send_mail('New Volumes from Emory have been uploaded', 'The following volumes have been uploaded and are ready:\n\n%s' % kdip_list, send_from, [send_to], fail_silently=False)

        super(Job, self).save(*args, **kwargs)

class BoxToken(models.Model):
    refresh_token = models.CharField(max_length=200, blank=True)
    client_id = models.CharField(max_length=200, blank=True)
    client_secret = models.CharField(max_length=200, blank=True)