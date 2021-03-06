"""
A handful of utility methods for various actions.
"""

import re
import yaml
import requests
from eulxml.xmlmap import load_xmlobject_from_string, load_xmlobject_from_file
from os import listdir, remove
from datetime import datetime
from PIL import Image
from django.conf import settings

import models

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
        if date2 is not None and date2 > date1:
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
    marc = load_xmlobject_from_file(marc_file, models.Marc)
    marc.tag_999a = enumcron
    with open(marc_file, 'w') as marcxml:
        marcxml.write(marc.serialize(pretty=True))

def remove_all_999_fields(record):
    """
    Method used by the check_ht manage command to remove all 999
    fileds from the MARC XML before going to Alema
    """
    try:
        record.field999 = ''
    except:
        pass
    return record

def update_583(record):
    """
    Method used by check_ht manage command to upddate the
    583 filed to `ditigized`.
    """
    try:
        record.tag583a = 'digitized'
    except:
        pass
    return record

def get_oclc_fields(record):
    """
from digitizedbooks.apps.publish import Utils
from digitizedbooks.apps.publish import models
k = models.KDip.objects.get(kdip_id = '010000666241')
record = Utils.load_bib_record(k)
alma = Utils.load_alma_bib_record(k)
"""
    oclc_tags = []
    for oclc_tag in record.field_035:
        # The
        try:
            # Mainly doing it this way for readablity and/or because I don't know any better way to do this in eulxml
            # And I don't want make this a Marc object for just this one field.
            oclc_tags.append(oclc_tag.node.xpath('marc:subfield[@code="a"]', namespaces=models.Marc.ROOT_NAMESPACES)[0].text)
        except IndexError:
            oclc_tags.append(oclc_tag.serialize())

    return oclc_tags

def load_bib_record(kdip):
    """
    Method to load MARC XML from Am
    http://discovere.emory.edu:8991/cgi-bin/get_alma_record?item_id=010002483050
    Method accepts a KDip object of a barcode as a string.
    """
    if isinstance(kdip, basestring):
        barcode = kdip
    else:
        barcode = kdip.kdip_id

    get_bib_rec = requests.get( \
        'https://kleene.library.emory.edu/cgi-bin/get_alma_record?item_id=', \
        params={'item_id': barcode})

    return load_xmlobject_from_string( \
        get_bib_rec.text.encode('utf-8'), models.Marc)

def load_alma_bib_record(kdip):
    """
    Bib record from Alma.
    """
    if isinstance(kdip, basestring):
        kdip = models.KDip.objects.get(kdip_id=kdip)

    item = requests.get('%sitems' % settings.ALMA_API_ROOT,
        params={
            'item_barcode': kdip.kdip_id,
            'apikey': settings.ALMA_APIKEY
        }
    )

    bib_rec = item.text.encode('utf-8').strip()
    item_obj = load_xmlobject_from_string(bib_rec, models.AlmaBibItem)

    kdip.mms_id = item_obj.mms_id
    kdip.save()

    bib = requests.get('%sbibs/%s' % (settings.ALMA_API_ROOT, kdip.mms_id),
        params={'apikey': settings.ALMA_APIKEY}
    )

    bib_xml = bib.text.encode('utf-8').strip()

    return load_xmlobject_from_string(bib_xml, models.AlmaBibRecord)

def transform_035(record):
    '''
    Remove this tag:
        <datafield ind1=" " ind2=" " tag="035">
            <subfield code="a">(Aleph)002240955EMU01</subfield>
            </datafield>
    And add this:
        <datafield ind1=" " ind2=" " tag="035">
            <subfield code="z">(GEU)Aleph002240955</subfield>
        </datafield>
    '''
    try:
        fields = record.field_035
        aleph = next(field_val for field_val in fields if "(Aleph" in field_val.serialize())
        fields.remove(aleph)

        # Get the numeric part out to the Aleph field
        field_text = aleph.node.xpath('marc:subfield[@code="a"]', namespaces=models.Marc.ROOT_NAMESPACES)[0].text
        geu = '(GEU)Aleph%s' % field_text[7:16]

        datafields = record.datafields
        insert_position = datafields.index(record.field_035[-1]) + 1
        datafields.insert(insert_position, models.Marc035Field(code_z = geu))

    except StopIteration:
        # Pure Alma records will not have an reference to Aleph records, so we
        # just move along.
        pass

    return record

