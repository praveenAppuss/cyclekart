from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login,logout
from django.views.decorators.cache import never_cache
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.views.decorators.http import require_POST
from django.db.models import Q,Sum
from django.core.paginator import Paginator
from userapp.models import CustomUser
from django.utils.text import slugify
from adminapp.models import Product, Category, Brand, ProductColorVariant, ProductImage,ProductSizeStock
import base64
import uuid
from django.core.files.base import ContentFile
import logging
from django.db import transaction
from django.http import HttpResponseServerError

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


#  Admin Dashboard View 
@superuser_required
@never_cache
def admin_dashboard(request):
    return render(request, 'admin_dashboard.html')



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






logger = logging.getLogger(__name__)

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

        # Variant inputs (multiple variants)
        colors = request.POST.getlist('colors[]')
        sizes = request.POST.getlist('sizes[]')
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

        # Validation
        logger.debug(f"Validation: name={name}, category_id={category_id}, colors={colors}, images={len(cropped_images)}")
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
        if len(sizes) != len(stocks) or len(sizes) % len(size_choices) != 0:
            errors['stocks'] = "Size and stock data are inconsistent with the number of variants."
        if len(cropped_images) < 3 * len(colors):  # At least 3 images per variant
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
                'zipped_stocks': list(zip(size_choices, [''] * len(size_choices))),
                'existing_images': [],
            })

        # Create Product within transaction
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

                # Process each variant
                image_index = 0
                size_stock_index = 0
                variants_per_size = len(sizes) // len(size_choices)  # Number of variants

                for i, color in enumerate(colors):
                    color_variant = ProductColorVariant.objects.create(
                        product=product,
                        name=color,
                        hex_code=color_hex_map.get(color, '#000000')
                    )

                    # Associate sizes and stocks for this variant
                    start_idx = i * len(size_choices)
                    end_idx = start_idx + len(size_choices)
                    variant_sizes = sizes[start_idx:end_idx] if start_idx < len(sizes) else []
                    variant_stocks = stocks[start_idx:end_idx] if start_idx < len(stocks) else []

                    for size, stock in zip(variant_sizes, variant_stocks):
                        if size and stock:
                            ProductSizeStock.objects.create(
                                color_variant=color_variant,
                                size=size,
                                quantity=int(stock)
                            )

                    # Associate images for this variant
                    image_count = min(3, len(cropped_images) - image_index)  # Ensure we don't exceed available images
                    for _ in range(image_count):
                        if image_index < len(cropped_images):
                            img_str = cropped_images[image_index]
                            try:
                                format, img_data = img_str.split(';base64,')
                                ext = format.split('/')[-1]
                                file_name = f"{uuid.uuid4()}.{ext}"
                                image_file = ContentFile(base64.b64decode(img_data), name=file_name)
                                new_img = ProductImage.objects.create(color_variant=color_variant, image=image_file)
                                if i == 0 and _ == 0:  # First image of first variant as thumbnail
                                    product.thumbnail = new_img.image
                                    product.save()
                            except Exception as e:
                                logger.error(f"Image saving error for variant {color}, image {_}: {str(e)}")
                                raise
                        image_index += 1

            logger.info(f"Product {name} created successfully")
            messages.success(request, 'Product added successfully.')
            print(f"Redirecting to product_list for product {name}")
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
                'zipped_stocks': list(zip(size_choices, [''] * len(size_choices))),
                'existing_images': [],
            })

    return render(request, 'product_form.html', {
        'categories': categories,
        'brands': brands,
        'colors': color_choices,
        'sizes': size_choices,
        'errors': {},
        'old': {},
        'zipped_stocks': list(zip(size_choices, [''] * len(size_choices))),
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

    color_variant = product.color_variants.first()  # Assuming single variant
    existing_images = ProductImage.objects.filter(color_variant=color_variant) if color_variant else []
    existing_color = color_variant.name if color_variant else ''
    stock_map = {stock.size: stock.quantity for stock in color_variant.size_stocks.all()} if color_variant else {}
    zipped_stocks = [(size, stock_map.get(size, '')) for size in size_choices]

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        category_id = request.POST.get('category')
        brand_id = request.POST.get('brand')
        description = request.POST.get('description', '').strip()
        color = request.POST.get('color')
        price = request.POST.get('price', '0.00')
        discount_price = request.POST.get('discount_price', None)
        sizes = request.POST.getlist('sizes[]')
        stocks = request.POST.getlist('stocks[]')
        cropped_images = request.POST.getlist('cropped_images[]')

        product.name = name
        product.slug = slugify(name)
        product.category_id = category_id
        product.brand_id = brand_id
        product.description = description
        product.price = price
        product.discount_price = discount_price
        product.save()

        # Update or create color variant
        if color_variant:
            color_variant.name = color
            color_variant.save()
        else:
            color_variant = ProductColorVariant.objects.create(product=product, name=color)

        # Update size stocks
        ProductSizeStock.objects.filter(color_variant=color_variant).delete()
        for size, stock in zip(sizes, stocks):
            if size and stock:
                ProductSizeStock.objects.create(color_variant=color_variant, size=size, quantity=int(stock))

        # Replace images if new ones uploaded
        if cropped_images:
            ProductImage.objects.filter(color_variant=color_variant).delete()
            for i, img_str in enumerate(cropped_images):
                try:
                    format, img_data = img_str.split(';base64,')
                    ext = format.split('/')[-1]
                    file_name = f"{uuid.uuid4()}.{ext}"
                    image_file = ContentFile(base64.b64decode(img_data), name=file_name)
                    new_img = ProductImage.objects.create(color_variant=color_variant, image=image_file)
                    if i == 0:
                        product.thumbnail = new_img.image
                        product.save()
                except Exception as e:
                    messages.error(request, f"Image saving error: {str(e)}")
                    raise  # Rollback transaction on error

        messages.success(request, "Product updated successfully.")
        return redirect('product_list')

    return render(request, 'product_form.html', {
        'product': product,
        'categories': categories,
        'brands': brands,
        'colors': color_choices,
        'sizes': size_choices,
        'selected_color': existing_color,
        'zipped_stocks': zipped_stocks,
        'existing_images': existing_images,
        'errors': {},
        'old': {
            'name': product.name,
            'category': str(product.category_id),
            'brand': str(product.brand_id),
            'description': product.description,
            'color': existing_color,
            'price': product.price,
            'discount_price': product.discount_price,
            'stocks': [stock_map.get(size, '') for size in size_choices],
        }
    })


@superuser_required
@never_cache
def delete_product(request, product_id):
    product = get_object_or_404(Product, id=product_id, is_deleted=False)
    product.is_deleted = True
    product.save()
    messages.success(request, 'Product deleted successfully.')
    return redirect('product_list')


@superuser_required
@never_cache
def toggle_product_status(request, product_id):
    product = get_object_or_404(Product, id=product_id, is_deleted=False)
    product.is_active = not product.is_active
    product.save()
    status = "listed" if product.is_active else "unlisted"
    messages.success(request, f"Product has been {status}.")
    return redirect('product_list') 