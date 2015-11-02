# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('publish', '0005_auto_20150610_1111'),
    ]

    operations = [
        migrations.AddField(
            model_name='kdip',
            name='al_ht',
            field=models.BooleanField(default=False, verbose_name=b'AL-HT'),
        ),
    ]
