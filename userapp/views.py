from decimal import Decimal
import uuid
from django.shortcuts import render, redirect
from django.contrib.auth import get_user_model, authenticate, login, logout
from django.contrib.auth.hashers import make_password
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.conf import settings
from django.db import transaction, IntegrityError
from django.contrib.auth import BACKEND_SESSION_KEY
import random
from django.db.models.functions import Coalesce
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.contrib.messages import get_messages
from django.contrib import messages
from adminapp.models import Product,Category,Brand,ProductSizeStock,ProductColorVariant
from userapp.models import CustomUser,Address,Cart,CartItem,Wishlist,Order,OrderItem
import re
from django.views.decorators.cache import never_cache
from .utils import no_cache_view,calculate_cart_total
from django.http import HttpResponse, JsonResponse
from django.template.loader import get_template
from xhtml2pdf import pisa
from django.db.models import Q, F, FloatField, ExpressionWrapper, Case, When, Value, IntegerField,Min,Max
from .forms import AddressForm
import json
from django.db.models import Exists, OuterRef
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_POST
User = get_user_model()

@no_cache_view
@never_cache
def user_signup(request):
    if request.user.is_authenticated:
        return redirect('user_home')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        mobile = request.POST.get('mobile', '').strip()
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')
        errors = {}

        # Basic validations
        if not username:
            errors['username'] = "Username is required."
        elif len(username) < 4:
            errors['username'] = "Username must be at least 3 characters long."

        if not email:
            errors['email'] = "Email is required."
        elif not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            errors['email'] = "Enter a valid email address."
        elif CustomUser.objects.filter(email=email).exists():
            errors['email'] = "Email already exists."

        if not mobile:
            errors['mobile'] = "Mobile number is required."
        elif not re.match(r"^\d{10}$", mobile):
            errors['mobile'] = "Enter a valid 10-digit mobile number."

        if not password:
            errors['password'] = "Password is required."
        elif len(password) < 6:
            errors['password'] = "Password must be at least 6 characters long."

        if password != confirm_password:
            errors['confirm_password'] = "Passwords do not match."

        if errors:
            return render(request, 'user_signup.html', {
                'errors': errors,
                'username': username,
                'email': email,
                'mobile': mobile,
            })

        # Send OTP and store session
        otp = str(random.randint(100000, 999999))
        request.session['otp'] = otp
        request.session['signup_data'] = {
            'username': username,
            'email': email,
            'mobile': mobile,
            'password': make_password(password)
        }
        print(otp)

        send_mail(
            subject='CycleKart - Email Verification',
            message=f'Your OTP is: {otp}',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
        return redirect('verify_otp')

    return render(request, 'user_signup.html')



@no_cache_view
@never_cache
def verify_otp(request):
    if request.user.is_authenticated:
        return redirect('user_home')

    if request.method == 'POST':
        entered_otp = request.POST.get('otp')
        session_otp = request.session.get('otp')
        signup_data = request.session.get('signup_data')

        if entered_otp == session_otp and signup_data:
            email = signup_data['email']
            username = signup_data['username']
            mobile = signup_data['mobile']
            password = signup_data['password']

            user = CustomUser.objects.filter(email=email).first()

            if user:
                
                if user.mobile and user.mobile != mobile:
                    return render(request, 'verify_otp.html', {
                        'error': 'This email is already linked to a different mobile number.'
                    })
                if not user.mobile:
                    user.mobile = mobile
                if not user.username:
                    user.username = username
                if not user.password:
                    user.password = password
            else:
                
                user = CustomUser(
                    email=email,
                    username=username,
                    mobile=mobile,
                    password=password
                )

            user.is_active = True
            try:
                user.save()
            except Exception as e:
                return render(request, 'verify_otp.html', {
                    'error': 'Something went wrong while saving your account. Please try again.'
                })

            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            request.session.pop('otp', None)
            request.session.pop('signup_data', None)

            return redirect('user_home')
        return render(request, 'verify_otp.html', {'error': 'Invalid OTP'})
    return render(request, 'verify_otp.html')

@no_cache_view
@never_cache
def user_login(request):
    if request.user.is_authenticated:
        return redirect('user_home')

    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        errors = {}

        if not email:
            errors['email'] = "Email is required."
        elif not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            errors['email'] = "Enter a valid email address."

        if not password:
            errors['password'] = "Password is required."

        if errors:
            return render(request, 'user_login.html', {'errors': errors})

        try:
            user = CustomUser.objects.get(email=email)
        except CustomUser.DoesNotExist:
            errors['email'] = "Email not found."
            return render(request, 'user_login.html', {'errors': errors})

        if not user.check_password(password):
            errors['password'] = "Incorrect password."
            return render(request, 'user_login.html', {'errors': errors})

        if user.is_blocked:
            messages.error(request, "Your account is currently suspended.")
        else:
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            request.session.set_expiry(300)
            return redirect('user_home')

    return render(request, 'user_login.html')



def resend_otp(request):
    signup_data = request.session.get('signup_data')
    if not signup_data:
        return redirect('user_signup')
    otp = str(random.randint(100000, 999999))
    request.session['otp'] = otp
    send_mail(
        subject='CycleKart - Resend OTP',
        message=f'Your new OTP is: {otp}',
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[signup_data['email']],
        fail_silently=False,
    )
    return redirect('verify_otp')


def user_logout(request):
    logout(request)
    return redirect('user_login')


@login_required(login_url='user_login')
def user_home(request):
    all_products = list(Product.objects.filter(is_active=True, is_deleted=False))
    featured_products = random.sample(all_products, min(len(all_products), 4))  
    return render(request, 'user_home.html', {'featured_products': featured_products})


@login_required(login_url='user_login')
def user_product_list(request):
    # Base queryset: exclude blocked/unlisted products
    products = Product.objects.filter(is_deleted=False, is_active=True).prefetch_related('color_variants', 'color_variants__size_stocks')

    # Get min and max prices for dynamic range
    price_range = products.aggregate(
        min_price=Min(Coalesce(F('discount_price'), F('price'))),
        max_price=Max(Coalesce(F('discount_price'), F('price')))
    )
    min_price = price_range['min_price'] or 0
    max_price = price_range['max_price'] or 10000

    # Check stock availability for each product
    products = products.annotate(
        has_stock=ExpressionWrapper(
            Case(
                When(color_variants__size_stocks__quantity__gt=0, then=Value(1)),
                default=Value(0),
                output_field=IntegerField()
            ),
            output_field=IntegerField()
        )
    ).filter(has_stock=1).distinct()

    # Search
    query = request.GET.get('search', '').strip()
    if query:
        products = products.filter(
            Q(name__icontains=query) | Q(description__icontains=query)
        ).distinct()

    # Filters
    category_ids = request.GET.getlist('category')
    brand_id = request.GET.get('brand')
    size_list = request.GET.getlist('size')
    color_list = request.GET.getlist('color')
    price_min = request.GET.get('price_min', min_price)
    price_max = request.GET.get('price_max', max_price)

    try:
        price_min = float(price_min) if price_min else min_price
        price_max = float(price_max) if price_max else max_price
    except ValueError:
        price_min, price_max = min_price, max_price

    if category_ids:
        products = products.filter(category__id__in=category_ids).distinct()
    if brand_id:
        products = products.filter(brand__id=brand_id).distinct()
    if size_list:
        products = products.filter(color_variants__size_stocks__size__in=size_list).distinct()
    if color_list:
        products = products.filter(color_variants__name__in=color_list).distinct()

    products = products.annotate(
        display_price=Coalesce(F('discount_price'), F('price'), output_field=FloatField())
    ).filter(display_price__gte=price_min, display_price__lte=price_max).distinct()

    # Sort
    sort_by = request.GET.get('sort', 'name_asc')
    sort_mapping = {
        'price_asc': 'display_price',
        'price_desc': '-display_price',
        'name_asc': 'name',
        'name_desc': '-name',
    }
    products = products.order_by(sort_mapping.get(sort_by, 'name')).distinct()

    # Pagination
    paginator = Paginator(products, 8)  # 8 products per page
    page_number = request.GET.get('page')
    products_page = paginator.get_page(page_number)

    # Clear filters (redirect to base URL)
    if 'clear' in request.GET:
        return redirect('userproduct_list')

    context = {
        'products': products_page,
        'categories': Category.objects.filter(is_deleted=False, is_active=True),
        'brands': Brand.objects.filter(is_deleted=False, is_active=True),
        'colors': ['Red', 'Blue', 'Green', 'Black', 'White', 'Yellow'],
        'sizes': ['S', 'M', 'L'],
        'query': query,
        'selected_categories': category_ids,
        'selected_brand': brand_id,
        'selected_sizes': size_list,
        'selected_colors': color_list,
        'price_min': price_min,
        'price_max': price_max,
        'sort_by': sort_by,
        'min_price': min_price,
        'max_price': max_price,
    }
    return render(request, 'user_product_list.html', context)



@login_required(login_url='user_login')
def product_detail(request, product_id):
    product = get_object_or_404(Product, id=product_id, is_deleted=False, is_active=True)
    
    color_variants = product.color_variants.prefetch_related('size_stocks', 'images').annotate(
        has_stock=Exists(ProductSizeStock.objects.filter(
            color_variant=OuterRef('pk'),
            quantity__gt=0
        ))
    ).all()

    if not color_variants.exists() or not any(variant.has_stock for variant in color_variants):
        messages.error(request, 'This product is currently unavailable.')
        return redirect('userproduct_list')

    savings = 0
    if product.discount_price and product.discount_price < product.price:
        savings = product.price - product.discount_price

    related_products = Product.objects.filter(
        category=product.category,
        is_active=True,
        is_deleted=False
    ).exclude(id=product_id).distinct()[:4]

    for variant in color_variants:
        variant.size_stocks_data = [
            {
                'id': stock.id,  # Added to match template's size_stock_id
                'size': stock.size,
                'quantity': stock.quantity,
                'display': stock.size  
            }
            for stock in variant.size_stocks.all()
        ]

    wishlist_items = Wishlist.objects.filter(user=request.user, color_variant__product=product) if request.user.is_authenticated else []

    context = {
        'product': product,
        'color_variants': color_variants,
        'related_products': related_products,
        'savings': savings,
        'wishlist_items': wishlist_items,
    }
    
    return render(request, 'product_detail.html', context)


# user profile section ---------------------------------------------------

@login_required
def profile_view(request):
    user = request.user
    user_addresses = Address.objects.filter(user=user)  # Only current user
    default_address = user_addresses.filter(is_default=True).first()

    return render(request, 'profile.html', {
        'user': user,
        'user_addresses': user_addresses,
        'default_address': default_address,
    })



@login_required
def upload_profile_image(request):
    if request.method == 'POST' and request.FILES.get('profile_image'):
        request.user.profile_image = request.FILES['profile_image']
        request.user.save()
    return redirect('profile')


@login_required
def update_profile(request):
    if request.method == 'POST':
        user = request.user
        user.username = request.POST.get('username', user.username)
        user.email = request.POST.get('email', user.email)
        user.mobile = request.POST.get('mobile', user.mobile)
        user.save()
        selected_address_id = request.POST.get('selected_user')
        if selected_address_id:
            try:
                # Reset current default
                Address.objects.filter(user=user, is_default=True).update(is_default=False)
                # Set new default
                address = Address.objects.get(id=selected_address_id, user=user)
                address.is_default = True
                address.save()
            except Address.DoesNotExist:
                pass  # silently ignore if someone messes with the form
        messages.success(request, "Profile updated successfully.")
        return redirect('profile')
    return redirect('profile')

    

# Address management section---------------------------------

@login_required
def address_list(request):
    addresses = Address.objects.filter(user=request.user)
    form = AddressForm()

    # Send data to frontend for JS auto-fill
    address_json_map = {
        str(a.id): {
            'full_name': a.full_name,
            'mobile': a.mobile,
            'address_line': a.address_line,
            'district': a.district,
            'state': a.state,
            'pin_code': a.pin_code,
            'country': a.country,
        }
        for a in addresses
    }

    context = {
        'addresses': addresses,
        'form': form,
        'address_json_map': mark_safe(json.dumps(address_json_map))
    }
    return render(request, 'address_page.html', context)



@login_required
def add_address(request):
    if request.method == 'POST':
        form = AddressForm(request.POST)
        if form.is_valid():
            address = form.save(commit=False)
            address.user = request.user
            address.save()
            return redirect('address_list')  
    return redirect('address_list')

@login_required
def update_address(request, pk):
    address = get_object_or_404(Address, pk=pk, user=request.user)
    if request.method == 'POST':
        form = AddressForm(request.POST, instance=address)
        if form.is_valid():
            form.save()
            return redirect('address_list')
    return redirect('address_list')

@login_required
def delete_address(request, pk):
    address = get_object_or_404(Address, pk=pk, user=request.user)
    address.delete()
    return redirect('address_list')




# Cart Management
@login_required(login_url='user_login')
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    if not product.is_active or product.is_deleted or not product.category.is_active or product.category.is_deleted:
        messages.error(request, "This product is unavailable.")
        return redirect('product_detail', product_id=product.id)

    color_variant_id = request.POST.get('color_variant')
    size_stock_id = request.POST.get('size_stock')
    quantity = request.POST.get('quantity', 1)

    try:
        quantity = int(quantity)
    except (ValueError, TypeError):
        messages.error(request, "Invalid quantity provided.")
        return redirect('product_detail', product_id=product.id)

    if not color_variant_id or not size_stock_id:
        messages.error(request, "Please select both a color and size.")
        return redirect('product_detail', product_id=product.id)

    try:
        color_variant = ProductColorVariant.objects.get(id=color_variant_id, product=product)
    except ProductColorVariant.DoesNotExist:
        messages.error(request, "Invalid color selected.")
        return redirect('product_detail', product_id=product.id)

    try:
        size_stock = ProductSizeStock.objects.get(id=size_stock_id, color_variant=color_variant)
    except ProductSizeStock.DoesNotExist:
        messages.error(request, "Invalid size or color combination selected.")
        return redirect('product_detail', product_id=product.id)

    if size_stock.quantity < 1:
        messages.warning(request, f"Size {size_stock.get_size_display()} in color {color_variant.name} is out of stock.")
        return redirect('product_detail', product_id=product.id)

    max_quantity = min(size_stock.quantity, 5)
    if quantity < 1 or quantity > max_quantity:
        messages.warning(request, f"Quantity must be between 1 and {max_quantity}.")
        return redirect('product_detail', product_id=product.id)

    cart, _ = Cart.objects.get_or_create(user=request.user)

    cart_item, created = CartItem.objects.get_or_create(
        cart=cart,
        product=product,
        color_variant=color_variant,
        size_stock=size_stock,
        defaults={'quantity': quantity}
    )

    if not created:
        new_quantity = cart_item.quantity + quantity
        if new_quantity > max_quantity:
            messages.warning(request, f"Cannot add more. Max limit is {max_quantity} for {color_variant.name} {size_stock.get_size_display()}.")
        else:
            cart_item.quantity = new_quantity
            cart_item.save()
            messages.success(request, f"{product.name} ({color_variant.name}, {size_stock.get_size_display()}) quantity updated in cart.")
    else:
        cart_item.quantity = quantity
        cart_item.save()
        messages.success(request, f"{product.name} ({color_variant.name}, {size_stock.get_size_display()}) added to cart.")

    Wishlist.objects.filter(
        user=request.user,
        color_variant__product=product,
        color_variant__name=color_variant.name
    ).delete()

    return redirect('cart_view')

def get_sizes(request, color_variant_id):
    size_stocks = ProductSizeStock.objects.filter(color_variant_id=color_variant_id).values('id', 'size')
    sizes = [{'id': ss['id'], 'size_display': dict(ProductSizeStock.SIZE_CHOICES).get(ss['size'], ss['size'])} for ss in size_stocks]
    return JsonResponse({'sizes': sizes})


@login_required(login_url='user_login')
def cart_view(request):
    cart = Cart.objects.filter(user=request.user).first()
    cart_items = cart.items.select_related('product', 'color_variant', 'size_stock').prefetch_related(
        'product__color_variants__images',
        'product__color_variants__size_stocks'
    ).all() if cart else []

    total_subtotal = Decimal('0')
    total_discount = Decimal('0')
    has_unavailable_items = False
    taxes = Decimal('0')
    TAX_RATE = Decimal('0.05')  # Configurable tax rate

    for item in cart_items:
        # Calculate subtotal (use discount_price if available)
        item_price = item.product.discount_price if item.product.discount_price and item.product.discount_price < item.product.price else item.product.price
        item.subtotal = item.quantity * item_price
        total_subtotal += item.subtotal

        # Get product image and color variant
        item.color_variant = item.color_variant  # Already fetched via select_related
        item.image = item.color_variant.images.first().image.url if item.color_variant.images.exists() else item.product.thumbnail.url if item.product.thumbnail else ''
        
        # Check stock and availability
        item.size_stock = item.size_stock  # Already fetched via select_related
        item.stock = item.size_stock.quantity
        item.max_quantity = min(item.stock, 5)  # Max 5 items
        item.size_display = item.size_stock.get_size_display()  # Use get_size_display for size label

        # Check if item is unavailable (out of stock, product/category blocked or deleted)
        if (item.product.is_deleted or not item.product.is_active or 
            item.product.category.is_deleted or not item.product.category.is_active or 
            item.quantity > item.stock):
            has_unavailable_items = True
            item.is_available = False
        else:
            item.is_available = True

        # Calculate savings (discount) for each item
        if item.product.discount_price and item.product.discount_price < item.product.price:
            item_savings = item.product.price - item.product.discount_price
            item.savings = item_savings * item.quantity
            total_discount += item.savings
        else:
            item.savings = Decimal('0')

    # Calculate taxes (5% of subtotal)
    taxes = total_subtotal * TAX_RATE
    # Calculate final total (subtotal + taxes - total_discount)
    final_total = total_subtotal + taxes - total_discount

    return render(request, 'cart.html', {
        'cart_items': cart_items,
        'cart_total': total_subtotal,
        'total_discount': total_discount,
        'taxes': taxes,
        'total': final_total,
        'has_unavailable_items': has_unavailable_items,
    })



@login_required(login_url='user_login')
def update_cart_quantity(request, cart_item_id):
    cart_item = get_object_or_404(CartItem, id=cart_item_id, cart__user=request.user)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        try:
            stock_entry = cart_item.size_stock
            max_quantity = min(stock_entry.quantity, 5)
        except ProductSizeStock.DoesNotExist:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': 'Selected size stock not found.'}, status=400)
            messages.error(request, "Selected size stock not found.")
            return redirect('cart_view')

        new_quantity = cart_item.quantity
        if action == 'increment' and cart_item.quantity < max_quantity:
            new_quantity = cart_item.quantity + 1
            messages.success(request, f"Quantity updated for {cart_item.product.name} ({cart_item.color_variant.name}, {stock_entry.get_size_display()}).")
        elif action == 'decrement' and cart_item.quantity > 1:
            new_quantity = cart_item.quantity - 1
            messages.success(request, f"Quantity updated for {cart_item.product.name} ({cart_item.color_variant.name}, {stock_entry.get_size_display()}).")
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': f"Cannot update quantity. Max limit: {max_quantity} or minimum reached."}, status=400)
            messages.warning(request, f"Cannot update quantity. Max limit: {max_quantity} or minimum reached.")
            return redirect('cart_view')

        cart_item.quantity = new_quantity
        cart_item.save()

        item_price = cart_item.product.discount_price if cart_item.product.discount_price and cart_item.product.discount_price < cart_item.product.price else cart_item.product.price
        subtotal = new_quantity * item_price

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            storage = get_messages(request)
            message = storage._queued_messages[-1].message if storage._queued_messages else ''
            return JsonResponse({
                'success': True,
                'quantity': new_quantity,
                'subtotal': float(subtotal),
                'message': message
            })
        return redirect('cart_view')
    

@login_required(login_url='user_login')
def remove_from_cart(request, cart_item_id):
    cart_item = get_object_or_404(CartItem, id=cart_item_id, cart__user=request.user)
    product_name = cart_item.product.name
    color_name = cart_item.color_variant.name
    size_display = cart_item.size_stock.get_size_display()
    cart_item.delete()
    messages.success(request, f"{product_name} ({color_name}, {size_display}) removed from cart.")
    return redirect('cart_view')


# Wishlist Management
@login_required(login_url='user_login')
def wishlist_view(request):
    wishlist_items = Wishlist.objects.filter(user=request.user).select_related('color_variant__product')
    size_map = {}
    for item in wishlist_items:
        sizes = ProductSizeStock.objects.filter(
            color_variant=item.color_variant, quantity__gt=0
        ).values('id', 'size', 'quantity')
        size_map[item.color_variant.id] = [
            {'id': s['id'], 'size': s['size'], 'display': s['size']}  # Use raw size for display
            for s in sizes
        ]

    return render(request, 'wishlist.html', {
        'wishlist_items': wishlist_items,
        'sizes': size_map,
    })


@login_required(login_url='user_login')
def add_to_wishlist(request, color_variant_id):
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    color_variant = get_object_or_404(ProductColorVariant, id=color_variant_id, product__is_active=True, product__is_deleted=False)

    # Check product/category availability
    if not color_variant.product.category.is_active or color_variant.product.category.is_deleted:
        if is_ajax:
            return JsonResponse({'success': False, 'message': 'This product is unavailable.'}, status=400)
        messages.error(request, 'This product is unavailable.')
        return redirect('product_detail', product_id=color_variant.product.id)

    # Toggle wishlist item
    wishlist_item = Wishlist.objects.filter(user=request.user, color_variant=color_variant).first()
    if wishlist_item:
        # Item exists, remove it
        wishlist_item.delete()
        message = f"{color_variant.product.name} ({color_variant.name}) removed from wishlist."
        if is_ajax:
            return JsonResponse({'success': True, 'added': False, 'message': message})
        messages.success(request, message)
    else:
        # Add new item
        Wishlist.objects.create(user=request.user, color_variant=color_variant)
        message = f"{color_variant.product.name} ({color_variant.name}) added to wishlist."
        if is_ajax:
            return JsonResponse({'success': True, 'added': True, 'message': message})
        messages.success(request, message)

    return redirect('product_detail', product_id=color_variant.product.id)



@login_required(login_url='user_login')
def remove_from_wishlist(request, wishlist_id):
    item = get_object_or_404(Wishlist, id=wishlist_id, user=request.user)
    product_name = item.color_variant.product.name
    color_name = item.color_variant.name
    item.delete()
    messages.success(request, f"{product_name} ({color_name}) removed from wishlist.")
    return redirect('wishlist')

@login_required(login_url='user_login')
def add_to_cart_from_wishlist(request):
    if request.method == 'POST':
        color_variant_id = request.POST.get('color_variant_id')
        size_stock_id = request.POST.get('size_stock_id')
        quantity = request.POST.get('quantity', 1)

        try:
            quantity = int(quantity)
        except (ValueError, TypeError):
            messages.error(request, "Invalid quantity provided.")
            return redirect('wishlist')

        if not size_stock_id:
            messages.error(request, "Please select a size.")
            return redirect('wishlist')

        color_variant = get_object_or_404(ProductColorVariant, id=color_variant_id, product__is_active=True, product__is_deleted=False)
        product = color_variant.product

        if not product.category.is_active or product.category.is_deleted:
            messages.error(request, "This product is unavailable.")
            return redirect('wishlist')

        try:
            stock_entry = ProductSizeStock.objects.get(id=size_stock_id, color_variant=color_variant)
        except ProductSizeStock.DoesNotExist:
            messages.error(request, "Invalid size or color combination selected.")
            return redirect('wishlist')

        if stock_entry.quantity < 1:
            messages.warning(request, f"Size {stock_entry.size} in color {color_variant.name} is out of stock.")
            return redirect('wishlist')

        max_quantity = min(stock_entry.quantity, 5)
        if quantity < 1 or quantity > max_quantity:
            messages.warning(request, f"Quantity must be between 1 and {max_quantity}.")
            return redirect('wishlist')

        cart, _ = Cart.objects.get_or_create(user=request.user)
        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            product=product,
            color_variant=color_variant,
            size_stock=stock_entry,
            defaults={'quantity': quantity}
        )

        if not created:
            new_quantity = cart_item.quantity + quantity
            if new_quantity > max_quantity:
                messages.warning(request, f"Cannot add more. Max limit is {max_quantity} for {color_variant.name} {stock_entry.size}.")
            else:
                cart_item.quantity = new_quantity
                cart_item.save()
                messages.success(request, f"{product.name} ({color_variant.name}, {stock_entry.size}) quantity updated in cart.")
        else:
            cart_item.quantity = quantity
            cart_item.save()
            messages.success(request, f"{product.name} ({color_variant.name}, {stock_entry.size}) added to cart.")

        Wishlist.objects.filter(user=request.user, color_variant=color_variant).delete()
        return redirect('cart_view')
    return redirect('wishlist')

