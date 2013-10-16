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

from eulxml.xmlmap import XmlObject
from eulxml.xmlmap.fields import StringField, NodeListField, IntegerField

class METSFile(XmlObject):
    ROOT_NAME = 'file'
    ROOT_NAMESPACES = {'xlink' : 'http://purl.org/dc/elements/1.1/xlink/'}

    id = StringField('@ID')
    admid = StringField('@ADMID')
    mimetype = StringField('@MIMETYPE')
    loctype = StringField('FLocat/@LOCTYPE')
    href = StringField('FLocat/@xlink:href')

class METStechMD(XmlObject):
    ROOT_NAME = 'techMD'
    ROOT_NAMESPACES = {'mix': 'http://www.loc.gov/mix/v20'}


    id = StringField('@ID')
    href = StringField('mdWrap/xmlData/mix:mix/mix:BasicDigitalObjectInformation/mix:ObjectIdentifier/mix:objectIdentifierValue')
    size = IntegerField('mdWrap/xmlData/mix:mix/mix:BasicDigitalObjectInformation/mix:fileSize')
    mimetype = StringField('mdWrap/xmlData/mix:mix/mix:BasicDigitalObjectInformation/mix:FormatDesignation/mix:formatName')
    checksum = StringField('mdWrap/xmlData/mix:mix/mix:BasicDigitalObjectInformation/mix:Fixity/mix:messageDigest')

class Mets(XmlObject):
    XSD_SCHEMA = 'http://www.loc.gov/standards/mets/version191/mets.xsd'
    ROOT_NAME = 'mets'

    tiffs = NodeListField('fileSec/fileGrp[@ID="TIFF"]/file', METSFile)
    jpegs = NodeListField('fileSec/fileGrp[@ID="JPEG"]/file', METSFile)
    jp2s = NodeListField('fileSec/fileGrp[@ID="JP2000"]/file', METSFile)
    techmd = NodeListField('amdSec/techMD', METStechMD)



