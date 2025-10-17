import csv
from datetime import datetime, timedelta
from decimal import Decimal
import re
from django.forms import DecimalField
from django.db.models import Sum, F, ExpressionWrapper
from django.db.models import ExpressionWrapper, F, Sum, DecimalField
from django.db.models.functions import Coalesce
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login,logout
from django.views.decorators.cache import never_cache
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.views.decorators.http import require_POST
from django.db.models import Q,Sum
from django.core.paginator import Paginator
import pytz
from userapp.services import WalletService
from userapp.models import Coupon, CustomUser, Order, OrderItem, ReturnRequest, Wallet, WalletTransaction
from django.utils.text import slugify
from adminapp.models import Product, Category, Brand, ProductColorVariant, ProductImage, ProductOffer,ProductSizeStock,CategoryOffer
import base64
import uuid
from django.core.files.base import ContentFile
import logging
from dateutil.relativedelta import relativedelta
from django.db.models.functions import TruncDate, TruncMonth, TruncYear,TruncDay
from django.db import transaction
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseServerError
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

def superuser_required(view_func):
    return user_passes_test(lambda u: u.is_authenticated and u.is_superuser, login_url='admin_login')(view_func)


#  Admin Login View
@never_cache
def admin_login(request):
    if request.user.is_authenticated and request.user.is_superuser:
        return redirect('admin_dashboard')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        user = authenticate(request, username=username, password=password)

        if user is not None and user.is_superuser:
            login(request, user)
            return redirect('admin_dashboard')
        else:
            messages.error(request, 'Invalid credentials or not authorized as admin.')

    return render(request, 'admin_login.html')


#  Admin Logout View
def admin_logout(request):
    logout(request)
    return redirect('admin_login')






#  USER LIST VIEW
@superuser_required
@never_cache
def user_list(request):
    query = request.GET.get('q', '')
    users = CustomUser.objects.filter(is_superuser=False)

    if query:
        users = users.filter(
            Q(username__icontains=query) |
            Q(email__icontains=query) |
            Q(mobile__icontains=query)
        )

    users = users.order_by('-date_joined')
    paginator = Paginator(users, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'user_list.html', {
        'users': page_obj,
        'query': query,
        'page_obj': page_obj,
    })


@superuser_required
@never_cache
@require_POST
def block_user(request, user_id):
    user = get_object_or_404(CustomUser, id=user_id, is_superuser=False)
    user.is_blocked = True
    user.save()
    return redirect('user_list')

@superuser_required
@never_cache
@require_POST
def unblock_user(request, user_id):
    user = get_object_or_404(CustomUser, id=user_id, is_superuser=False)
    user.is_blocked = False
    user.save()
    return redirect('user_list')

#  CATEGORY MANAGEMENT
@superuser_required
@never_cache
def category_list(request):
    query = request.GET.get('q', '').strip()
    categories = Category.objects.filter(is_deleted=False)
    if query:
        categories = categories.filter(name__icontains=query)
    categories = categories.order_by('-created_at')
    paginator = Paginator(categories, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'category_list.html', {
        'categories': page_obj,
        'query': query,
        'page_obj': page_obj,
    })

