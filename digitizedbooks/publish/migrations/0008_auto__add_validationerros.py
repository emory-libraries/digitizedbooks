# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'ValidationErros'
        db.create_table(u'publish_validationerros', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('kdip', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['publish.KDip'])),
            ('error', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('error_type', self.gf('django.db.models.fields.CharField')(max_length=25)),
        ))
        db.send_create_signal(u'publish', ['ValidationErros'])


    def backwards(self, orm):
        # Deleting model 'ValidationErros'
        db.delete_table(u'publish_validationerros')


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
            'path': ('django.db.models.fields.CharField', [], {'max_length': '400', 'blank': 'True'}),
            'pid': ('django.db.models.fields.CharField', [], {'max_length': '5', 'blank': 'True'}),
            'reason': ('django.db.models.fields.CharField', [], {'max_length': '1000', 'blank': 'True'}),
            'status': ('django.db.models.fields.CharField', [], {'default': "'invalid'", 'max_length': '20'})
        },
        u'publish.validationerros': {
            'Meta': {'object_name': 'ValidationErros'},
            'error': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'error_type': ('django.db.models.fields.CharField', [], {'max_length': '25'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'kdip': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['publish.KDip']"})
        }
    }

    complete_apps = ['publish']