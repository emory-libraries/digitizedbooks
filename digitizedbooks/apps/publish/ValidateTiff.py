from PIL import Image
import sys, re

import models


class ValidateTiff:
    def __init__(self, tiff_file, kdip):
        self.tiff_file = tiff_file
        self.kdip = kdip

    def validate_tiffs(self):
        '''
        Method to validate the Tiff files.
        Site for looking up Tiff tags: http://www.awaresystems.be/imaging/tiff/tifftags/search.html
        '''

        def log_error():
            tiff_error = models.ValidationError(
                kdip=self.kdip,
                error="%s %s" % (self.error, self.tiff_file),
                error_type="Invalid Tiff")
            tiff_error.save()

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
        try:
            image = Image.open(self.tiff_file)

            tags = image.tag
            for tif_tag in tif_tags:
                valid = tags.has_key(tif_tags[tif_tag])
                if valid is False:
                    found[tif_tag] = False

                if valid is True:
                    found[tif_tag] = tags.get(tif_tags[tif_tag])

            ## START REAL VALIDATION
            if found['ImageWidth'] <= 0:
                self.error = 'Invalid value for ImageWidth in '
                log_error()

            if found['ImageLength']  <= 0:
                self.error = 'Invalid value for ImageLength in '
                log_error()

            if not found['Make']:
                self.error = 'Invalid value for Make in '
                log_error()

            if not found['Model']:
                self.error = 'Invalid value for Make in '
                log_error()

            if found['Orientation'] != (1,):
                self.error = 'Invalid value for Orientation in '
                log_error(self.kdip)

            if found['ResolutionUnit'] != (2,):
                self.error = 'Invalid value for ResolutionUnit in '
                log_error()

            if not found['DateTime']:
                self.error = 'Invalid value for DateTime in '
                log_error()

            image_code = re.sub("[^0-9]", "", str(found['BitsPerSample']))
            image_type = bittsPerSample[image_code]

            if image_type is 'Bitonal' or image_type is 'Grayscale':

                if found['Compression'] == compressions['Uncompressed'] or found['Compression'] == compressions['T6/Group 4 Fax']:
                    pass
                else :
                    self.error = 'Invalid value for PhotometricInterpretation in '
                    log_error()

                if str(found['SamplesPerPixel']) != samplesPerPixel['Grayscale']:
                    self.error = 'Invalid value for SamplesPerPixel in '
                    log_error()

                if found['XResolution'] < 600:
                    self.error = 'Invalid value for XResolution in '
                    log_error()

                if found['YResolution'] < 600:
                    self.error = 'Invalid value for YResolution in '
                    log_error()

            # COLOR
            elif image_type is 'Color-3' or image_type is 'Color-888':

                if found['Compression'] == compressions['Uncompressed'] or found['Compression'] == compressions['LZW']:
                    pass
                else:
                    self.error = 'Invalid value for Compression in %s' % (self.tiff_file)
                    log_error()

                if found['PhotometricInterpretation'] != photometricInterpretation['RGB']:
                    self.error = 'Invalid value for PhotometricInterpretation in %s' % (self.tiff_file)
                    log_error()

                if str(found['SamplesPerPixel']) != samplesPerPixel['RGB']:
                    self.error = 'Invalid value for SamplesPerPixel in '
                    log_error()

                if found['XResolution'] < 300:
                    self.error = 'Invalid value for XResolution in '
                    log_error()

                if found['YResolution'] < 300:
                    self.error = 'Invalid value for YResolution in '
                    log_error()

            else:
                self.error = 'Cannot determine type for '
                log_error()

            image.close()

        except:
            self.error = 'Error \'%s\' while validating ' % sys.exc_info()[1]
            log_error()
            image.close()
