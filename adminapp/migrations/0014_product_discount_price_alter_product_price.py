# Generated by Django 5.2.3 on 2025-07-17 12:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('adminapp', '0013_product_is_new_product_is_trending'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='discount_price',
            field=models.DecimalField(blank=True, decimal_places=2, help_text='Discounted price (leave blank if no discount)', max_digits=10, null=True),
        ),
        migrations.AlterField(
            model_name='product',
            name='price',
            field=models.DecimalField(decimal_places=2, help_text='Original price', max_digits=10),
        ),
    ]
