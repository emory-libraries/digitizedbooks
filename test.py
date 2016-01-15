from eulxml.xmlmap import XmlObject
from eulxml.xmlmap import load_xmlobject_from_string, load_xmlobject_from_file
from eulxml.xmlmap.fields import StringField, NodeListField, IntegerField, NodeField

text = '<bib><mms_id>991122800000121</mms_id><holdings link="/almaws/v1/bibs/991122800000121/holdings"/><created_by>exl_impl</created_by><created_date>2013-11-05Z</created_date> <last_modified_by>exl_impl</last_modified_by><last_modified_date>2014-01-20Z</last_modified_date><record><datafield ind1="1" ind2=" " tag="100"><subfield code="a">Smith, John</subfield></datafield></record></bib>'

class AlmaBibDataField(XmlObject):
    ROOT_NAME = 'datafield'
    ind1 = StringField("@ind1")
    ind2 = StringField("@ind2")
    tag = StringField("@tag")
    code_3 = StringField('subfield[@code="3"]')
    code_u = StringField('subfield[@code="u"]')

    def __init__(self, *args, **kwargs):
        super(AlmaBibDataField, self).__init__(*args, **kwargs)
        self.tag = '856'
        self.ind1 = "4"
        self.ind2 = "1"

class AlmaBibRecord(XmlObject):
    field856 = NodeListField('record/datafield', AlmaBibDataField)

item_obj = load_xmlobject_from_string(str(text), AlmaBibRecord)
item_obj.field856.append(AlmaBibDataField(code_u="yeah baby", code_3="foo bar"))
print item_obj.serialize()
