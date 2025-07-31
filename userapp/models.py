from django.contrib.auth.models import AbstractUser
from django.db import models
from adminapp.models import Product, ProductColorVariant, ProductSizeStock
class CustomUser(AbstractUser):
    email = models.EmailField(unique=True)
    mobile = models.CharField(max_length=15, unique=True, blank=True, null=True)
    is_blocked = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)
    profile_image = models.ImageField(upload_to='profile_images/', null=True, blank=True)


    def __str__(self):
        return self.username


class Address(models.Model):
    user = models.ForeignKey('CustomUser', on_delete=models.CASCADE, related_name='addresses')
    full_name = models.CharField(max_length=100)
    mobile = models.CharField(max_length=15)
    address_line = models.TextField()
    district = models.CharField(max_length=50,default="Unknown")
    state = models.CharField(max_length=50)
    country = models.CharField(max_length=50)
    pin_code = models.CharField(max_length=10)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.full_name} - {self.address_line}, {self.district}, {self.state} {self.pin_code}"



class Cart(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='cart')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Cart for {self.user.username}"


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    size = models.CharField(max_length=2, blank=True, null=True)  # Keep for now, but consider making required
    color = models.CharField(max_length=50, blank=True, null=True)  # Keep for now, but consider making required
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = ('cart', 'product', 'color', 'size')  # Enforce uniqueness

    def __str__(self):
        return f"{self.quantity} x {self.product.name} ({self.color or 'No Color'}, {self.size or 'No Size'})"

class Wishlist(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='wishlist_items')
    color_variant = models.ForeignKey(ProductColorVariant, on_delete=models.CASCADE, related_name='wishlist_items')
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'color_variant')

    def __str__(self):
        return f"{self.user.username} - {self.color_variant.product.name} ({self.color_variant.name})"



class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('shipped', 'Shipped'),
        ('out_for_delivery', 'Out for Delivery'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    ]

    PAYMENT_METHOD_CHOICES = [
        ('cod', 'Cash on Delivery'),
        ('card', 'Debit Card / Credit Card'),
        ('net_banking', 'Net Banking'),
        ('wallet', 'Wallet'),
    ]

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='orders')
    address = models.ForeignKey(Address, on_delete=models.SET_NULL, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    order_id = models.CharField(max_length=100, unique=True)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='cod')
    created_at = models.DateTimeField(auto_now_add=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return f"Order {self.order_id}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    size = models.CharField(max_length=2, blank=True, null=True)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"