def cleanup_035s(record):
    """
    If any 035 $a has a value following the string '(OCoLC)' that matches the
    number in the 001 field, it is not an OCLC number at all (it is the ALMA
    system number, and is a mistake made during ALMA migration).  If you find
    a match, drop the field.
    """
    for field in record.field_035:
        if record.alma_number in field.serialize():
            record.field_035.remove(field)

    # HT only wants one 035 with the OCoLC. So we just keep the first one.
    oclc_prefixs = ["OCoLC", "ocm", "ocn"]
    oclcs = []
    for field in record.field_035:
        if any(oclc_prefix in field.serialize() for oclc_prefix in oclc_prefixs):
            oclcs.append(field)
    for extra_oclc in oclcs[1:]:
        record.field_035.remove(extra_oclc)

    return record

def remove_most_999_fields(record, barcode):
    """
    Remove extra 999 fileds. We only want the one where the 'i' code matches the barcode.
    """
    for field_999 in record.tag_999:
        if barcode not in field_999.serialize():
            record.tag_999.remove(field_999)

    return record

def create_ht_marc(kdip):

    if isinstance(kdip, basestring):
        barcode = kdip
    else:
        barcode = kdip.kdip_id

    record = load_bib_record(barcode)
    cleanup_035s(record)
    remove_most_999_fields(record, barcode)
    transform_035(record)

    marc_file = '%s/%s/marc.xml' % (settings.KDIP_DIR, barcode)

    # Write the marc.xml to disk.
    with open(marc_file, 'w') as marcxml:
        # When we insert the 035 field in position an empaty datafield is instered
        # at the bottom, so we get rid of that.
        marcxml.write(re.sub('\<datafield\/\>\\n', '', record.serialize(pretty=True)))

    return load_xmlobject_from_file(marc_file, models.Marc)

def create_yaml(kdip):
    """
    Method to create a YAML file with some basic default
    metadata for HathiTrust
    """

    try:
        #TODO have this use the `kdip.meta_yml` a
        remove('%s/%s/meta.yml' % (kdip.path, kdip.kdip_id))
    except OSError:
        pass

    bib_rec = load_bib_record(kdip.kdip_id)
    capture_agent = str(bib_rec.tag_583_5)

    # First we need to figure out the 'capture date'
    tif_dir = '%s/%s/TIFF' % (kdip.path, kdip.kdip_id)
    tif = '%s/%s' % (tif_dir, listdir(tif_dir)[-1])
    image = Image.open(tif)
    # In Pillow 3.0 the DateTime/306 tag is returned as a tuple, not a string.
    # So if/when we move to 3.x we will need this conversion.
    if image.tag.has_key(306):
        dt = datetime.strptime(image.tag[306], '%Y:%m:%d %H:%M:%S')
    else:
        dt = ''

    yaml_data = {}
    yaml_data['capture_agent'] = capture_agent
    yaml_data['scanner_user'] = 'Emory University: LITS Digitization Services'
    yaml_data['scanning_order'] = 'left-to-right'
    yaml_data['reading_order'] = 'left-to-right'
    yaml_data['capture_date']= dt.isoformat('T')
    # TODO make this use `kdip.meta_yml` class atribute.
    with open('%s/%s/meta.yml' % (kdip.path, kdip.kdip_id), 'a') as outfile:
        yaml.dump(yaml_data, outfile, default_flow_style=False)
