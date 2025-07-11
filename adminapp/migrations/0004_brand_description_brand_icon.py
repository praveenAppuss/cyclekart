# Generated by Django 5.2.3 on 2025-07-01 09:39

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('adminapp', '0003_brand'),
    ]

    operations = [
        migrations.AddField(
            model_name='brand',
            name='description',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='brand',
            name='icon',
            field=models.ImageField(blank=True, null=True, upload_to='brand_icons/'),
        ),
    ]
