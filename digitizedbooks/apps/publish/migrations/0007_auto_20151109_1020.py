# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('publish', '0006_kdip_al_ht'),
    ]

    operations = [
        migrations.AlterField(
            model_name='job',
            name='status',
            field=models.CharField(default=b'new', max_length=20, choices=[(b'new', b'New'), (b'ready for zephir', b'Ready for Zephir'), (b'waiting on zephir', b'Waiting on Zephir'), (b'zephir upload error', b'Zephir Upload Error'), (b'zephir error', b'Zephir Error'), (b'ready for hathi', b'Ready for Hathi'), (b'uploading', b'Uploading to HathiTrust'), (b'failed', b'Upload Failed'), (b'being processed', b'Being Processed'), (b'processed', b'Processed'), (b'processed by ht', b'Processed by HT')]),
        ),
    ]
