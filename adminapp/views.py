from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login,logout
from django.views.decorators.cache import never_cache
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.views.decorators.http import require_POST
from django.db.models import Q,Sum
from django.core.paginator import Paginator
from userapp.services import WalletService
from userapp.models import CustomUser, Order, OrderItem, ReturnRequest, Wallet, WalletTransaction
from django.utils.text import slugify
from adminapp.models import Product, Category, Brand, ProductColorVariant, ProductImage,ProductSizeStock
import base64
import uuid
from django.core.files.base import ContentFile
import logging
from django.db import transaction
from django.http import HttpResponseBadRequest, HttpResponseServerError
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
            variant_id = next((v.id for v in color_variants if v.name == color), None)
            existing_count = len(existing_images.get(variant_id, [])) if variant_id else 0
            new_images = [img for img in cropped_images if img and i * 3 <= cropped_images.index(img) < (i + 1) * 3]
            variant_image_counts[color] = len(new_images) if new_images else existing_count
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

                
                ProductColorVariant.objects.filter(product=product).delete()
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

                    
                    new_images = variant_image_map.get(color, [])
                    if new_images:
                        ProductImage.objects.filter(color_variant=color_variant).delete()
                        for img_str in new_images:
                            try:
                                format, img_data = img_str.split(';base64,')
                                ext = format.split('/')[-1]
                                file_name = f"{uuid.uuid4()}.{ext}"
                                image_file = ContentFile(base64.b64decode(img_data), name=file_name)
                                new_img = ProductImage.objects.create(color_variant=color_variant, image=image_file)
                                if i == 0 and not product.thumbnail:
                                    product.thumbnail = new_img.image
                                    product.save()
                            except Exception as e:
                                logger.error(f"Image saving error for variant {color}: {str(e)}")
                                raise
                    else:
                        
                        existing_imgs = existing_images.get(next((v.id for v in color_variants if v.name == color), None), [])
                        for img in existing_imgs:
                            ProductImage.objects.create(
                                color_variant=color_variant,
                                image=img.image
                            )
                        if existing_imgs and i == 0 and not product.thumbnail:
                            product.thumbnail = existing_imgs[0].image
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
        return redirect('adminapp:admin_order_detail', order_id=order.id)

    if order.status == 'cancelled':
        logger.warning(f"Attempted to update status of cancelled order {order.order_id}")
        messages.error(request, "Cannot update status of a cancelled order.")
        return redirect('admin_order_detail', order_id=order.id)

    if new_status != order.status:
        with transaction.atomic():
            order.status = new_status
            if new_status == 'delivered':
                order.delivered_at = timezone.now()
                if order.payment_status == 'pending':  
                    order.payment_status = 'paid'
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
                        order.payment_status = 'pending'  
                        logger.info(f"Refunded ₹{refund_amount} for cancelled order {order.order_id}")
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
                        order.payment_status = 'pending'  
                        logger.info(f"Refunded ₹{refund_amount} for returned order {order.order_id}")
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
            item.save()

            if order.payment_status == 'paid':
                item_price = (item.discount_price or item.price) * item.quantity
                total_items_price = sum(
                    (oi.discount_price or oi.price) * oi.quantity
                    for oi in order.items.all()
                )

                tax_amount = Decimal('0.00')
                if order.tax and total_items_price > 0:
                    tax_amount = (item_price / total_items_price) * order.tax

                shipping_amount = Decimal('0.00')
                if order.shipping_cost:
                    if not order.items.exclude(status='return_accepted').exists():
                        shipping_amount = order.shipping_cost

                refund_amount = item_price + tax_amount + shipping_amount                
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

            if not order.items.filter(status__in=['active', 'return_requested']).exists():
                order.status = 'returned'
                order.returned_at = timezone.now()
                order.payment_status = 'pending'  
                order.save()
                logger.info(f"Order {order.order_id} status updated to 'returned'")

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