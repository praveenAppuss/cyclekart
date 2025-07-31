from django.db import migrations
import logging

logger = logging.getLogger(__name__)

def migrate_wishlist_to_color_variant(apps, schema_editor):
    Wishlist = apps.get_model('userapp', 'Wishlist')
    ProductColorVariant = apps.get_model('adminapp', 'ProductColorVariant')

    for item in Wishlist.objects.all():
        if item.product_id:
            color_variant = ProductColorVariant.objects.filter(product_id=item.product_id).first()
            if color_variant:
                logger.info(f"Migrating wishlist item {item.id} to color_variant {color_variant.id}")
                item.color_variant = color_variant
                item.save()
            else:
                logger.warning(f"No color variant for product {item.product_id}, deleting wishlist item {item.id}")
                item.delete()

def reverse_migrate_wishlist(apps, schema_editor):
    Wishlist = apps.get_model('userapp', 'Wishlist')
    for item in Wishlist.objects.all():
        if item.color_variant:
            item.product_id = item.color_variant.product_id
            item.save()

class Migration(migrations.Migration):
    dependencies = [
        ('userapp', '0015_wishlist_color_variant_alter_wishlist_product'),
        ('adminapp', '0015_remove_productimage_product_and_more'),
    ]

    operations = [
        migrations.RunPython(
            migrate_wishlist_to_color_variant,
            reverse_code=reverse_migrate_wishlist
        ),
    ]