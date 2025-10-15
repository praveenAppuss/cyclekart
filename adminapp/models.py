from decimal import ROUND_HALF_UP, Decimal
from django.db import models
from django.utils.text import slugify
from django.utils import timezone

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Brand(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    icon = models.ImageField(upload_to='brand_icons/')
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, blank=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name='products')
    price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Original price (same for all sizes)")
    discount_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, help_text="Discounted price (same for all sizes)")
    description = models.TextField(blank=True)
    thumbnail = models.ImageField(upload_to='thumbnails/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    is_trending = models.BooleanField(default=False)
    is_new = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_final_price(self):
        now = timezone.now()
        price = self.price or Decimal('0.00')
        discount_price = self.discount_price or price
        product_offers = self.product_offers.filter(
            is_deleted=False,
            is_active=True,
            valid_from__lte=now,
            valid_to__gte=now
        )
        product_discount = max([o.discount_percentage for o in product_offers], default=0)

        category_offers = self.category.category_offers.filter(
            is_deleted=False,
            is_active=True,
            valid_from__lte=now,
            valid_to__gte=now
        )
        category_discount = max([o.discount_percentage for o in category_offers], default=0)
        best_offer = max(product_discount, category_discount)
        offer_price = price * (Decimal('1.00') - Decimal(best_offer) / Decimal('100.00'))
        final_price = min(discount_price, offer_price)
        return final_price.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    def get_savings(self):
        price = self.price or Decimal('0.00')
        final_price = self.get_final_price()
        savings = price - final_price
        return savings if savings > 0 else Decimal('0.00')
    

    def get_best_discount(self):
        now = timezone.now()
        base_price = self.discount_price if self.discount_price else self.price
        product_offers = self.product_offers.filter(
            is_deleted=False,
            is_active=True,
            valid_from__lte=now,
            valid_to__gte=now
        )
        product_discount = max([o.discount_percentage for o in product_offers], default=0)
        category_offers = self.category.category_offers.filter(
            is_deleted=False,
            is_active=True,
            valid_from__lte=now,
            valid_to__gte=now
        )
        category_discount = max([o.discount_percentage for o in category_offers], default=0)
        return max(product_discount, category_discount)

    def __str__(self):
        return self.name


class ProductColorVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='color_variants')
    name = models.CharField(max_length=50)
    hex_code = models.CharField(max_length=7, blank=True, null=True)  
    
    def __str__(self):
        return f"{self.product.name} - {self.name}"


class ProductImage(models.Model):
    color_variant = models.ForeignKey(ProductColorVariant, on_delete=models.CASCADE, related_name='images', null=True, blank=True)
    image = models.ImageField(upload_to='product_images/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Image for {self.color_variant}"


class ProductSizeStock(models.Model):
    SIZE_CHOICES = [
        ('S', 'Small'),
        ('M', 'Medium'),
        ('L', 'Large'),
    ]

    color_variant = models.ForeignKey(ProductColorVariant, on_delete=models.CASCADE, related_name='size_stocks', null=True, blank=True)
    size = models.CharField(max_length=1, choices=SIZE_CHOICES)
    quantity = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('color_variant', 'size')

    def __str__(self):
        return f"{self.color_variant} - {self.size} - Qty: {self.quantity}"

    def get_size_display(self):
        return dict(self.SIZE_CHOICES).get(self.size, self.size)


class CategoryOffer(models.Model):
    categories = models.ManyToManyField(Category, related_name='category_offers')
    name = models.CharField(max_length=100)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2)  
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_valid(self):
        now = timezone.now()
        return self.is_active and self.valid_from <= now <= self.valid_to

    
    def __str__(self):
        return f"{self.name} - {self.discount_percentage}%"


class ProductOffer(models.Model):
    products = models.ManyToManyField(Product, related_name='product_offers')
    name = models.CharField(max_length=100)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_valid(self):
        now = timezone.now()
        return self.is_active and self.valid_from <= now <= self.valid_to

    def __str__(self):
        return f"{self.name} - {self.discount_percentage}%"