# ------------checkout view---------------------------------------------------
@login_required
def checkout_view(request):
    user = request.user

    # Fetch all addresses for the user
    addresses = Address.objects.filter(user=user)
    default_address = addresses.filter(is_default=True).first()

    # Fetch cart and cart items
    try:
        cart = Cart.objects.get(user=user)
        cart_items = CartItem.objects.filter(cart=cart, product__is_active=True)
    except Cart.DoesNotExist:
        cart = None
        cart_items = []

    # Price calculations
    subtotal = 0
    total_discount = 0
    total_quantity = 0

    for item in cart_items:
        product = item.product
        original_price = product.price
        discount_price = product.discount_price or original_price
        quantity = item.quantity

        item_total = original_price * quantity
        item_discount = (original_price - discount_price) * quantity

        subtotal += item_total
        total_discount += item_discount
        total_quantity += quantity

    shipping_cost = 0  
    taxes = subtotal * Decimal('0.05')  
    
    final_total = subtotal + shipping_cost+taxes

    context = {
        'addresses': addresses,
        'default_address': default_address,
        'cart_items': cart_items,
        'subtotal': subtotal,
        'total_discount': total_discount,
        'shipping_cost': shipping_cost,
        'final_total': final_total,
        'total_quantity': total_quantity,
        'taxes':taxes,
    }

    return render(request, 'checkout.html', context)



