# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('publish', '0009_auto_20160120_1735'),
    ]

    operations = [
        migrations.AddField(
            model_name='boxtoken',
            name='access_token',
            field=models.CharField(max_length=200, blank=True),
        ),
        migrations.AlterField(
            model_name='job',
            name='status',
            field=models.CharField(default=b'new', max_length=20, choices=[(b'new', b'New'), (b'ready for zephir', b'Ready for Zephir'), (b'waiting on zephir', b'Waiting on Zephir'), (b'zephir upload error', b'Zephir Upload Error'), (b'zephir error', b'Zephir Error'), (b'ready for hathi', b'Ready for Hathi'), (b'uploading', b'Uploading to HathiTrust'), (b'retry', b'Retry Upload'), (b'failed', b'Upload Failed'), (b'being processed', b'Being Processed'), (b'processed', b'Processed'), (b'processed by ht', b'Processed by HT')]),
        ),
        migrations.AlterField(
            model_name='kdip',
            name='status',
            field=models.CharField(default=b'invalid', max_length=20, choices=[(b'new', b'Valid'), (b'processed', b'Processed'), (b'archived', b'Archived'), (b'invalid', b'Invalid'), (b'do not process', b'Do Not Process'), (b'alma_fail', b'Alma Update Failed'), (b'reprocess', b'Reprocess'), (b'upload_fail', b'Upload Failed'), (b'uploaded', b'Uploaded')]),
        ),
    ]
