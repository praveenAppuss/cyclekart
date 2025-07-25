# Generated by Django 5.2.3 on 2025-07-19 09:21

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('userapp', '0006_wishlist'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='payment_method',
            field=models.CharField(choices=[('cod', 'Cash on Delivery'), ('card', 'Debit Card / Credit Card'), ('net_banking', 'Net Banking'), ('wallet', 'Wallet')], default='cod', max_length=20),
        ),
    ]