import logging

# Set up logging
logger = logging.getLogger(__name__)

@login_required
@never_cache
@no_cache_view
def place_order(request):
    if request.method == 'POST':
        # Get form data
        address_id = request.POST.get('selected_address')
        payment_method = request.POST.get('payment_method')
        logger.debug(f"Form data: selected_address={address_id}, payment_method={payment_method}")

        # Validate address and payment method
        if not address_id or not payment_method:
            messages.error(request, "Please select address and payment method.")
            logger.error("Missing address_id or payment_method")
            return redirect('checkout')

        # Get the address
        address = get_object_or_404(Address, id=address_id, user=request.user)
        logger.debug(f"Address found: {address}")

        # Get the user's cart
        cart = get_object_or_404(Cart, user=request.user)
        cart_items = CartItem.objects.filter(cart=cart)
        logger.debug(f"Cart items: {[(item.product.name, item.size, item.quantity) for item in cart_items]}")

        # Check if cart is empty
        if not cart_items.exists():
            messages.error(request, "Your cart is empty.")
            logger.error("Cart is empty")
            return redirect('cart_view')

        # Validate COD for orders above ₹10000
        total = calculate_cart_total(cart_items)  # Assume this is defined
        logger.debug(f"Calculated total: {total}")
        if payment_method == 'cod' and total > 100000:
            messages.error(request, "Cash on Delivery not available for orders above ₹100000.")
            logger.error("COD not allowed for total > ₹100000")
            return redirect('checkout')

        # Check stock availability for each item
        for item in cart_items:
            if not item.size:
                messages.error(request, f"No size specified for {item.product.name}")
                logger.error(f"No size specified for product: {item.product.name}")
                return redirect('cart_view')
            try:
                size_stock = ProductSizeStock.objects.get(product=item.product, size=item.size)
                logger.debug(f"Stock check for {item.product.name} (Size {item.size}): {size_stock.quantity}")
                if size_stock.quantity < item.quantity:
                    messages.error(request, f"Insufficient stock for {item.product.name} (Size {item.size}). Available: {size_stock.quantity}")
                    logger.error(f"Insufficient stock for {item.product.name} (Size {item.size}): {size_stock.quantity} < {item.quantity}")
                    return redirect('cart_view')
            except ProductSizeStock.DoesNotExist:
                messages.error(request, f"No stock record found for {item.product.name} (Size {item.size})")
                logger.error(f"No ProductSizeStock for {item.product.name} (Size {item.size})")
                return redirect('cart_view')

        # Create order and update stock atomically
        try:
            with transaction.atomic():
                # Generate unique order_id
                unique_order_id = f"ORDER-{uuid.uuid4().hex[:8].upper()}"
                logger.debug(f"Generated order_id: {unique_order_id}")

                # Create Order
                order = Order.objects.create(
                    user=request.user,
                    address=address,
                    payment_method=payment_method,
                    order_id=unique_order_id,
                    total_amount=total,
                    status='pending'
                )
                logger.debug(f"Order created: {order.order_id}")

                # Create OrderItems and reduce stock
                for item in cart_items:
                    size_stock = ProductSizeStock.objects.get(product=item.product, size=item.size)
                    logger.debug(f"Reducing stock for {item.product.name} (Size {item.size}): {size_stock.quantity} -> {size_stock.quantity - item.quantity}")
                    size_stock.quantity -= item.quantity
                    size_stock.save()

                    OrderItem.objects.create(
                        order=order,
                        product=item.product,
                        quantity=item.quantity,
                        price=item.product.price,
                        size=item.size
                    )
                    logger.debug(f"OrderItem created for {item.product.name} (Size {item.size}, Qty: {item.quantity})")

                # Clear cart
                cart_items.delete()
                logger.debug("Cart cleared")

                return redirect('order_success', order_id=order.id)
        except Exception as e:
            logger.error(f"Order creation failed: {str(e)}", exc_info=True)
            messages.error(request, f"An error occurred while placing the order: {str(e)}")
            return redirect('checkout')
    return redirect('checkout')

    

