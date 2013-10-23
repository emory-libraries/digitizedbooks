# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'Job'
        db.create_table(u'publish_job', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(unique=True, max_length=100)),
            ('status', self.gf('django.db.models.fields.CharField')(default='new', max_length=20)),
        ))
        db.send_create_signal(u'publish', ['Job'])

        # Adding model 'KDip'
        db.create_table(u'publish_kdip', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('kdip_id', self.gf('django.db.models.fields.CharField')(unique=True, max_length=100)),
            ('create_date', self.gf('django.db.models.fields.DateTimeField')()),
            ('status', self.gf('django.db.models.fields.CharField')(default='new', max_length=20)),
            ('note', self.gf('django.db.models.fields.CharField')(max_length=200, blank=True)),
            ('job', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['publish.Job'], null=True, on_delete=models.SET_NULL, blank=True)),
        ))
        db.send_create_signal(u'publish', ['KDip'])


    def backwards(self, orm):
        # Deleting model 'Job'
        db.delete_table(u'publish_job')

        # Deleting model 'KDip'
        db.delete_table(u'publish_kdip')


    models = {
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
            'status': ('django.db.models.fields.CharField', [], {'default': "'new'", 'max_length': '20'})
        }
    }

    complete_apps = ['publish']