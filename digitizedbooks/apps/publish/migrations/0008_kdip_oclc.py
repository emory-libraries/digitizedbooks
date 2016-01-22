# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('publish', '0007_auto_20151109_1020'),
    ]

    operations = [
        migrations.AddField(
            model_name='kdip',
            name='oclc',
            field=models.CharField(max_length=100, blank=True),
        ),
    ]