@login_required
@never_cache
@no_cache_view
def order_success(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'order_success.html', {'order': order})


@login_required
def orders_list_view(request):
    user = request.user
    query = request.GET.get('q', '')
    sort = request.GET.get('sort', 'latest')

    # Filter orders belonging to the user
    orders = Order.objects.filter(user=user)

    # Search by product name
    if query:
        orders = orders.filter(items__product__name__icontains=query).distinct()

    # Sort mapping
    sort_options = {
        'latest': '-created_at',
        'oldest': 'created_at',
        'amount_high': '-total_amount',
        'amount_low': 'total_amount',
    }
    sort_by = sort_options.get(sort, '-created_at')
    orders = orders.order_by(sort_by)

    context = {
        'orders': orders,
        'query': query,
        'sort': sort,
    }
    return render(request, 'orders_list.html', context)





@login_required
def download_invoice(request, order_id):
    try:
        order = Order.objects.get(id=order_id, user=request.user)
    except Order.DoesNotExist:
        return HttpResponse("Order not found", status=404)

    template_path = 'invoice_template.html'
    context = {'order': order}

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename=invoice_{order.order_id}.pdf'

    template = get_template(template_path)
    html = template.render(context)

    pisa_status = pisa.CreatePDF(html, dest=response)

    if pisa_status.err:
        return HttpResponse('Error generating invoice PDF')
    return response