@superuser_required
@never_cache
def add_category(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if not name:
            messages.error(request, 'Category name is required.')
            return redirect('add_category')
        existing = Category.objects.filter(name__iexact=name).first()
        if existing:
            if not existing.is_deleted:
                messages.error(request, f'Category "{name}" already exists.')
                return redirect('add_category')
            else:
                existing.is_deleted = False
                existing.save()
                messages.success(request, f'Category "{name}" restored successfully.')
                return redirect('category_list')
        Category.objects.create(name=name)
        messages.success(request, f'Category "{name}" added successfully.')
        return redirect('category_list')
    return render(request, 'category_form.html')

@superuser_required
@never_cache
def edit_category(request, category_id):
    category = get_object_or_404(Category, id=category_id, is_deleted=False)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if not name:
            messages.error(request, 'Category name is required.')
        elif Category.objects.filter(name__iexact=name, is_deleted=False).exclude(id=category.id).exists():
            messages.error(request, f'Category "{name}" already exists.')
        else:
            category.name = name
            category.save()
            messages.success(request, f'Category updated to "{name}".')
            return redirect('category_list')
    return render(request, 'category_form.html', {'category': category})

@superuser_required
@never_cache
@require_POST
def delete_category(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    category.is_deleted = True
    category.save()
    return redirect('category_list')

@superuser_required
@never_cache
@require_POST
def toggle_category_status(request, category_id):
    category = get_object_or_404(Category, id=category_id, is_deleted=False)
    category.is_active = not category.is_active
    category.save()
    status = "listed" if category.is_active else "unlisted"
    messages.success(request, f'Category "{category.name}" has been {status}.')
    return redirect('category_list')

#  BRAND MANAGEMENT
@superuser_required
@never_cache
def brand_list(request):
    query = request.GET.get('q', '').strip()
    brands = Brand.objects.filter(is_deleted=False)
    if query:
        brands = brands.filter(name__icontains=query)
    brands = brands.order_by('-created_at')
    paginator = Paginator(brands, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'brand_list.html', {
        'brands': page_obj,
        'query': query,
        'page_obj': page_obj,
    })

@superuser_required
@never_cache
def add_brand(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        icon = request.FILES.get('icon')
        if not name:
            messages.error(request, 'Brand name is required.')
            return redirect('brand_list')
        existing = Brand.objects.filter(name__iexact=name).first()
        if existing:
            if not existing.is_deleted:
                messages.error(request, f'Brand "{name}" already exists.')
                return redirect('brand_list')
            else:
                existing.is_deleted = False
                existing.save()
                messages.success(request, f'Brand "{name}" restored successfully.')
                return redirect('brand_list')
        Brand.objects.create(name=name, description=description, icon=icon)
        messages.success(request, f'Brand "{name}" added successfully.')
        return redirect('brand_list')
    return redirect('brand_list')

@superuser_required
@never_cache
def edit_brand(request, brand_id):
    brand = get_object_or_404(Brand, id=brand_id, is_deleted=False)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        icon = request.FILES.get('icon')
        if not name:
            messages.error(request, 'Brand name is required.')
        elif Brand.objects.filter(name__iexact=name, is_deleted=False).exclude(id=brand.id).exists():
            messages.error(request, f'Brand "{name}" already exists.')
        else:
            brand.name = name
            brand.description = description
            if icon:
                brand.icon = icon
            brand.save()
            messages.success(request, f'Brand updated to "{name}".')
            return redirect('brand_list')
    return redirect('brand_list')

@superuser_required
@never_cache
@require_POST
def delete_brand(request, brand_id):
    brand = get_object_or_404(Brand, id=brand_id)
    brand.is_deleted = True
    brand.save()
    messages.success(request, f'Brand "{brand.name}" has been deleted.')
    return redirect('brand_list')

@superuser_required
@never_cache
@require_POST
def toggle_brand_status(request, brand_id):
    brand = get_object_or_404(Brand, id=brand_id, is_deleted=False)
    brand.is_active = not brand.is_active
    brand.save()
    status = "listed" if brand.is_active else "unlisted"
    messages.success(request, f'Brand "{brand.name}" has been {status}.')
    return redirect('brand_list')

# PRODUCT LIST
@superuser_required
@never_cache
def product_list(request):
    query = request.GET.get('q', '')
    products = Product.objects.filter(is_deleted=False).prefetch_related(
    'color_variants__size_stocks',
    'color_variants__images'
)

    if query:
        products = products.filter(
            Q(name__icontains=query) | Q(category__name__icontains=query)
        )
    products = products.order_by('-created_at')
    
    for product in products:
        all_stocks = []
        for variant in product.color_variants.all():
            for stock in variant.size_stocks.all():
                all_stocks.append(f"{variant.name}-{stock.size}={stock.quantity}")
        product.stock_summary = ', '.join(all_stocks)

    paginator = Paginator(products, 5)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'product_list.html', {
        'products': page_obj,
        'query': query,
        'page_obj': page_obj,
    })




@superuser_required
@never_cache
def add_product(request):
    categories = Category.objects.filter(is_active=True, is_deleted=False)
    brands = Brand.objects.filter(is_active=True, is_deleted=False)
    color_choices = ['Red', 'Blue', 'Green', 'Black', 'White', 'Yellow']
    size_choices = ['S', 'M', 'L']

    color_hex_map = {
        'Red': '#ff0000',
        'Blue': '#0000ff',
        'Green': '#008000',
        'Black': '#000000',
        'White': '#ffffff',
        'Yellow': '#ffff00',
    }

    errors = {}
    old = {}

    if request.method == 'POST':
        logger.info("Processing POST request for add_product")
        name = request.POST.get('name', '').strip()
        category_id = request.POST.get('category')
        brand_id = request.POST.get('brand')
        description = request.POST.get('description', '').strip()
        price = request.POST.get('price', '0.00')
        discount_price = request.POST.get('discount_price', None)
        colors = request.POST.getlist('colors[]')
        stocks = request.POST.getlist('stocks[]')
        cropped_images = request.POST.getlist('cropped_images[]')

        old = {
            'name': name,
            'category': category_id,
            'brand': brand_id,
            'description': description,
            'price': price,
            'discount_price': discount_price,
            'colors': colors,
            'stocks': stocks,
        }

        
        logger.debug(f"Validation: name={name}, category_id={category_id}, colors={colors}, images={len(cropped_images)}, stocks={stocks}")
        if Product.objects.filter(name__iexact=name).exists():
            errors['name'] = "Product with this name already exists."
        if not name:
            errors['name'] = "Product name is required."
        if not category_id:
            errors['category'] = "Please select a category."
        if not brand_id:
            errors['brand'] = "Please select a brand."
        if not colors:
            errors['colors'] = "Please add at least one color variant."
        expected_stock_count = len(colors) * len(size_choices)
        if len(stocks) != expected_stock_count:
            errors['stocks'] = f"Expected {expected_stock_count} stock entries (for {len(colors)} colors × {len(size_choices)} sizes), got {len(stocks)}."
        if len(cropped_images) < 3 * len(colors):
            errors['images'] = f"Please upload at least 3 images per color variant (got {len(cropped_images)}, need {3 * len(colors)})."
        try:
            price = float(price)
            if discount_price:
                discount_price = float(discount_price)
                if discount_price > price:
                    errors['discount_price'] = "Discount price cannot exceed original price."
        except ValueError:
            errors['price'] = "Price must be a valid number."

        if errors:
            logger.warning(f"Validation failed with errors: {errors}")
            return render(request, 'product_form.html', {
                'categories': categories,
                'brands': brands,
                'colors': color_choices,
                'sizes': size_choices,
                'errors': errors,
                'old': old,
                'zipped_stocks': list(zip(range(len(colors) if colors else 1), size_choices, [''] * len(size_choices))),
                'existing_images': [],
            })

        
        logger.info(f"Creating product: {name}")
        try:
            with transaction.atomic():
                product = Product.objects.create(
                    name=name,
                    slug=slugify(name),
                    category_id=category_id,
                    brand_id=brand_id,
                    price=price,
                    discount_price=discount_price,
                    description=description
                )

                
                image_index = 0
                stock_index = 0
                for i, color in enumerate(colors):
                    color_variant = ProductColorVariant.objects.create(
                        product=product,
                        name=color,
                        hex_code=color_hex_map.get(color, '#000000')
                    )

                    
                    for size in size_choices:
                        stock_value = int(stocks[stock_index]) if stock_index < len(stocks) and stocks[stock_index].isdigit() else 0
                        logger.debug(f"Saving stock for {color} - {size}: {stock_value}")
                        ProductSizeStock.objects.create(
                            color_variant=color_variant,
                            size=size,
                            quantity=stock_value
                        )
                        stock_index += 1

                    
                    image_count = min(3, len(cropped_images) - image_index)
                    for _ in range(image_count):
                        if image_index < len(cropped_images):
                            img_str = cropped_images[image_index]
                            try:
                                format, img_data = img_str.split(';base64,')
                                ext = format.split('/')[-1]
                                file_name = f"{uuid.uuid4()}.{ext}"
                                image_file = ContentFile(base64.b64decode(img_data), name=file_name)
                                new_img = ProductImage.objects.create(color_variant=color_variant, image=image_file)
                                if i == 0 and _ == 0:  
                                    product.thumbnail = new_img.image
                                    product.save()
                            except Exception as e:
                                logger.error(f"Image saving error for variant {color}, image {_}: {str(e)}")
                                raise
                        image_index += 1

            logger.info(f"Product {name} created successfully")
            messages.success(request, 'Product added successfully.')
            return redirect('product_list')

        except Exception as e:
            logger.error(f"Transaction failed: {str(e)}")
            messages.error(request, f"Failed to add product: {str(e)}")
            return render(request, 'product_form.html', {
                'categories': categories,
                'brands': brands,
                'colors': color_choices,
                'sizes': size_choices,
                'errors': {'general': f"Error: {str(e)}"},
                'old': old,
                'zipped_stocks': list(zip(range(len(colors) if colors else 1), size_choices, [''] * len(size_choices))),
                'existing_images': [],
            })

    return render(request, 'product_form.html', {
        'categories': categories,
        'brands': brands,
        'colors': color_choices,
        'sizes': size_choices,
        'errors': {},
        'old': {},
        'zipped_stocks': list(zip(range(1), size_choices, [''] * len(size_choices))),
        'existing_images': [],
    })



@superuser_required
@never_cache
def edit_product(request, product_id):
    product = get_object_or_404(Product, id=product_id, is_deleted=False)
    categories = Category.objects.filter(is_active=True, is_deleted=False)
    brands = Brand.objects.filter(is_active=True, is_deleted=False)
    color_choices = ['Red', 'Blue', 'Green', 'Black', 'White', 'Yellow']
    size_choices = ['S', 'M', 'L']

    color_hex_map = {
        'Red': '#ff0000',
        'Blue': '#0000ff',
        'Green': '#008000',
        'Black': '#000000',
        'White': '#ffffff',
        'Yellow': '#ffff00',
    }

    errors = {}
    old = {}

    # Prepare existing data
    color_variants = product.color_variants.all()
    existing_images = {variant.id: list(ProductImage.objects.filter(color_variant=variant)) for variant in color_variants}
    stock_map = {}
    for variant in color_variants:
        for stock in variant.size_stocks.all():
            stock_map[f"{variant.id}_{stock.size}"] = stock.quantity
    zipped_stocks = []
    for i, variant in enumerate(color_variants):
        for size in size_choices:
            stock = stock_map.get(f"{variant.id}_{size}", 0)
            zipped_stocks.append((i, size, stock))

    if request.method == 'POST':
        logger.info(f"Processing POST request for edit_product, product_id={product_id}")
        name = request.POST.get('name', product.name).strip()
        category_id = request.POST.get('category', str(product.category_id))
        brand_id = request.POST.get('brand', str(product.brand_id))
        description = request.POST.get('description', product.description).strip()
        price = request.POST.get('price', str(product.price))
        discount_price = request.POST.get('discount_price', str(product.discount_price) if product.discount_price else None)
        colors = request.POST.getlist('colors[]')
        stocks = request.POST.getlist('stocks[]')

        old = {
            'name': name,
            'category': category_id,
            'brand': brand_id,
            'description': description,
            'price': price,
            'discount_price': discount_price,
            'colors': colors,
            'stocks': stocks,
        }

        # Validation
        logger.debug(f"POST data: {dict(request.POST)}")
        if Product.objects.filter(name__iexact=name).exclude(id=product_id).exists() and name != product.name:
            errors['name'] = "Another product with this name already exists."
        if not name:
            errors['name'] = "Product name is required."
        if not category_id:
            errors['category'] = "Please select a category."
        if not brand_id:
            errors['brand'] = "Please select a brand."
        if not colors:
            errors['colors'] = "Please add at least one color variant."
        expected_stock_count = len(colors) * len(size_choices)
        if len(stocks) != expected_stock_count:
            errors['stocks'] = f"Expected {expected_stock_count} stock entries (for {len(colors)} colors × {len(size_choices)} sizes), got {len(stocks)}."
        
        variant_image_counts = {}
        variant_image_map = {}
        for i, color in enumerate(colors):
            new_images = request.POST.getlist(f'cropped_images_{i}[]')
            variant_id = next((v.id for v in color_variants if v.name == color), None)
            existing_count = len(existing_images.get(variant_id, [])) if variant_id else 0
            len_new = len(new_images)
            variant_image_counts[color] = len_new if len_new > 0 else existing_count
            variant_image_map[color] = new_images
            if variant_image_counts[color] < 3:
                errors['images'] = f"Color {color} has only {variant_image_counts[color]} images; at least 3 required per variant."
        try:
            price = float(price)
            if discount_price:
                discount_price = float(discount_price)
                if discount_price > price:
                    errors['discount_price'] = "Discount price cannot exceed original price."
        except ValueError:
            errors['price'] = "Price must be a valid number."

        if errors:
            logger.warning(f"Validation failed with errors: {errors}")
            return render(request, 'product_form.html', {
                'product': product,
                'categories': categories,
                'brands': brands,
                'colors': color_choices,
                'sizes': size_choices,
                'zipped_stocks': zipped_stocks,
                'existing_images': [img for imgs in existing_images.values() for img in imgs],
                'errors': errors,
                'old': old,
            })

        # Update product
        logger.info(f"Updating product: {name}")
        try:
            with transaction.atomic():
                product.name = name
                product.slug = slugify(name)
                product.category_id = category_id
                product.brand_id = brand_id
                product.description = description
                product.price = price
                product.discount_price = discount_price
                product.save()

                # Delete existing variants
                ProductColorVariant.objects.filter(product=product).delete()
                stock_index = 0
                first_image = None
                for i, color in enumerate(colors):
                    color_variant = ProductColorVariant.objects.create(
                        product=product,
                        name=color,
                        hex_code=color_hex_map.get(color, '#000000')
                    )

                    # Save stocks
                    for size in size_choices:
                        stock_value = int(stocks[stock_index]) if stock_index < len(stocks) and stocks[stock_index].isdigit() else 0
                        logger.debug(f"Saving stock for {color} - {size}: {stock_value}")
                        ProductSizeStock.objects.create(
                            color_variant=color_variant,
                            size=size,
                            quantity=stock_value
                        )
                        stock_index += 1

                    # Save images
                    new_images = variant_image_map.get(color, [])
                    if len(new_images) > 0:
                        for img_str in new_images:
                            try:
                                format, img_data = img_str.split(';base64,')
                                ext = format.split('/')[-1]
                                file_name = f"{uuid.uuid4()}.{ext}"
                                image_file = ContentFile(base64.b64decode(img_data), name=file_name)
                                new_img = ProductImage.objects.create(color_variant=color_variant, image=image_file)
                                if i == 0 and not first_image:
                                    first_image = new_img.image
                            except Exception as e:
                                logger.error(f"Image saving error for variant {color}: {str(e)}")
                                raise
                    else:
                        # Copy existing images for unchanged variants
                        existing_imgs = existing_images.get(next((v.id for v in color_variants if v.name == color), None), [])
                        for img in existing_imgs:
                            new_img = ProductImage.objects.create(
                                color_variant=color_variant,
                                image=img.image
                            )
                            if i == 0 and not first_image:
                                first_image = new_img.image

                # Update thumbnail to the first image of the first variant, or None if no variants
                product.thumbnail = first_image
                product.save()

            logger.info(f"Product {name} updated successfully with {len(colors)} variants")
            messages.success(request, "Product updated successfully.")
            return redirect('product_list')

        except Exception as e:
            logger.error(f"Transaction failed: {str(e)}")
            messages.error(request, f"Failed to update product: {str(e)}")
            return render(request, 'product_form.html', {
                'product': product,
                'categories': categories,
                'brands': brands,
                'colors': color_choices,
                'sizes': size_choices,
                'zipped_stocks': zipped_stocks,
                'existing_images': [img for imgs in existing_images.values() for img in imgs],
                'errors': {'general': f"Error: {str(e)}"},
                'old': old,
            })

    return render(request, 'product_form.html', {
        'product': product,
        'categories': categories,
        'brands': brands,
        'colors': color_choices,
        'sizes': size_choices,
        'zipped_stocks': zipped_stocks,
        'existing_images': [img for imgs in existing_images.values() for img in imgs],
        'errors': {},
        'old': {
            'name': product.name,
            'category': str(product.category_id),
            'brand': str(product.brand_id),
            'description': product.description,
            'price': str(product.price),
            'discount_price': str(product.discount_price) if product.discount_price else '',
            'colors': [variant.name for variant in color_variants],
            'stocks': [stock_map.get(f"{variant.id}_{size}", '0') for variant in color_variants for size in size_choices],
        }
    })

@superuser_required
@never_cache
def delete_product(request, product_id):
    if request.method != 'POST':
        return HttpResponseBadRequest("Invalid request method.")
    product = get_object_or_404(Product, id=product_id, is_deleted=False)
    product.is_deleted = True
    product.save()
    messages.success(request, 'Product deleted successfully.')
    return redirect('product_list')


@superuser_required
@never_cache
def toggle_product_status(request, product_id):
    if request.method != 'POST':
        return HttpResponseBadRequest("Invalid request method.")
    product = get_object_or_404(Product, id=product_id, is_deleted=False)
    product.is_active = not product.is_active
    product.save()
    status = "listed" if product.is_active else "unlisted"
    messages.success(request, f"Product has been {status}.")
    return redirect('product_list')



# ------------------------ordermanagement--------------------------------------#


@superuser_required
def admin_order_list(request):
    search_query = request.GET.get('q', '')
    sort_by = request.GET.get('sort', '-created_at')  
    filter_status = request.GET.get('status', '')
    orders = Order.objects.all()

    if search_query:
        orders = orders.filter(
            Q(order_id__icontains=search_query) |
            Q(user__username__icontains=search_query) |
            Q(user__email__icontains=search_query)
        )

    if filter_status:
        orders = orders.filter(status=filter_status)

    
    if sort_by in ['created_at', '-created_at', 'status', '-status']:
        orders = orders.order_by(sort_by)
    else:
        orders = orders.order_by('-created_at')  

    paginator = Paginator(orders, 4)  
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'sort_by': sort_by,
        'filter_status': filter_status,
        'status_choices': Order.STATUS_CHOICES,
    }
    return render(request, 'admin_order_list.html', context)


@superuser_required
def admin_order_detail(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    context = {
        'order': order,
        'items': order.items.all(),
    }
    return render(request, 'admin_order_detail.html', context)


@superuser_required
@require_POST
def update_order_status(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    new_status = request.POST.get('status')

    if new_status not in dict(Order.STATUS_CHOICES):
        logger.error(f"Invalid status {new_status} for order {order.order_id}")
        messages.error(request, "Invalid status selected.")
        return redirect('admin_order_detail', order_id=order.id)

    if order.status == 'cancelled':
        logger.warning(f"Attempted to update status of cancelled order {order.order_id}")
        messages.error(request, "Cannot update status of a cancelled order.")
        return redirect('admin_order_detail', order_id=order.id)

    if new_status != order.status:
        with transaction.atomic():
            order.status = new_status
            if new_status == 'delivered':
                order.delivered_at = timezone.now()
                if order.payment_status == 'pending':  # Update to 'paid' for COD and other pending payments
                    order.payment_status = 'paid'
                    # Update all OrderItem payment_status to 'paid' to match the order
                    order.items.update(payment_status='paid')
            elif new_status == 'cancelled':
                order.cancelled_at = timezone.now()
                if order.payment_status == 'paid':
                    try:
                        wallet = order.user.wallet
                        refund_amount = order.total_amount
                        WalletTransaction.objects.create(
                            wallet=wallet,
                            order=order,
                            amount=refund_amount,
                            transaction_type='credit',
                            description=f"Refund for cancelled Order {order.order_id}"
                        )
                        wallet.balance += refund_amount
                        wallet.save()
                        order.payment_status = 'refunded'  
                        # Update all OrderItem payment_status to 'refunded'
                        order.items.update(payment_status='refunded')
                        logger.info(f"Refunded ₹{refund_amount:.2f} for cancelled order {order.order_id}")
                    except Exception as e:
                        logger.error(f"Refund failed for order {order.order_id}: {str(e)}")
                        messages.warning(request, "Status updated, but refund failed.")
            elif new_status == 'returned':
                order.returned_at = timezone.now()
                order.delivered_at = None
                order.cancelled_at = None
                if not order.items.filter(status='return_accepted').exists():
                    messages.error(request, "Cannot set to 'returned' unless all items are return accepted.")
                    return redirect('admin_order_detail', order_id=order.id)
                
                if order.payment_status == 'paid':
                    try:
                        wallet = order.user.wallet
                        refund_amount = order.total_amount
                        WalletTransaction.objects.create(
                            wallet=wallet,
                            order=order,
                            amount=refund_amount,
                            transaction_type='credit',
                            description=f"Refund for returned Order {order.order_id}"
                        )
                        wallet.balance += refund_amount
                        wallet.save()
                        order.payment_status = 'refunded'  
                        # Update all OrderItem payment_status to 'refunded'
                        order.items.update(payment_status='refunded')
                        logger.info(f"Refunded ₹{refund_amount:.2f} for returned order {order.order_id}")
                    except Exception as e:
                        logger.error(f"Refund failed for order {order.order_id}: {str(e)}")
                        messages.warning(request, "Status updated, but refund failed.")
            else:
                order.delivered_at = None
                order.cancelled_at = None
                order.returned_at = None

            order.save()
            logger.info(f"Order {order.order_id} status updated to {new_status}")
            messages.success(request, f"Order {order.order_id} status updated to {order.get_status_display()}.")
    else:
        messages.info(request, "No changes made to order status.")

    return redirect('admin_order_detail', order_id=order.id)


@superuser_required
@require_POST
def return_accept(request, item_id):
    item = get_object_or_404(OrderItem, id=item_id)
    order = item.order

    if item.status != 'return_requested':
        messages.warning(request, "Invalid return request status.")
        return redirect('admin_order_detail', order_id=order.id)

    try:
        with transaction.atomic():
            item.status = 'return_accepted'
            item.is_return_approved = True
            item.is_return_rejected = False
            # Update the specific item's payment_status to 'refunded' if order was paid
            if order.payment_status == 'paid':
                item.payment_status = 'refunded'
            item.save()

            if order.payment_status == 'paid':
                total_net_before_coupon = sum(
                    ((oi.discount_price if oi.discount_price else oi.price) * oi.quantity)
                    for oi in order.items.all()
                )
                item_net_before_coupon = (item.discount_price if item.discount_price else item.price) * item.quantity
                item_coupon_share = order.coupon_discount * (item_net_before_coupon / total_net_before_coupon) if total_net_before_coupon > 0 else Decimal('0.00')
                item_effective = item_net_before_coupon - item_coupon_share

                total_after_discounts = order.subtotal - order.discount - order.coupon_discount
                tax_amount = order.tax * (item_effective / total_after_discounts) if total_after_discounts > 0 else Decimal('0.00')

                shipping_amount = Decimal('0.00')
                all_items_returned = not order.items.filter(status__in=['active', 'return_requested']).exists()
                if all_items_returned:
                    shipping_amount = order.shipping_cost

                refund_amount = item_effective + tax_amount + shipping_amount                
                wallet, _ = Wallet.objects.get_or_create(user=order.user)

                # Generate unique transaction ID
                unique_txn_id = f"TXN-{uuid.uuid4().hex[:8].upper()}"

                WalletTransaction.objects.create(
                    wallet=wallet,
                    order=order,
                    amount=refund_amount,
                    transaction_type='credit',
                    description=f"Refund for return of {item.product.name} (Order {order.order_id})",
                    transaction_id=unique_txn_id
                )

                wallet.balance = (wallet.balance or Decimal('0.00')) + refund_amount
                wallet.save()

                messages.success(request, f"Return request accepted. ₹{refund_amount:.2f} refunded to user's wallet.")
                logger.info(f"Refunded ₹{refund_amount:.2f} to wallet for {order.user.username} (Order {order.order_id})")

            if item.color_variant and item.size:
                try:
                    size_stock = ProductSizeStock.objects.get(color_variant=item.color_variant, size=item.size)
                    size_stock.quantity += item.quantity
                    size_stock.save()
                    logger.info(f"Stock updated for {size_stock} (+{item.quantity})")
                except ProductSizeStock.DoesNotExist:
                    logger.error(f"Stock not found for {item.color_variant}, {item.size}")
                    messages.warning(request, "Return accepted, but stock not updated: variant/size not found.")

            # Update order status and payment_status only if all items are processed
            all_items_returned = not order.items.filter(status__in=['active', 'return_requested']).exists()
            if all_items_returned:
                order.status = 'returned'
                order.returned_at = timezone.now()
                if order.payment_status == 'paid':
                    order.payment_status = 'refunded'
                    # Update all remaining OrderItem payment_status to 'refunded'
                    order.items.update(payment_status='refunded')
                order.save()
                logger.info(f"Order {order.order_id} status updated to 'returned' and payment_status to '{order.payment_status}'")

    except Exception as e:
        logger.error(f"Error processing return acceptance for item {item.id}: {str(e)}")
        messages.error(request, f"Error processing return request: {str(e)}")

    return redirect('admin_order_detail', order_id=order.id)


@superuser_required
@require_POST
def return_reject(request, item_id):
    item = get_object_or_404(OrderItem, id=item_id)
    order = item.order
    if item.status != 'return_requested':
        messages.warning(request, "Invalid return request status.")
        return redirect('admin_order_detail', order_id=order.id)

    try:
        with transaction.atomic():
            item.status = 'return_rejected'
            item.is_return_approved = False
            item.is_return_rejected = True
            item.return_rejected_reason = request.POST.get('reason', 'No reason provided')
            item.save()
            messages.success(request, "Return request rejected.")
    except Exception as e:
        logger.error(f"Error processing return rejection for item {item.id}: {str(e)}")
        messages.error(request, f"Error processing return request: {str(e)}")
    return redirect('admin_order_detail', order_id=order.id)


# ------------------------coupon management---------------------------#

@superuser_required
def coupon_list(request):
    coupons = Coupon.objects.filter(is_deleted=False).order_by('-valid_to')
    paginator = Paginator(coupons, 6)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'coupon_list.html', {'coupons': page_obj, 'now': timezone.now()})

@superuser_required
def add_coupon(request):
    if request.method == 'POST':
        code = request.POST.get('code', '').strip()
        discount_amount = request.POST.get('discount_amount', '').strip()
        minimum_order_amount = request.POST.get('minimum_order_amount', '').strip()
        valid_from = request.POST.get('valid_from', '').strip()
        valid_to = request.POST.get('valid_to', '').strip()
        error = {}

        if not code:
            error['code'] = 'Coupon code is required.'
        elif re.fullmatch(r'_+', code):
            error['code'] = 'Coupon code cannot be only underscores.'
        elif code.isdigit():
            error['code'] = 'Coupon code cannot be only digits.'
        elif not re.match(r'^[A-Za-z0-9_-]+$', code):
            error['code'] = 'Coupon code can only contain letters, numbers, dashes, and underscores.'
        elif Coupon.objects.filter(code=code).exists():
            error['code'] = 'Coupon code already exists.'

        if not discount_amount:
            error['discount_amount'] = 'Discount amount is required.'
        else:
            try:
                discount_amount = float(discount_amount)
                if discount_amount <= 0:
                    error['discount_amount'] = 'Discount must be greater than zero.'
            except ValueError:
                error['discount_amount'] = 'Discount must be a number.'

        if not minimum_order_amount:
            error['minimum_order_amount'] = 'Minimum order amount is required.'
        else:
            try:
                minimum_order_amount = float(minimum_order_amount)
                if minimum_order_amount <= 0:
                    error['minimum_order_amount'] = 'Minimum order must be greater than zero.'
            except ValueError:
                error['minimum_order_amount'] = 'Minimum order must be a number.'

        date_format = '%Y-%m-%d'
        try:
            valid_from_date = datetime.strptime(valid_from, date_format)
            valid_from_date = timezone.make_aware(valid_from_date)
        except ValueError:
            error['valid_from'] = 'Invalid start date format (YYYY-MM-DD).'

        try:
            valid_to_date = datetime.strptime(valid_to, date_format)
            valid_to_date = timezone.make_aware(valid_to_date)
        except ValueError:
            error['valid_to'] = 'Invalid end date format (YYYY-MM-DD).'

        if 'valid_from' not in error and 'valid_to' not in error:
            if valid_to_date < valid_from_date:
                error['valid_to'] = 'End date cannot be before start date.'

        if not error:
            Coupon.objects.create(
                code=code,
                discount_amount=discount_amount,
                minimum_order_amount=minimum_order_amount,
                valid_from=valid_from_date,
                valid_to=valid_to_date,
                active=True
            )
            messages.success(request, 'Coupon created successfully.')
            return redirect('coupon_list')
        else:
            return render(request, 'add_coupon.html', {'error': error, 'form': {
                'code': code,
                'discount_amount': discount_amount,
                'minimum_order_amount': minimum_order_amount,
                'valid_from': valid_from,
                'valid_to': valid_to,
            }})

    return render(request, 'add_coupon.html')

@superuser_required
def edit_coupon(request, coupon_id):
    coupon = get_object_or_404(Coupon, id=coupon_id)
    if request.method == 'POST':
        code = request.POST.get('code', '').strip()
        discount_amount = request.POST.get('discount_amount', '').strip()
        minimum_order_amount = request.POST.get('minimum_order_amount', '').strip()
        valid_from = request.POST.get('valid_from', '').strip()
        valid_to = request.POST.get('valid_to', '').strip()
        error = {}

        if Coupon.objects.exclude(id=coupon_id).filter(code__iexact=code).exists():
            error['code'] = 'This coupon code already exists.'
        if not code:
            error['code'] = 'Coupon code is required.'
        elif re.fullmatch(r'_+', code):
            error['code'] = "Coupon code can't be only underscores."
        elif code.isdigit():
            error['code'] = "Coupon code can't be only digits."
        elif not re.match(r'^[A-Za-z0-9_-]+$', code):
            error['code'] = 'Coupon code can only contain letters, numbers, dashes, and underscores.'

        if not discount_amount:
            error['discount_amount'] = 'Discount amount is required.'
        else:
            try:
                discount_amount = float(discount_amount)
                if discount_amount <= 0:
                    error['discount_amount'] = 'Discount amount must be greater than zero.'
            except ValueError:
                error['discount_amount'] = 'Discount amount must be a number.'

        if not minimum_order_amount:
            error['minimum_order_amount'] = 'Minimum order amount is required.'
        else:
            try:
                minimum_order_amount = float(minimum_order_amount)
                if minimum_order_amount <= 0:
                    error['minimum_order_amount'] = 'Minimum order amount must be greater than zero.'
            except ValueError:
                error['minimum_order_amount'] = 'Minimum order amount must be a number.'

        date_format = '%Y-%m-%d'
        try:
            valid_from_date = datetime.strptime(valid_from, date_format)
            valid_from_date = timezone.make_aware(valid_from_date)
        except ValueError:
            error['valid_from'] = 'Invalid start date format (YYYY-MM-DD).'

        try:
            valid_to_date = datetime.strptime(valid_to, date_format)
            valid_to_date = timezone.make_aware(valid_to_date)
        except ValueError:
            error['valid_to'] = 'Invalid end date format (YYYY-MM-DD).'

        if 'valid_from' not in error and 'valid_to' not in error:
            if valid_to_date < valid_from_date:
                error['valid_to'] = 'End date cannot be before start date.'

        if not error:
            coupon.code = code
            coupon.discount_amount = discount_amount
            coupon.minimum_order_amount = minimum_order_amount
            coupon.valid_from = valid_from_date
            coupon.valid_to = valid_to_date
            coupon.save()
            messages.success(request, 'Coupon updated successfully.')
            return redirect('coupon_list')
        else:
            return render(request, 'add_coupon.html', {'error': error, 'form': {
                'coupon_id': coupon_id,
                'code': code,
                'discount_amount': discount_amount,
                'minimum_order_amount': minimum_order_amount,
                'valid_from': valid_from,
                'valid_to': valid_to,
            }})

    form = {
        'coupon_id': coupon.id,
        'code': coupon.code,
        'discount_amount': coupon.discount_amount,
        'minimum_order_amount': coupon.minimum_order_amount,
        'valid_from': coupon.valid_from.date().strftime('%Y-%m-%d') if coupon.valid_from else '',
        'valid_to': coupon.valid_to.date().strftime('%Y-%m-%d') if coupon.valid_to else '',
    }
    return render(request, 'add_coupon.html', {'form': form})

@superuser_required
def delete_coupon(request, coupon_id):
    coupon = get_object_or_404(Coupon, id=coupon_id, is_deleted=False)
    coupon.is_deleted = True
    coupon.save()
    messages.success(request, f"Coupon '{coupon.code}' has been deleted successfully.")
    return redirect('coupon_list')

@superuser_required
def toggle_coupon(request, coupon_id):
    coupon = get_object_or_404(Coupon, id=coupon_id)
    coupon.active = not coupon.active
    coupon.save()
    status = 'Enabled' if coupon.active else 'Disabled'
    messages.success(request, f'Coupon has been {status} successfully.')
    return redirect('coupon_list')


#----------------------------------Offer Management----------------------------------------#

@superuser_required
def list_offers(request):
    now = timezone.now()
    
    product_offers = ProductOffer.objects.filter(
        is_deleted=False
    ).prefetch_related('products__category', 'products__brand', 'products').order_by('-created_at')
    
    category_offers = CategoryOffer.objects.filter(
        is_deleted=False
    ).prefetch_related('categories').order_by('-created_at')

    context = {
        'product_offers': product_offers,
        'category_offers': category_offers,
        'now': now,
    }
    return render(request, 'offers_list.html', context)

@superuser_required
def add_product_offer(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        discount_percentage_str = request.POST.get('discount_percentage')
        valid_from_str = request.POST.get('valid_from')
        valid_to_str = request.POST.get('valid_to')
        selected_product_ids = request.POST.getlist('products')  

        errors = []
        if not name:
            errors.append('Offer name is required.')
        if not discount_percentage_str:
            errors.append('Discount percentage is required.')
        else:
            try:
                discount_percentage = float(discount_percentage_str)
                if not 0 <= discount_percentage <= 100:
                    errors.append('Discount percentage must be between 0 and 100.')
            except ValueError:
                errors.append('Discount percentage must be a valid number.')
        
        if not valid_from_str or not valid_to_str:
            errors.append('Both valid from and valid to are required.')
        else:
            date_format = '%Y-%m-%d'
            try:
                valid_from_date = datetime.strptime(valid_from_str, date_format)
                valid_to_date = datetime.strptime(valid_to_str, date_format)
                valid_from = timezone.make_aware(valid_from_date)
                valid_to = timezone.make_aware(valid_to_date)
                if valid_to < valid_from:
                    errors.append("Valid 'to' must be after 'from'.")
            except ValueError:
                errors.append('Invalid date format (YYYY-MM-DD).')

        if len(selected_product_ids) == 0:
            errors.append('Select at least one product.')

        if errors:
            messages.error(request, '<br>'.join(errors))  
        else:
            offer = ProductOffer.objects.create(
                name=name,
                discount_percentage=discount_percentage,
                valid_from=valid_from,
                valid_to=valid_to,
                is_active=True,
                is_deleted=False
            )
            selected_products = Product.objects.filter(
                id__in=selected_product_ids,
                is_active=True,
                is_deleted=False
            )
            offer.products.set(selected_products)
            messages.success(request, f'Product offer "{name}" created successfully with {selected_products.count()} products!')
            return redirect('offers_list')

    products = Product.objects.filter(is_active=True, is_deleted=False).order_by('name')
    return render(request, 'add_product_offer.html', {'products': products})

@superuser_required
def add_category_offer(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        discount_percentage_str = request.POST.get('discount_percentage')
        valid_from_str = request.POST.get('valid_from')
        valid_to_str = request.POST.get('valid_to')
        selected_category_ids = request.POST.getlist('categories')

        errors = []
        if not name:
            errors.append('Offer name is required.')
        if not discount_percentage_str:
            errors.append('Discount percentage is required.')
        else:
            try:
                discount_percentage = float(discount_percentage_str)
                if not 0 <= discount_percentage <= 100:
                    errors.append('Discount percentage must be between 0 and 100.')
            except ValueError:
                errors.append('Discount percentage must be a valid number.')
        
        if not valid_from_str or not valid_to_str:
            errors.append('Both valid from and valid to are required.')
        else:
            date_format = '%Y-%m-%d'
            try:
                valid_from_date = datetime.strptime(valid_from_str, date_format)
                valid_to_date = datetime.strptime(valid_to_str, date_format)
                valid_from = timezone.make_aware(valid_from_date)
                valid_to = timezone.make_aware(valid_to_date)
                if valid_to < valid_from:
                    errors.append("Valid 'to' must be after 'from'.")
            except ValueError:
                errors.append('Invalid date format (YYYY-MM-DD).')

        if len(selected_category_ids) == 0:
            errors.append('Select at least one category.')

        if errors:
            messages.error(request, '<br>'.join(errors))
        else:
            offer = CategoryOffer.objects.create(
                name=name,
                discount_percentage=discount_percentage,
                valid_from=valid_from,
                valid_to=valid_to,
                is_active=True,
                is_deleted=False
            )
            selected_categories = Category.objects.filter(
                id__in=selected_category_ids,
                is_active=True,
                is_deleted=False
            )
            offer.categories.set(selected_categories)
            messages.success(request, f'Category offer "{name}" created successfully with {selected_categories.count()} categories!')
            return redirect('offers_list')

    categories = Category.objects.filter(is_active=True, is_deleted=False).order_by('name')
    return render(request, 'add_category_offer.html', {'categories': categories})

@superuser_required
def edit_product_offer(request, offer_id):
    offer = get_object_or_404(ProductOffer, id=offer_id, is_deleted=False)
    
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        discount_percentage_str = request.POST.get('discount_percentage')
        valid_from_str = request.POST.get('valid_from')
        valid_to_str = request.POST.get('valid_to')
        selected_product_ids = request.POST.getlist('products')  

        errors = []
        if not name:
            errors.append('Offer name is required.')
        if not discount_percentage_str:
            errors.append('Discount percentage is required.')
        else:
            try:
                discount_percentage = float(discount_percentage_str)
                if not 0 <= discount_percentage <= 100:
                    errors.append('Discount percentage must be between 0 and 100.')
            except ValueError:
                errors.append('Discount percentage must be a valid number.')
        
        if not valid_from_str or not valid_to_str:
            errors.append('Both valid from and valid to are required.')
        else:
            date_format = '%Y-%m-%d'
            try:
                valid_from_date = datetime.strptime(valid_from_str, date_format)
                valid_to_date = datetime.strptime(valid_to_str, date_format)
                valid_from = timezone.make_aware(valid_from_date)
                valid_to = timezone.make_aware(valid_to_date)
                if valid_to < valid_from:
                    errors.append("Valid 'to' must be after 'from'.")
            except ValueError:
                errors.append('Invalid date format (YYYY-MM-DD).')

        if len(selected_product_ids) == 0:
            errors.append('Select at least one product.')

        if errors:
            messages.error(request, '<br>'.join(errors))  
            products = Product.objects.filter(is_active=True, is_deleted=False).order_by('name')
            selected_product_ids_current = [str(p.id) for p in offer.products.all()]
            context = {
                'offer': offer,
                'products': products,
                'selected_product_ids': selected_product_ids_current,
                'valid_from': valid_from_str,
                'valid_to': valid_to_str,
            }
            return render(request, 'add_product_offer.html', context)
        else:
            offer.name = name
            offer.discount_percentage = discount_percentage
            offer.valid_from = valid_from
            offer.valid_to = valid_to
            offer.save()
            selected_products = Product.objects.filter(
                id__in=selected_product_ids,
                is_active=True,
                is_deleted=False
            )
            offer.products.set(selected_products)
            messages.success(request, f'Product offer "{name}" updated successfully with {selected_products.count()} products!')
            return redirect('offers_list')

    valid_from = offer.valid_from.date().strftime('%Y-%m-%d') if offer.valid_from else ''
    valid_to = offer.valid_to.date().strftime('%Y-%m-%d') if offer.valid_to else ''
    
    products = Product.objects.filter(is_active=True, is_deleted=False).order_by('name')
    selected_product_ids = [str(p.id) for p in offer.products.all()]
    
    context = {
        'offer': offer,
        'products': products,
        'selected_product_ids': selected_product_ids,
        'valid_from': valid_from,
        'valid_to': valid_to,
    }
    return render(request, 'add_product_offer.html', context)

@superuser_required
def edit_category_offer(request, offer_id):
    offer = get_object_or_404(CategoryOffer, id=offer_id, is_deleted=False)
    
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        discount_percentage_str = request.POST.get('discount_percentage')
        valid_from_str = request.POST.get('valid_from')
        valid_to_str = request.POST.get('valid_to')
        selected_category_ids = request.POST.getlist('categories')

        errors = []
        if not name:
            errors.append('Offer name is required.')
        if not discount_percentage_str:
            errors.append('Discount percentage is required.')
        else:
            try:
                discount_percentage = float(discount_percentage_str)
                if not 0 <= discount_percentage <= 100:
                    errors.append('Discount percentage must be between 0 and 100.')
            except ValueError:
                errors.append('Discount percentage must be a valid number.')
        
        if not valid_from_str or not valid_to_str:
            errors.append('Both valid from and valid to are required.')
        else:
            date_format = '%Y-%m-%d'
            try:
                valid_from_date = datetime.strptime(valid_from_str, date_format)
                valid_to_date = datetime.strptime(valid_to_str, date_format)
                valid_from = timezone.make_aware(valid_from_date)
                valid_to = timezone.make_aware(valid_to_date)
                if valid_to < valid_from:
                    errors.append("Valid 'to' must be after 'from'.")
            except ValueError:
                errors.append('Invalid date format (YYYY-MM-DD).')

        if len(selected_category_ids) == 0:
            errors.append('Select at least one category.')

        if errors:
            messages.error(request, '<br>'.join(errors))
            categories = Category.objects.filter(is_active=True, is_deleted=False).order_by('name')
            selected_category_ids_current = [str(c.id) for c in offer.categories.all()]
            context = {
                'offer': offer,
                'categories': categories,
                'selected_category_ids': selected_category_ids_current,
                'valid_from': valid_from_str,
                'valid_to': valid_to_str,
            }
            return render(request, 'add_category_offer.html', context)
        else:
            offer.name = name
            offer.discount_percentage = discount_percentage
            offer.valid_from = valid_from
            offer.valid_to = valid_to
            offer.save()
            selected_categories = Category.objects.filter(
                id__in=selected_category_ids,
                is_active=True,
                is_deleted=False
            )
            offer.categories.set(selected_categories)
            messages.success(request, f'Category offer "{name}" updated successfully with {selected_categories.count()} categories!')
            return redirect('offers_list')

    valid_from = offer.valid_from.date().strftime('%Y-%m-%d') if offer.valid_from else ''
    valid_to = offer.valid_to.date().strftime('%Y-%m-%d') if offer.valid_to else ''
    
    categories = Category.objects.filter(is_active=True, is_deleted=False).order_by('name')
    selected_category_ids = [str(c.id) for c in offer.categories.all()]
    
    context = {
        'offer': offer,
        'categories': categories,
        'selected_category_ids': selected_category_ids,
        'valid_from': valid_from,
        'valid_to': valid_to,
    }
    return render(request, 'add_category_offer.html', context)

@superuser_required
def delete_product_offer(request, offer_id):
    if request.method == 'POST':
        offer = get_object_or_404(ProductOffer, id=offer_id, is_deleted=False)
        offer.is_deleted = True
        offer.save()
        messages.success(request, f'Product offer "{offer.name}" deleted successfully.')
        return redirect('offers_list')
    return redirect('offers_list')

@superuser_required
def delete_category_offer(request, offer_id):
    if request.method == 'POST':
        offer = get_object_or_404(CategoryOffer, id=offer_id, is_deleted=False)
        offer.is_deleted = True
        offer.save()
        messages.success(request, f'Category offer "{offer.name}" deleted successfully.')
        return redirect('offers_list')
    return redirect('offers_list')

@superuser_required
def toggle_product_offer(request, offer_id):
    offer = get_object_or_404(ProductOffer, id=offer_id)
    offer.is_active = not offer.is_active
    offer.save()
    status = 'Enabled' if offer.is_active else 'Disabled'
    messages.success(request, f'Product offer has been {status} successfully.')
    return redirect('offers_list')

@superuser_required
def toggle_category_offer(request, offer_id):
    offer = get_object_or_404(CategoryOffer, id=offer_id)
    offer.is_active = not offer.is_active
    offer.save()
    status = 'Enabled' if offer.is_active else 'Disabled'
    messages.success(request, f'Category offer has been {status} successfully.')
    return redirect('offers_list')

# ----------------------Sales Report---------------------------------#


@superuser_required
def sales_report(request):
    errors = {}
    now = timezone.now()
    today = now.date()
    filter_type = request.GET.get('filter', 'month')
    from_date_str = request.GET.get('from_date')
    to_date_str = request.GET.get('to_date')

    start_date = None
    end_date = today

    if filter_type == 'today':
        start_date = today
        end_date = today
    elif filter_type == 'week':
        start_date = today - timedelta(days=7)
        end_date = today
    elif filter_type == 'month':
        start_date = today.replace(day=1)
        end_date = today
    elif filter_type == 'year':
        start_date = today.replace(month=1, day=1)
        end_date = today
    elif filter_type == 'custom':
        if from_date_str and to_date_str:
            try:
                start_date = datetime.strptime(from_date_str, '%Y-%m-%d').date()
                end_date = datetime.strptime(to_date_str, '%Y-%m-%d').date()
                if end_date < start_date:
                    errors['date'] = 'End date cannot be earlier than start date.'
            except ValueError:
                errors['date'] = 'Invalid date format. Use YYYY-MM-DD.'
        else:
            errors['date'] = 'Please provide both start and end dates for custom filter.'

    if errors:
        context = {
            'errors': errors,
            'filter_type': filter_type,
            'from_date': from_date_str,
            'to_date': to_date_str,
            'orders': [],
            'total_order_amount': Decimal('0.00'),
            'total_item_sales': Decimal('0.00'),
            'total_discount': Decimal('0.00'),
            'total_product_savings': Decimal('0.00'),
            'total_orders': 0,
            'total_qty': 0,
        }
        return render(request, 'sales_report.html', context)

    orders_queryset = Order.objects.filter(
        status='delivered',
        payment_status='paid',
        created_at__date__range=(start_date, end_date)
    ).order_by('-created_at')

    total_orders = orders_queryset.count()
    total_order_amount = orders_queryset.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    total_discount = orders_queryset.aggregate(discount=Sum('coupon_discount'))['discount'] or Decimal('0.00')

    order_items_qs = OrderItem.objects.filter(
        order__in=orders_queryset,
        status='active'  
    ).select_related('product')
    total_qty = order_items_qs.aggregate(qty=Sum('quantity'))['qty'] or 0
    total_item_sales = order_items_qs.annotate(
        total_price=ExpressionWrapper(F('quantity') * F('price'), output_field=DecimalField(max_digits=12, decimal_places=2))
    ).aggregate(sales=Sum('total_price'))['sales'] or Decimal('0.00')

    total_product_savings = Decimal('0.00')
    for item in order_items_qs:
        total_product_savings += item.product.get_savings() * item.quantity

    
    paginator = Paginator(orders_queryset, 8)  
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'orders': page_obj,  
        'total_order_amount': total_order_amount,
        'total_item_sales': total_item_sales,
        'total_discount': total_discount,
        'total_product_savings': total_product_savings,
        'total_orders': total_orders,
        'total_qty': total_qty,
        'filter_type': filter_type,
        'from_date': from_date_str if filter_type == 'custom' else (start_date.strftime('%Y-%m-%d') if start_date else ''),
        'to_date': to_date_str if filter_type == 'custom' else (end_date.strftime('%Y-%m-%d') if end_date else ''),
        'errors': errors,
    }

    return render(request, 'sales_report.html', context)


@superuser_required
def download_sales_report_csv(request):
    now = timezone.now()
    today = now.date()
    filter_type = request.GET.get('filter', 'month')
    from_date_str = request.GET.get('from_date')
    to_date_str = request.GET.get('to_date')

    start_date = None
    end_date = today

    if filter_type == 'today':
        start_date = today
        end_date = today
    elif filter_type == 'week':
        start_date = today - timedelta(days=7)
        end_date = today
    elif filter_type == 'month':
        start_date = today.replace(day=1)
        end_date = today
    elif filter_type == 'year':
        start_date = today.replace(month=1, day=1)
        end_date = today
    elif filter_type == 'custom' and from_date_str and to_date_str:
        try:
            start_date = datetime.strptime(from_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(to_date_str, '%Y-%m-%d').date()
        except ValueError:
            start_date = end_date = today  

    orders_queryset = Order.objects.filter(
        status='delivered',
        payment_status='paid',
        created_at__date__range=(start_date, end_date)
    ).order_by('-created_at')

    total_orders = orders_queryset.count()
    total_order_amount = orders_queryset.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    total_discount = orders_queryset.aggregate(discount=Sum('coupon_discount'))['discount'] or Decimal('0.00')
    order_items_qs = OrderItem.objects.filter(order__in=orders_queryset, status='active').select_related('product')
    total_qty = order_items_qs.aggregate(qty=Sum('quantity'))['qty'] or 0
    total_item_sales = order_items_qs.annotate(
        total_price=ExpressionWrapper(F('quantity') * F('price'), output_field=DecimalField(max_digits=12, decimal_places=2))
    ).aggregate(sales=Sum('total_price'))['sales'] or Decimal('0.00')

    total_product_savings = Decimal('0.00')
    for item in order_items_qs:
        total_product_savings += item.product.get_savings() * item.quantity

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="sales_report.csv"'

    writer = csv.writer(response)
    writer.writerow(['Sales Report'])
    writer.writerow(['Filter', filter_type])
    writer.writerow(['Date Range', f'{start_date} to {end_date}'])
    writer.writerow([])
    writer.writerow(['Summary'])
    writer.writerow(['Total Orders', total_orders])
    writer.writerow(['Total Quantity Sold', total_qty])
    writer.writerow(['Total Item Sales', f'Rs.{total_item_sales}'])
    writer.writerow(['Total Coupon Discount', f'Rs.{total_discount}'])
    writer.writerow(['Total Product Discount', f'Rs.{total_product_savings}'])
    writer.writerow(['Total Order Amount', f'Rs.{total_order_amount}'])
    writer.writerow([])
    writer.writerow(['Order ID', 'Date', 'User', 'Total Amount', 'Coupon Code', 'Coupon Discount'])

    for order in orders_queryset:
        writer.writerow([
            order.order_id,
            order.created_at.strftime('%Y-%m-%d'),
            order.user.username,
            f'Rs.{order.total_amount}',
            order.coupon_code or '-',
            f'Rs.{order.coupon_discount or Decimal("0.00")}'
        ])

    return response



#--------------------Admin Dashboard------------------------------#

@superuser_required
def admin_dashboard(request):
    filter_type = request.GET.get('filter', 'monthly')  
    today = timezone.now()

    if filter_type == 'daily':
        orders = Order.objects.annotate(period=TruncDay('created_at'))
    elif filter_type == 'yearly':
        orders = Order.objects.annotate(period=TruncYear('created_at'))
    else:   
        orders = Order.objects.annotate(period=TruncMonth('created_at'))

    orders = orders.filter(
        status__in=['delivered', 'confirmed'],
        payment_status='paid'
    )

    sales_data = orders.values('period').annotate(total=Sum('total_amount')).order_by('period')

    top_products = (
        OrderItem.objects.filter(
            order__status__in=['delivered', 'confirmed'],
            order__payment_status='paid'
        )
        .values('product__name', 'product__id')
        .annotate(total_sold=Sum('quantity'))
        .order_by('-total_sold')[:10]
    )

    
    top_categories = (
        OrderItem.objects.filter(
            order__status__in=['delivered', 'confirmed'],
            order__payment_status='paid'
        )
        .values('product__category__name', 'product__category__id')
        .annotate(total_sold=Sum('quantity'))
        .order_by('-total_sold')[:10]
    )

    
    top_brands = (
        OrderItem.objects.filter(
            order__status__in=['delivered', 'confirmed'],
            order__payment_status='paid'
        )
        .values('product__brand__name', 'product__brand__id')
        .annotate(total_sold=Sum('quantity'))
        .order_by('-total_sold')[:10]
    )

    context = {
        'sales_data': sales_data,
        'top_products': top_products,
        'top_categories': top_categories,
        'top_brands': top_brands,
        'filter_type': filter_type,
    }
    return render(request, 'admin_dashboard.html', context)


#---------------------Admin Wallet Management------------------------#

@superuser_required
def admin_wallet_list(request):
    transactions = WalletTransaction.objects.select_related('wallet__user', 'order').order_by('-created_at')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    if start_date:
        transactions = transactions.filter(created_at__date__gte=start_date)
    if end_date:
        transactions = transactions.filter(created_at__date__lte=end_date)
    
    paginator = Paginator(transactions, 8)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'admin_wallet_list.html', {
        'transactions': page_obj,
        'start_date': start_date,
        'end_date': end_date,
    })

@superuser_required
def admin_wallet_detail(request, transaction_id):
    transaction = get_object_or_404(WalletTransaction, transaction_id=transaction_id)
    user = transaction.wallet.user
    is_return_or_cancel = False
    if transaction.order:
        order_statuses = ['cancelled', 'returned']
        if transaction.transaction_type == 'credit' and transaction.order.status in order_statuses:
            is_return_or_cancel = True
    
    return render(request, 'admin_wallet_detail_view.html', {
        'transaction': transaction,
        'user': user,
        'is_return_or_cancel': is_return_or_cancel,
    })