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

def load_bib_record(barcode):
    """
    Method to load MARC XML from Am
    http://chivs01aleph02.hosted.exlibrisgroup.com:8991/uhtbin/get_bibrecord?item_id=010002483050
    """
    get_bib_rec = requests.get( \
        'http://chivs01aleph02.hosted.exlibrisgroup.com:8991/uhtbin/get_bibrecord', \
        params={'item_id': barcode})

    return load_xmlobject_from_string( \
        get_bib_rec.text.encode('utf-8'), models.Marc)

def load_local_bib_record(barcode):
    """
    Method to load local version of MARC XML from Aleph
    Used by the check_ht command.
    """
    get_bib_rec = requests.get( \
        'http://library.emory.edu/uhtbin/get_aleph_bibrecord', \
        params={'item_id': barcode})

    return load_xmlobject_from_string( \
        get_bib_rec.text.encode('utf-8'), models.Marc)

def create_yaml(kdip):
    """
    Method to create a YAML file with some basic default
    metadata for HathiTrust
    """

    try:
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
    yaml_data['scanning_order'] = 'left-to-right!!!!'
    yaml_data['reading_order'] = 'left-to-right'
    yaml_data['capture_date']= dt.isoformat('T')
    with open('%s/%s/meta.yml' % (kdip.path, kdip.kdip_id), 'a') as outfile:
        outfile.write(yaml.dump(yaml_data, default_flow_style=False))