@login_required
def order_detail(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    items = order.items.select_related('product').all()

    # Price calculations
    subtotal = Decimal('0.00')
    total_discount = Decimal('0.00')
    total_quantity = 0

    for item in items:
        product = item.product
        original_price = product.price
        discount_price = product.discount_price or original_price
        quantity = item.quantity

        item_total = original_price * quantity
        item_discount = (original_price - discount_price) * quantity

        subtotal += item_total
        total_discount += item_discount
        total_quantity += quantity

    shipping_cost = Decimal('0.00')  # Update if needed
    taxes = subtotal * Decimal('0.05')  # 5% tax

    final_total = subtotal + shipping_cost + taxes

    context = {
        'order': order,
        'items': items,
        'subtotal': subtotal,
        'discount': total_discount,
        'tax': taxes,
        'shipping': shipping_cost,
        'grand_total': final_total,
        'total_quantity': total_quantity,
    }
    return render(request, 'order_detail.html', context)

@never_cache
@require_POST
@login_required
def cancel_order(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    reason = request.POST.get('cancel_reason', '')

    if order.status != 'cancelled':
        order.status = 'cancelled'

        if order.payment_method != 'cod':
            order.payment_status = 'refunded'

        order.save()

        # Restore stock per size
        for item in order.items.all():
            product = item.product
            size = item.size  # Assuming size is stored in the order item
            quantity = item.quantity

            try:
                size_stock = ProductSizeStock.objects.get(product=product, size=size)
                size_stock.quantity += quantity
                size_stock.save()
            except ProductSizeStock.DoesNotExist:
                # Optional: create stock record if missing
                ProductSizeStock.objects.create(product=product, size=size, quantity=quantity)

    messages.success(request, "Order cancelled successfully and stock restored.")
    return redirect('order_detail', order_id=order.id)