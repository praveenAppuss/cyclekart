from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [
        ('userapp', '0017_alter_wishlist_unique_together_and_more'),  # Updated dependency
    ]

    operations = [
        migrations.RunSQL(
            sql='ALTER TABLE userapp_wishlist ALTER COLUMN color_variant_id SET NOT NULL;',
            reverse_sql='ALTER TABLE userapp_wishlist ALTER COLUMN color_variant_id DROP NOT NULL;'
        ),
        migrations.AlterField(
            model_name='wishlist',
            name='color_variant',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='wishlist_items',
                to='adminapp.productcolorvariant',
            ),
        ),
    ]