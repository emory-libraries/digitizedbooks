# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('publish', '0008_kdip_oclc'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='job',
            options={'ordering': ['-pk']},
        ),
        migrations.AlterModelOptions(
            name='kdip',
            options={'ordering': ['-pk']},
        ),
        migrations.AddField(
            model_name='kdip',
            name='mms_id',
            field=models.CharField(max_length=100, blank=True),
        ),
    ]
