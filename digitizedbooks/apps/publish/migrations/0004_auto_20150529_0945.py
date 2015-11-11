# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('publish', '0003_kdip_accepted_by_ia'),
    ]

    operations = [
        migrations.AlterField(
            model_name='job',
            name='status',
            field=models.CharField(default=b'new', max_length=20, choices=[(b'new', b'New'), (b'ready for zephir', b'Ready for Zephir'), (b'waiting on zephir', b'Waiting on Zephir'), (b'ready for hathi', b'Ready for Hathi'), (b'uploading', b'Uploading to HathiTrust'), (b'failed', b'Upload Failed'), (b'being processed', b'Being Processed'), (b'processed', b'Processed')]),
        ),
        migrations.AlterField(
            model_name='kdip',
            name='accepted_by_ht',
            field=models.BooleanField(default=False, verbose_name=b'HT'),
        ),
        migrations.AlterField(
            model_name='kdip',
            name='accepted_by_ia',
            field=models.BooleanField(default=False, verbose_name=b'IA'),
        ),
    ]
