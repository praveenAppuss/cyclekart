from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [
        ('userapp', '0014_alter_cartitem_unique_together_and_more'),
        ('adminapp', '0015_remove_productimage_product_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='wishlist',
            name='color_variant',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='wishlist_items',
                to='adminapp.productcolorvariant',
            ),
        ),
    ]