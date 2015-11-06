# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('publish', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='kdip',
            name='accepted_by_ht',
            field=models.BooleanField(default=False, verbose_name=b'Accepted by HT'),
        ),
    ]
