# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding field 'BoxToken.client_id'
        db.add_column(u'publish_boxtoken', 'client_id',
                      self.gf('django.db.models.fields.CharField')(default='', max_length=200, blank=True),
                      keep_default=False)

        # Adding field 'BoxToken.client_secret'
        db.add_column(u'publish_boxtoken', 'client_secret',
                      self.gf('django.db.models.fields.CharField')(default='', max_length=200, blank=True),
                      keep_default=False)


    def backwards(self, orm):
        # Deleting field 'BoxToken.client_id'
        db.delete_column(u'publish_boxtoken', 'client_id')

        # Deleting field 'BoxToken.client_secret'
        db.delete_column(u'publish_boxtoken', 'client_secret')


    models = {
        u'publish.boxtoken': {
            'Meta': {'object_name': 'BoxToken'},
            'client_id': ('django.db.models.fields.CharField', [], {'max_length': '200', 'blank': 'True'}),
            'client_secret': ('django.db.models.fields.CharField', [], {'max_length': '200', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'refresh_token': ('django.db.models.fields.CharField', [], {'max_length': '200', 'blank': 'True'})
        },
        u'publish.job': {
            'Meta': {'ordering': "['id']", 'object_name': 'Job'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '100'}),
            'status': ('django.db.models.fields.CharField', [], {'default': "'new'", 'max_length': '20'})
        },
        u'publish.kdip': {
            'Meta': {'ordering': "['create_date']", 'object_name': 'KDip'},
            'create_date': ('django.db.models.fields.DateTimeField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'job': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['publish.Job']", 'null': 'True', 'on_delete': 'models.SET_NULL', 'blank': 'True'}),
            'kdip_id': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '100'}),
            'note': ('django.db.models.fields.CharField', [], {'max_length': '200', 'blank': 'True'}),
            'reason': ('django.db.models.fields.CharField', [], {'max_length': '1000', 'blank': 'True'}),
            'status': ('django.db.models.fields.CharField', [], {'default': "'new'", 'max_length': '20'})
        }
    }

    complete_apps = ['publish']