# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='BoxToken',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('refresh_token', models.CharField(max_length=200, blank=True)),
                ('client_id', models.CharField(max_length=200, blank=True)),
                ('client_secret', models.CharField(max_length=200, blank=True)),
            ],
        ),
        migrations.CreateModel(
            name='Job',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(unique=True, max_length=100)),
                ('status', models.CharField(default=b'new', max_length=20, choices=[(b'new', b'New'), (b'ready for zephir', b'Ready for Zephir'), (b'waiting on zephir', b'Waiting on Zephir'), (b'ready for hathi', b'Ready for Hathi'), (b'failed', b'Upload Failed'), (b'being processed', b'Being Processed'), (b'processed', b'Processed')])),
            ],
            options={
                'ordering': ['id'],
            },
        ),
        migrations.CreateModel(
            name='KDip',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('kdip_id', models.CharField(unique=True, max_length=100)),
                ('create_date', models.DateTimeField()),
                ('status', models.CharField(default=b'invalid', max_length=20, choices=[(b'new', b'New'), (b'processed', b'Processed'), (b'archived', b'Archived'), (b'invalid', b'Invalid'), (b'do not process', b'Do Not Process'), (b'reprocess', b'Reprocess')])),
                ('note', models.CharField(max_length=200, verbose_name=b'EnumCron', blank=True)),
                ('reason', models.CharField(max_length=1000, blank=True)),
                ('path', models.CharField(max_length=400, blank=True)),
                ('pid', models.CharField(max_length=5, blank=True)),
                ('notes', models.TextField(default=b'', blank=True)),
                ('job', models.ForeignKey(on_delete=django.db.models.deletion.SET_NULL, blank=True, to='publish.Job', null=True)),
            ],
            options={
                'ordering': ['create_date'],
            },
        ),
        migrations.CreateModel(
            name='ValidationError',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('error', models.CharField(max_length=255)),
                ('error_type', models.CharField(max_length=25)),
                ('kdip', models.ForeignKey(to='publish.KDip')),
            ],
        ),
    ]
