# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'Package'
        db.create_table(u'publish_package', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('package_id', self.gf('django.db.models.fields.CharField')(max_length=100)),
            ('create_date', self.gf('django.db.models.fields.DateTimeField')()),
            ('status', self.gf('django.db.models.fields.CharField')(default='new', max_length=20)),
            ('order', self.gf('django.db.models.fields.IntegerField')()),
        ))
        db.send_create_signal(u'publish', ['Package'])


    def backwards(self, orm):
        # Deleting model 'Package'
        db.delete_table(u'publish_package')


    models = {
        u'publish.package': {
            'Meta': {'object_name': 'Package'},
            'create_date': ('django.db.models.fields.DateTimeField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'order': ('django.db.models.fields.IntegerField', [], {}),
            'package_id': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'status': ('django.db.models.fields.CharField', [], {'default': "'new'", 'max_length': '20'})
        }
    }

    complete_apps = ['publish']