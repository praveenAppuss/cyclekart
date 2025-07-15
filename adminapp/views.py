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
from adminapp.models import Product, Category, Brand, ProductColor, ProductImage,ProductSizeStock
import base64
import uuid
from django.core.files.base import ContentFile


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
    products = Product.objects.filter(is_deleted=False).prefetch_related('size_stocks', 'images')
    if query:
        products = products.filter(
            Q(name__icontains=query) | Q(category__name__icontains=query)
        )
    products = products.order_by('-created_at')
    for product in products:
        product.stock_summary = ', '.join([
            f"{stock.size}={stock.quantity}"
            for stock in product.size_stocks.all()
        ])
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
        name = request.POST.get('name', '').strip()
        category_id = request.POST.get('category')
        brand_id = request.POST.get('brand')
        description = request.POST.get('description', '').strip()
        color = request.POST.get('color')
        price = request.POST.get('price', '0.00')
        sizes = request.POST.getlist('sizes[]')
        stocks = request.POST.getlist('stocks[]')
        cropped_images = request.POST.getlist('cropped_images')

        old = {
            'name': name,
            'category': category_id,
            'brand': brand_id,
            'description': description,
            'color': color,
            'price': price,
            'stocks': stocks,
        }

        # Validation
        if Product.objects.filter(name__iexact=name).exists():
            errors['name'] = "Product with this name already exists."

        if not name:
            errors['name'] = "Product name is required."
        if not category_id:
            errors['category'] = "Please select a category."
        if not brand_id:
            errors['brand'] = "Please select a brand."
        if not color:
            errors['color'] = "Please select a color."
        if not sizes or not stocks:
            errors['stocks'] = "Please provide size and stock."
        if len(cropped_images) < 3:
            errors['images'] = "Please upload at least 3 cropped images."

        if errors:
            return render(request, 'product_form.html', {
                'categories': categories,
                'brands': brands,
                'colors': color_choices,
                'sizes': size_choices,
                'product': {},
                'errors': errors,
                'old': old
            })

        # Create product
        product = Product.objects.create(
            name=name,
            slug=slugify(name),
            category_id=category_id,
            brand_id=brand_id,
            price=price,
            description=description
        )

        # Save color
        ProductColor.objects.create(
            product=product,
            name=color,
            hex_code=color_hex_map.get(color, '#000000')
        )

        # Save size and stock
        for size, stock in zip(sizes, stocks):
            if size and stock:
                ProductSizeStock.objects.create(product=product, size=size, quantity=int(stock))

        # Save images
        for i, img_str in enumerate(cropped_images):
            try:
                format, img_data = img_str.split(';base64,')
                ext = format.split('/')[-1]
                file_name = f"{uuid.uuid4()}.{ext}"
                image_file = ContentFile(base64.b64decode(img_data), name=file_name)
                new_img = ProductImage.objects.create(product=product, image=image_file)

                if i == 0:
                    product.thumbnail = new_img.image
                    product.save()

            except Exception as e:
                print("Image saving error:", e)
                messages.warning(request, "Some images could not be saved.")

        messages.success(request, 'Product added successfully.')
        return redirect('product_list')

    return render(request, 'product_form.html', {
        'categories': categories,
        'brands': brands,
        'colors': color_choices,
        'sizes': size_choices,
        'product': {},
        'errors': {},
        'old': {}
    })




@superuser_required
@never_cache
def edit_product(request, product_id):
    product = get_object_or_404(Product, id=product_id, is_deleted=False)
    categories = Category.objects.filter(is_active=True, is_deleted=False)
    brands = Brand.objects.filter(is_active=True, is_deleted=False)
    color_choices = ['Red', 'Blue', 'Green', 'Black', 'White', 'Yellow']
    size_choices = ['S', 'M', 'L']
    existing_stocks = ProductSizeStock.objects.filter(product=product)
    existing_images = ProductImage.objects.filter(product=product)

    # ✅ Get the existing color (if any)
    existing_color = ''
    if product.colors.exists():
        existing_color = product.colors.first().name

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        category_id = request.POST.get('category')
        brand_id = request.POST.get('brand')
        description = request.POST.get('description', '').strip()
        color = request.POST.get('color')
        price = request.POST.get('price', '0.00')
        sizes = request.POST.getlist('sizes[]')
        stocks = request.POST.getlist('stocks[]')
        cropped_images = request.POST.getlist('cropped_images')

        if not name or not category_id or not brand_id or not color or not sizes or not stocks:
            messages.error(request, "Please fill all required fields.")
            return redirect('edit_product', product_id=product_id)

        product.name = name
        product.slug = slugify(name)
        product.category_id = category_id
        product.brand_id = brand_id
        product.description = description
        product.price = price
        product.save()

        # ✅ Update or create color (overwrite existing color if only one is allowed)
        ProductColor.objects.filter(product=product).delete()
        ProductColor.objects.create(product=product, name=color)

        # ✅ Replace old stock records
        ProductSizeStock.objects.filter(product=product).delete()
        for size, stock in zip(sizes, stocks):
            if size and stock:
                ProductSizeStock.objects.create(product=product, size=size, quantity=int(stock))

        # ✅ Only replace images if new ones were uploaded
        if cropped_images:
            ProductImage.objects.filter(product=product).delete()
            for i, img_str in enumerate(cropped_images):
                try:
                    format, img_data = img_str.split(';base64,')
                    ext = format.split('/')[-1]
                    file_name = f"{uuid.uuid4()}.{ext}"
                    image_file = ContentFile(base64.b64decode(img_data), name=file_name)
                    new_img = ProductImage.objects.create(product=product, image=image_file)
                    if i == 0:
                        product.thumbnail = new_img.image
                        product.save()
                except Exception as e:
                    print("Error saving cropped image:", e)
                    messages.warning(request, "Some images couldn't be saved.")

        messages.success(request, "Product updated successfully.")
        return redirect('product_list')

    return render(request, 'product_form.html', {
        'product': product,
        'categories': categories,
        'brands': brands,
        'colors': color_choices,
        'sizes': size_choices,
        'selected_color': existing_color,
        'existing_stocks': existing_stocks,
        'existing_images': existing_images,
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