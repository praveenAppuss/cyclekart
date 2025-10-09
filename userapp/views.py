import datetime
from django.utils import timezone
from django.views.decorators.cache import cache_control
from dotenv import get_key
import pytz
from .otp import generate_otp, send_otp_email
from decimal import Decimal
import razorpay
from django.middleware.csrf import get_token
from django.urls import reverse
import logging
logger = logging.getLogger(__name__)
import uuid
from django.forms import DecimalField
from .services import WalletService
from django.shortcuts import render, redirect
from django.contrib.auth import get_user_model, authenticate, login, logout
from django.contrib.auth.hashers import make_password
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.conf import settings
from django.db import transaction, IntegrityError
from django.contrib.auth import BACKEND_SESSION_KEY
import random
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models.functions import Coalesce
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404
from django.contrib.messages import get_messages
from django.contrib import messages
from adminapp.models import Product,Category,Brand,ProductSizeStock,ProductColorVariant
from userapp.models import Coupon, CustomUser,Address,Cart,CartItem, ReturnRequest, UsedCoupon,Wishlist,Order,OrderItem,Wallet,WalletTransaction
import re
from django.views.decorators.cache import never_cache
from .utils import no_cache_view,calculate_cart_total
from django.http import HttpResponse, JsonResponse
from django.template.loader import get_template
from xhtml2pdf import pisa
from django.db.models import Q, F, FloatField, ExpressionWrapper, Case, When, Value, IntegerField,Min,Max,Sum
from .forms import AddressForm
import json
from django.db.models import Exists, OuterRef
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_POST
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from allauth.socialaccount.models import SocialAccount
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponseBadRequest

User = get_user_model()

@no_cache_view
@never_cache
@cache_control(no_store=True, no_cache=True, must_revalidate=True)
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
@cache_control(no_store=True, no_cache=True, must_revalidate=True)
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


@cache_control(no_store=True, no_cache=True, must_revalidate=True)
@never_cache
@no_cache_view
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
            messages.error(request, "Your account is currently suspended.",extra_tags='login')
        else:
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            request.session.set_expiry(300)
            return redirect('user_home')

    return render(request, 'user_login.html')

@cache_control(no_store=True, no_cache=True, must_revalidate=True)
@never_cache
@no_cache_view
def resend_otp(request):
    signup_data = request.session.get('signup_data')
    if not signup_data:
        return redirect('user_signup')
    otp = str(random.randint(100000, 999999))
    print(otp)
    request.session['otp'] = otp
    send_mail(
        subject='CycleKart - Resend OTP',
        message=f'Your new OTP is: {otp}',
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[signup_data['email']],
        fail_silently=False,
    )
    print(otp)
    return redirect('verify_otp')


@cache_control(no_store=True, no_cache=True, must_revalidate=True, max_age=0)
@never_cache
def user_logout(request):
    logout(request)              
    request.session.flush()      
    return redirect('user_login')



@login_required(login_url='user_login')
@cache_control(no_store=True, no_cache=True, must_revalidate=True,max_age=0)
@never_cache
def user_home(request):
    all_products = list(Product.objects.filter(is_active=True, is_deleted=False))
    featured_products = random.sample(all_products, min(len(all_products), 4))  
    return render(request, 'user_home.html', {'featured_products': featured_products})


@login_required(login_url='user_login')
@cache_control(no_store=True, no_cache=True, must_revalidate=True)
@never_cache
def user_product_list(request):
    
    products = Product.objects.filter(is_deleted=False, is_active=True).prefetch_related('color_variants', 'color_variants__size_stocks')

    price_range = products.aggregate(
        min_price=Min(Coalesce(F('discount_price'), F('price'))),
        max_price=Max(Coalesce(F('discount_price'), F('price')))
    )
    min_price = price_range['min_price'] or 0
    max_price = price_range['max_price'] or 10000

    # Simplified stock filter: products with at least one size stock > 0
    products = products.filter(color_variants__size_stocks__quantity__gt=0).distinct()

    query = request.GET.get('search', '').strip()
    if query:
        products = products.filter(
            Q(name__icontains=query) | Q(description__icontains=query)
        ).distinct()

    category_ids = request.GET.getlist('category')
    brand_id = request.GET.get('brand')
    size_list = request.GET.getlist('size')
    color_list = request.GET.getlist('color')
    price_min_str = request.GET.get('price_min', '')
    price_max_str = request.GET.get('price_max', '')

    try:
        price_min = float(price_min_str) if price_min_str else min_price
        price_max = float(price_max_str) if price_max_str else max_price
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

    
    sort_by = request.GET.get('sort', 'name_asc')
    sort_mapping = {
        'price_asc': 'display_price',
        'price_desc': '-display_price',
        'name_asc': 'name',
        'name_desc': '-name',
    }
    products = products.order_by(sort_mapping.get(sort_by, 'name')).distinct()
    
    paginator = Paginator(products, 8)  
    page_number = request.GET.get('page')
    products_page = paginator.get_page(page_number)

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
        'price_min_input': price_min_str,
        'price_max_input': price_max_str,
        'sort_by': sort_by,
        'min_price': min_price,
        'max_price': max_price,
    }
    return render(request, 'user_product_list.html', context)


@login_required(login_url='user_login')
@cache_control(no_store=True, no_cache=True, must_revalidate=True)
@never_cache
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

    final_price = product.get_final_price()
    savings = product.get_savings()
    
    best_discount = product.get_best_discount()  

    related_products = Product.objects.filter(
        category=product.category,
        is_active=True,
        is_deleted=False
    ).exclude(id=product_id).distinct()[:4]

    for variant in color_variants:
        variant.size_stocks_data = [
            {
                'id': stock.id,  
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
        'final_price': final_price,  
        'savings': savings,         
        'best_discount': best_discount,  
        'wishlist_items': wishlist_items,
    }
    return render(request, 'product_detail.html', context)


# user profile section ---------------------------------------------------

@login_required
@cache_control(no_store=True, no_cache=True, must_revalidate=True)
@never_cache
def profile_view(request):
    user = request.user
    user_addresses = Address.objects.filter(user=user)  
    default_address = user_addresses.filter(is_default=True).first()

    return render(request, 'profile.html', {
        'user': user,
        'user_addresses': user_addresses,
        'default_address': default_address,
    })



@login_required
@cache_control(no_store=True, no_cache=True, must_revalidate=True)
@never_cache
def upload_profile_image(request):
    if request.method == 'POST' and request.FILES.get('profile_image'):
        request.user.profile_image = request.FILES['profile_image']
        request.user.save()
    return redirect('profile')

@login_required
@cache_control(no_store=True, no_cache=True, must_revalidate=True)
@never_cache
def update_profile(request):
    user = request.user
    if request.method == 'POST':
        if 'otp' in request.POST:
            entered_otp = request.POST.get('otp')
            session_otp = request.session.get('otp')
            pending_email = request.session.get('pending_email')
            if entered_otp == session_otp and pending_email:
                if CustomUser.objects.filter(email=pending_email).exclude(id=user.id).exists():
                    messages.error(request, "This email is already in use.")
                    return redirect('profile')
                user.email = pending_email
                user.save()
                request.session.pop('otp', None)
                request.session.pop('pending_email', None)
                messages.success(request, "Email updated successfully.")
            else:
                messages.error(request, "Invalid or expired OTP.")
            return redirect('profile')

        username = request.POST.get('username', user.username).strip()
        email = request.POST.get('email', user.email).strip()
        mobile = request.POST.get('mobile', user.mobile).strip()

        errors = {}
        if not email:
            errors['email'] = "Email is required."
        elif not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            errors['email'] = "Enter a valid email address."
        elif email != user.email and CustomUser.objects.filter(email=email).exclude(id=user.id).exists():
            errors['email'] = "This email is already in use."

        if not mobile:
            errors['mobile'] = "Mobile number is required."
        elif not re.match(r"^\d{10}$", mobile):
            errors['mobile'] = "Enter a valid 10-digit mobile number."
        elif mobile != user.mobile and CustomUser.objects.filter(mobile=mobile).exclude(id=user.id).exists():
            errors['mobile'] = "This mobile number is already in use."

        if errors:
            for field, error in errors.items():
                messages.error(request, error)
            return redirect('profile')

        
        if email != user.email:
            otp = generate_otp()
            request.session['otp'] = otp
            request.session['pending_email'] = email
            send_otp_email(email, otp, purpose="Email Update Verification")
            print(otp)  
            messages.info(request, "An OTP has been sent to your new email. Please verify to update.")
            return render(request, 'profile.html', {
                'user': user,
                'user_addresses': Address.objects.filter(user=user),
                'default_address': Address.objects.filter(user=user, is_default=True).first(),
                'show_otp_modal': True,
            })

        user.username = username
        user.mobile = mobile
        user.save()

        selected_address_id = request.POST.get('selected_user')
        if selected_address_id:
            try:
                Address.objects.filter(user=user, is_default=True).update(is_default=False)
                address = Address.objects.get(id=selected_address_id, user=user)
                address.is_default = True
                address.save()
            except Address.DoesNotExist:
                pass
        messages.success(request, "Profile updated successfully.")
        return redirect('profile')
    return redirect('profile')


@cache_control(no_store=True, no_cache=True, must_revalidate=True)
@never_cache
def resend_profile_otp(request):
    pending_email = request.session.get('pending_email')
    if not pending_email:
        messages.error(request, "No pending email found. Please try updating your email again.")
        return redirect('profile')
    
    otp = generate_otp()
    request.session['otp'] = otp
    send_otp_email(pending_email, otp, purpose="Email Update Verification")
    print(otp)  
    messages.info(request, "A new OTP has been sent to your email.")
    return redirect('profile')

    

# Address management section---------------------------------

@login_required(login_url='user_login')
@cache_control(no_store=True, no_cache=True, must_revalidate=True)
@never_cache
def address_list(request):
    addresses = Address.objects.filter(user=request.user)
    form = AddressForm()
    selected_id = request.session.pop('selected_address_id', None)
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
        'address_json_map': mark_safe(json.dumps(address_json_map)),
        'selected_id': selected_id,
    }
    return render(request, 'address_page.html', context)


@login_required(login_url='user_login')
@cache_control(no_store=True, no_cache=True, must_revalidate=True)
@never_cache
def add_address(request):
    if request.method == 'POST':
        form = AddressForm(request.POST)
        if form.is_valid():
            address = form.save(commit=False)
            address.user = request.user
            is_default = not Address.objects.filter(user=request.user, is_default=True).exists()
            address.is_default = is_default
            address.save()

            if is_default:
                Address.objects.filter(user=request.user).exclude(id=address.id).update(is_default=False)
            request.session['selected_address_id'] = address.id

            next_url = request.GET.get('next')
            if next_url:
                return redirect(f"{next_url}?new_address_id={address.id}")
            return redirect('address_list')
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': 'Invalid address data. Please check the form.'}, status=400)
            messages.error(request, 'Invalid address data. Please check the form.')
            return redirect('address_list')
    return redirect('address_list')

@login_required(login_url='user_login')
@cache_control(no_store=True, no_cache=True, must_revalidate=True)
@never_cache
def update_address(request, pk):
    address = get_object_or_404(Address, pk=pk, user=request.user)
    if request.method == 'POST':
        form = AddressForm(request.POST, instance=address)
        if form.is_valid():
            form.save()
            request.session['selected_address_id'] = address.id
            next_url = request.GET.get('next')
            if next_url:
                return redirect(f"{next_url}?new_address_id={address.id}")
            return redirect('address_list')
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': 'Invalid address data. Please check the form.'}, status=400)
            messages.error(request, 'Invalid address data. Please check the form.')
            return redirect('address_list')
    return redirect('address_list')

@login_required(login_url='user_login')
@cache_control(no_store=True, no_cache=True, must_revalidate=True)
@never_cache
def delete_address(request, pk):
    address = get_object_or_404(Address, pk=pk, user=request.user)
    address.delete()
    if request.session.get('selected_address_id') == pk:
        request.session.pop('selected_address_id', None)
    return redirect('address_list')




# ---------------------------Cart Management------------------------

@login_required(login_url='user_login')
@cache_control(no_store=True, no_cache=True, must_revalidate=True)
@never_cache
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

    return redirect('product_detail',product_id=product.id)


def get_sizes(request, color_variant_id):
    size_stocks = ProductSizeStock.objects.filter(color_variant_id=color_variant_id).values('id', 'size')
    sizes = [{'id': ss['id'], 'size_display': dict(ProductSizeStock.SIZE_CHOICES).get(ss['size'], ss['size'])} for ss in size_stocks]
    return JsonResponse({'sizes': sizes})


@login_required(login_url='user_login')
@cache_control(no_store=True, no_cache=True, must_revalidate=True)
@never_cache
def cart_view(request):
    cart = Cart.objects.filter(user=request.user).first()
    cart_items = (
        cart.items
        .select_related('product', 'color_variant', 'size_stock')
        .prefetch_related('product__color_variants__images')
        if cart else []
    )

    total_subtotal = Decimal('0.00')
    total_discount = Decimal('0.00')
    TAX_RATE = Decimal('0.05')
    has_unavailable_items = False

    for item in cart_items:
        product = item.product

        # Always use the original price for subtotal
        item_unit_price = product.price
        item.subtotal = item_unit_price * item.quantity
        total_subtotal += item.subtotal

        # Calculate savings based on offers/discounts
        item_unit_savings = product.get_savings()  # price - final_price
        item.savings = item_unit_savings * item.quantity
        total_discount += item.savings

        # Image and availability
        item.image = (
            item.color_variant.images.first().image.url
            if item.color_variant and item.color_variant.images.exists()
            else product.thumbnail.url if product.thumbnail else ''
        )
        item.stock = item.size_stock.quantity
        item.max_quantity = min(item.stock, 5)
        item.size_display = item.size_stock.get_size_display()

        # Availability check
        if (
            product.is_deleted or not product.is_active or
            product.category.is_deleted or not product.category.is_active or
            item.quantity > item.stock
        ):
            has_unavailable_items = True
            item.is_available = False
        else:
            item.is_available = True

    # Totals
    taxable_amount = total_subtotal - total_discount
    taxes = taxable_amount * TAX_RATE
    final_total = taxable_amount + taxes

    return render(request, 'cart.html', {
        'cart_items': cart_items,
        'cart_total': total_subtotal,
        'total_discount': total_discount,
        'taxes': taxes,
        'total': final_total,
        'has_unavailable_items': has_unavailable_items,
    })

@login_required(login_url='user_login')
@cache_control(no_store=True, no_cache=True, must_revalidate=True)
@never_cache
@require_http_methods(["POST"])
def update_cart_quantity(request, cart_item_id):
    cart_item = get_object_or_404(CartItem, id=cart_item_id, cart__user=request.user)
    action = request.POST.get('action')

    stock_entry = cart_item.size_stock
    max_quantity = min(stock_entry.quantity, 5)

    if action == 'increment' and cart_item.quantity < max_quantity:
        cart_item.quantity += 1
        messages.success(request, f"Quantity updated for {cart_item.product.name} ({cart_item.color_variant.name}, {stock_entry.get_size_display()}).")
    elif action == 'decrement' and cart_item.quantity > 1:
        cart_item.quantity -= 1
        messages.success(request, f"Quantity updated for {cart_item.product.name} ({cart_item.color_variant.name}, {stock_entry.get_size_display()}).")
    else:
        msg = f"Cannot update quantity. Max limit: {max_quantity} or minimum reached."
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': msg}, status=400)
        messages.warning(request, msg)
        return redirect('cart_view')

    cart_item.save()

    # Recalculate using product's offer logic
    cart = cart_item.cart
    cart_items = cart.items.select_related('product', 'size_stock').all()

    total_subtotal = sum(item.product.price * item.quantity for item in cart_items)
    total_discount = sum(item.product.get_savings() * item.quantity for item in cart_items)
    taxable_amount = total_subtotal - total_discount
    taxes = taxable_amount * Decimal('0.05')
    total = taxable_amount + taxes

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        storage = messages.get_messages(request)
        message = ''
        for msg in storage:
            message = msg.message  # Get the last message
        return JsonResponse({
            'success': True,
            'quantity': cart_item.quantity,
            'cart_total': float(total_subtotal),
            'total_discount': float(total_discount),
            'taxes': float(taxes),
            'total': float(total),
            'message': message
        })

    return redirect('cart_view')



@login_required(login_url='user_login')
@cache_control(no_store=True, no_cache=True, must_revalidate=True)
@never_cache
def remove_from_cart(request, cart_item_id):
    cart_item = get_object_or_404(CartItem, id=cart_item_id, cart__user=request.user)
    product_name = cart_item.product.name
    color_name = cart_item.color_variant.name
    size_display = cart_item.size_stock.get_size_display()
    cart_item.delete()
    messages.success(request, f"{product_name} ({color_name}, {size_display}) removed from cart.")
    return redirect('cart_view')



@login_required(login_url='user_login')
@cache_control(no_store=True, no_cache=True, must_revalidate=True)
@never_cache
def wishlist_view(request):
    wishlist_items = Wishlist.objects.filter(user=request.user).select_related('color_variant__product')
    size_map = {}
    for item in wishlist_items:
        sizes = ProductSizeStock.objects.filter(
            color_variant=item.color_variant, quantity__gt=0
        ).values('id', 'size', 'quantity')
        size_map[item.color_variant.id] = [
            {'id': s['id'], 'size': s['size'], 'display': s['size']}  
            for s in sizes
        ]

    return render(request, 'wishlist.html', {
        'wishlist_items': wishlist_items,
        'sizes': size_map,
    })


@login_required(login_url='user_login')
@cache_control(no_store=True, no_cache=True, must_revalidate=True)
@never_cache
def add_to_wishlist(request, color_variant_id):
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    color_variant = get_object_or_404(ProductColorVariant, id=color_variant_id, product__is_active=True, product__is_deleted=False)

    if not color_variant.product.category.is_active or color_variant.product.category.is_deleted:
        if is_ajax:
            return JsonResponse({'success': False, 'message': 'This product is unavailable.'}, status=400)
        messages.error(request, 'This product is unavailable.')
        return redirect('product_detail', product_id=color_variant.product.id)

    wishlist_item = Wishlist.objects.filter(user=request.user, color_variant=color_variant).first()
    if wishlist_item:
        wishlist_item.delete()
        message = f"{color_variant.product.name} ({color_variant.name}) removed from wishlist."
        if is_ajax:
            return JsonResponse({'success': True, 'added': False, 'message': message})
        messages.success(request, message)
    else:
        Wishlist.objects.create(user=request.user, color_variant=color_variant)
        message = f"{color_variant.product.name} ({color_variant.name}) added to wishlist."
        if is_ajax:
            return JsonResponse({'success': True, 'added': True, 'message': message})
        messages.success(request, message)

    return redirect('product_detail', product_id=color_variant.product.id)



@login_required(login_url='user_login')
@cache_control(no_store=True, no_cache=True, must_revalidate=True)
@never_cache
def remove_from_wishlist(request, wishlist_id):
    item = get_object_or_404(Wishlist, id=wishlist_id, user=request.user)
    product_name = item.color_variant.product.name
    color_name = item.color_variant.name
    item.delete()
    messages.success(request, f"{product_name} ({color_name}) removed from wishlist.",extra_tags="wishlist")
    return redirect('wishlist')

@login_required(login_url='user_login')
@cache_control(no_store=True, no_cache=True, must_revalidate=True)
@never_cache
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
        return redirect('wishlist')
    return redirect('wishlist')



# ------------checkout view---------------------------------------------------


@login_required(login_url='user_login')
@cache_control(no_store=True, no_cache=True, must_revalidate=True)
@never_cache
def checkout_view(request):
    user = request.user
    addresses = Address.objects.filter(user=user)
    default_address = addresses.filter(is_default=True).first()
    
    try:
        cart = Cart.objects.get(user=user)
        cart_items = CartItem.objects.filter(cart=cart).select_related('product', 'color_variant', 'size_stock')
    except Cart.DoesNotExist:
        cart = None
        cart_items = []

    subtotal = Decimal('0')
    total_discount = Decimal('0')
    total_quantity = 0
    coupon_discount = Decimal('0')

    for item in cart_items:
        # Updated: Use dynamic final_price and savings (includes offers)
        unit_price = item.product.price
        unit_savings = item.product.get_savings()
        quantity = item.quantity
        item_total = unit_price * quantity
        item_discount = unit_savings * quantity
        subtotal += item_total
        total_discount += item_discount
        total_quantity += quantity
        logger.debug(f"Item: {item.product.name}, Final Price: {unit_price}, Savings: {unit_savings}, Qty: {quantity}, Item Total: {item_total}, Item Discount: {item_discount}")

    shipping_cost = Decimal('0')
    taxable_amount = subtotal - total_discount  
    applied_coupon = None
    coupon_error = None

    if 'applied_coupon_id' in request.session:
        try:
            applied_coupon = Coupon.objects.get(id=request.session['applied_coupon_id'], active=True, is_deleted=False)
            if Decimal(str(applied_coupon.minimum_order_amount)) > taxable_amount:
                coupon_error = "Minimum order amount not met for this coupon."
                del request.session['applied_coupon_id']
                del request.session['coupon_discount']
                applied_coupon = None
            else:
                coupon_discount = Decimal(str(applied_coupon.discount_amount))
        except Coupon.DoesNotExist:
            del request.session['applied_coupon_id']
            del request.session['coupon_discount']
            applied_coupon = None

    net_taxable_amount = taxable_amount - coupon_discount  
    taxes = net_taxable_amount * Decimal('0.05')  
    final_total = net_taxable_amount + shipping_cost + taxes
    logger.debug(f"Subtotal: {subtotal}, Total Discount: {total_discount}, Coupon Discount: {coupon_discount}, Taxable Amount: {taxable_amount}, Net Taxable Amount: {net_taxable_amount}, Taxes: {taxes}, Final Total: {final_total}")

    current_time = timezone.now()
    ist = pytz.timezone('Asia/Kolkata')
    eligible_for_coupons = taxable_amount > Decimal('0')
    coupons = Coupon.objects.filter(
        active=True,
        valid_from__lte=current_time,
        valid_to__gte=current_time,
        is_deleted=False
    ).exclude(used_by__user=user)

    used_coupons = {uc.coupon_id for uc in UsedCoupon.objects.filter(user=user)}
    coupon_status = {coupon.id: coupon.id in used_coupons for coupon in coupons}

    logger.debug(f"Current time: {current_time} (IST: {current_time.astimezone(ist)}), Taxable Amount: {taxable_amount}, Coupons Count: {coupons.count()}")

    context = {
        'addresses': addresses,
        'default_address': default_address,
        'cart_items': cart_items,
        'subtotal': subtotal,
        'total_discount': total_discount,
        'coupon_discount': coupon_discount,
        'shipping_cost': shipping_cost,
        'taxes': taxes,
        'final_total': final_total,
        'total_quantity': total_quantity,
        'applied_coupon': applied_coupon,
        'coupons': coupons,
        'coupon_error': coupon_error,
        'eligible_for_coupons': eligible_for_coupons,
        'taxable_amount': taxable_amount,  
        'net_taxable_amount': net_taxable_amount,  
        'coupon_status': coupon_status,
    }

    return render(request, 'checkout.html', context)


@login_required(login_url='user_login')
@cache_control(no_store=True, no_cache=True, must_revalidate=True)
@never_cache
@require_http_methods(["POST"])
def apply_coupon(request):
    if request.method == 'POST':
        coupon_code = request.POST.get('coupon_code', '').strip()
        if not coupon_code:
            return JsonResponse({'success': False, 'message': 'Please enter a coupon code.'})

        user = request.user
        try:
            cart = Cart.objects.get(user=user)
            cart_items = CartItem.objects.filter(cart=cart).select_related('product', 'color_variant', 'size_stock')
            
            # Updated: Recalculate subtotal with dynamic offers
            subtotal = Decimal('0')
            total_discount = Decimal('0')
            for item in cart_items:
                unit_price = item.product.price
                unit_savings = item.product.get_savings()
                quantity = item.quantity
                subtotal += unit_price * quantity
                total_discount += unit_savings * quantity
            taxable_amount = subtotal - total_discount
            logger.debug(f"Taxable Amount in apply_coupon: {taxable_amount}")

            coupon = Coupon.objects.get(
                code=coupon_code,
                active=True,
                valid_from__lte=timezone.now(),
                valid_to__gte=timezone.now(),
                is_deleted=False
            )

            if UsedCoupon.objects.filter(user=user, coupon=coupon).exists():
                return JsonResponse({'success': False, 'message': 'This coupon has already been used.'})

            min_order_amount = Decimal(str(coupon.minimum_order_amount))
            logger.debug(f"Minimum order amount: {min_order_amount}")
            if min_order_amount > taxable_amount:
                return JsonResponse({'success': False, 'message': 'Minimum order amount not met for this coupon.'})

            request.session['applied_coupon_id'] = coupon.id  
            request.session['coupon_discount'] = str(coupon.discount_amount)
            return JsonResponse({'success': True, 'message': 'Coupon applied successfully!', 'coupon_discount': float(coupon.discount_amount)})
        except Coupon.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Invalid or expired coupon code.'})
    return JsonResponse({'success': False, 'message': 'Invalid request method.'})


@login_required(login_url='user_login')
@never_cache
def remove_coupon(request):
    if request.method == 'POST':
        if 'applied_coupon_id' in request.session:  
            del request.session['applied_coupon_id']
            del request.session['coupon_discount']
            return JsonResponse({'success': True, 'message': 'Coupon removed successfully!', 'reload': True})
        return JsonResponse({'success': False, 'message': 'No coupon applied.'})
    return JsonResponse({'success': False, 'message': 'Invalid request method.'})
    
    
    
razorpay_client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))


@login_required(login_url='user_login')
@never_cache
@cache_control(no_store=True, no_cache=True, must_revalidate=True)
@require_http_methods(["POST"])
def place_order(request):
    if request.method != 'POST':
        return redirect('checkout')

    address_id = request.POST.get('selected_address')
    payment_method = request.POST.get('payment_method')

    if not address_id or not payment_method:
        messages.error(request, "Please select address and payment method.")
        return redirect('checkout')

    address = get_object_or_404(Address, id=address_id, user=request.user)
    cart = get_object_or_404(Cart, user=request.user)
    cart_items = cart.items.select_related('product', 'color_variant', 'size_stock').all()

    if not cart_items.exists():
        messages.error(request, "Your cart is empty.")
        return redirect('cart_view')

    # Updated: Calculate with dynamic offers
    subtotal = Decimal('0.00')
    product_discount = Decimal('0.00')
    coupon_discount = Decimal('0.00')
    applied_coupon = None

    for item in cart_items:
        unit_price = item.product.price
        unit_savings = item.product.get_savings()
        quantity = item.quantity
        subtotal += unit_price * quantity
        product_discount += unit_savings * quantity
        logger.debug(f"Item: {item.product.name}, Final Price: {unit_price}, Savings: {unit_savings}, Qty: {quantity}, Subtotal: {unit_price * quantity}, Discount: {unit_savings * quantity}")

    if 'applied_coupon_id' in request.session:
        try:
            applied_coupon = Coupon.objects.get(
                id=request.session['applied_coupon_id'],
                active=True,
                is_deleted=False,
                valid_from__lte=timezone.now(),
                valid_to__gte=timezone.now()
            )
            taxable_amount = subtotal - product_discount
            if Decimal(str(applied_coupon.minimum_order_amount)) <= taxable_amount:
                coupon_discount = Decimal(str(applied_coupon.discount_amount))
            else:
                messages.error(request, "Minimum order amount not met for the applied coupon.")
                del request.session['applied_coupon_id']
                applied_coupon = None
        except Coupon.DoesNotExist:
            del request.session['applied_coupon_id']
            applied_coupon = None

    taxable_amount = subtotal - product_discount - coupon_discount  
    tax = taxable_amount * Decimal('0.05')
    shipping_cost = Decimal('0.00')
    total_amount = taxable_amount + tax + shipping_cost
    razorpay_amount = int(total_amount * 100)
    logger.debug(f"Subtotal: {subtotal}, Product Discount: {product_discount}, Coupon Discount: {coupon_discount}, Tax: {tax}, Total: {total_amount}")

    if payment_method == 'cod' and total_amount > Decimal('100000'):
        messages.error(request, "Cash on Delivery not available for orders above ₹100000.")
        return redirect('checkout')

    try:
        with transaction.atomic():
            for item in cart_items:
                size_stock = item.size_stock
                if size_stock.quantity < item.quantity:
                    raise ValueError(f"Insufficient stock for {item.product.name} (Size {size_stock.size}): {size_stock.quantity} available, {item.quantity} requested")

            unique_order_id = f"ORDER-{uuid.uuid4().hex[:8].upper()}"
            order = Order.objects.create(
                user=request.user,
                address=address,
                payment_method=payment_method,
                order_id=unique_order_id,
                subtotal=subtotal,
                discount=product_discount,
                coupon_discount=coupon_discount,
                coupon_code=applied_coupon.code if applied_coupon else None,
                tax=tax,
                shipping_cost=shipping_cost,
                total_amount=total_amount,
                status='pending'
            )

            if applied_coupon:
                UsedCoupon.objects.create(user=request.user, coupon=applied_coupon)
                del request.session['applied_coupon_id']  

            initial_payment_status = 'pending' if payment_method == 'cod' else 'paid'

            for item in cart_items:
                size_stock = item.size_stock
                size_stock.quantity -= item.quantity
                size_stock.save(update_fields=['quantity'])

                # Updated: Store dynamic final_price as price, original as reference
                final_price = item.product.get_final_price()
                OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    color_variant=item.color_variant,
                    size=size_stock.size,
                    quantity=item.quantity,
                    price=item.product.price,  # Original for reference
                    discount_price=final_price,  # Offer-applied as discount_price
                    payment_status=initial_payment_status
                )

            if payment_method == 'cod':
                order.status = 'confirmed'
                order.payment_status = 'pending'
                order.save()
                cart.items.all().delete()
                return redirect('order_success', order_id=order.id)

            elif payment_method == 'wallet':
                wallet, _ = Wallet.objects.get_or_create(user=request.user)
                if wallet.balance >= total_amount:
                    wallet.balance -= total_amount
                    wallet.save()
                    WalletTransaction.objects.create(
                        wallet=wallet,
                        order=order,
                        amount=total_amount,
                        transaction_type='debit',
                        description=f"Payment for Order {order.order_id}",
                        transaction_id=f"TXN-{uuid.uuid4().hex[:8].upper()}"
                    )
                    order.status = 'confirmed'
                    order.payment_status = 'paid'
                    order.save()
                    cart.items.all().delete()
                    return redirect('order_success', order_id=order.id)
                else:
                    raise ValueError("Insufficient wallet balance.")

            elif payment_method == 'razorpay':
                razorpay_order = razorpay_client.order.create({
                    "amount": razorpay_amount,
                    "currency": "INR",
                    "payment_capture": "1"
                })
                order.razorpay_order_id = razorpay_order['id']
                order.payment_status = 'pending'
                order.save()
                return render(request, "razorpay_checkout.html", {
                    "order": order,
                    "razorpay_order": razorpay_order,
                    "razorpay_key": settings.RAZORPAY_KEY_ID,
                    "amount": razorpay_amount,
                    "currency": "INR",
                    "csrf_token": get_token(request)
                })

            else:
                raise ValueError("Invalid payment method selected.")

    except Exception as e:
        logger.error(f"Order creation failed: {str(e)}", exc_info=True)
        messages.error(request, f"An error occurred while placing the order: {str(e)}")
        return redirect('checkout')
    

@csrf_exempt
@require_http_methods(["POST"])
def payment_handler(request):
    if request.method == "POST":
        try:
            body = request.body.decode('utf-8')
            logger.debug(f"Raw request body: {body}")
            data = json.loads(body) if body else {}
            logger.debug(f"Parsed JSON data: {data}")
        except Exception as e:
            logger.error(f"Failed to parse request body: {str(e)}")
            data = {}

        razorpay_payment_id = data.get("razorpay_payment_id") or request.POST.get("razorpay_payment_id")
        razorpay_order_id = data.get("razorpay_order_id") or request.POST.get("razorpay_order_id")
        razorpay_signature = data.get("razorpay_signature") or request.POST.get("razorpay_signature")
        order_id = data.get("order_id") or request.POST.get("order_id")
        logger.debug(f"Extracted data: payment_id={razorpay_payment_id}, order_id={razorpay_order_id}, signature={razorpay_signature}, django_order_id={order_id}")

        if not all([razorpay_payment_id, razorpay_order_id, razorpay_signature]):
            logger.error(f"Missing payment data: payment_id={razorpay_payment_id}, order_id={razorpay_order_id}, signature={razorpay_signature}, django_order_id={order_id}")
            messages.error(request, "Payment data is incomplete. Please try again or contact support.")
            if order_id:
                try:
                    order = get_object_or_404(Order, id=order_id)
                    logger.warning(f"Payment data missing, falling back to order {order.order_id} for manual verification")
                    order.payment_status = "pending"
                    order.save()
                    return JsonResponse({"status": "pending", "redirect_url": reverse('order_pending', args=[order.id])})
                except Exception as e:
                    logger.error(f"Fallback failed for order_id={order_id}: {str(e)}")
            return JsonResponse({"status": "failed", "redirect_url": reverse('payment_failed')})

        try:
            order = get_object_or_404(Order, razorpay_order_id=razorpay_order_id)

            params_dict = {
                "razorpay_order_id": razorpay_order_id,
                "razorpay_payment_id": razorpay_payment_id,
                "razorpay_signature": razorpay_signature
            }
            logger.debug(f"Verifying payment with params: {params_dict}")

            razorpay_client.utility.verify_payment_signature(params_dict)

            order.razorpay_payment_id = razorpay_payment_id
            order.razorpay_signature = razorpay_signature
            order.payment_status = "paid"
            order.status = "confirmed"
            order.items.update(payment_status='paid')
            order.save()
            logger.info(f"Payment successful for order {order.order_id}")

            cart = Cart.objects.get(user=order.user)
            cart.items.all().delete()

            success_url = reverse('order_success', args=[order.id])
            return JsonResponse({"status": "success", "redirect_url": success_url})

        except razorpay.errors.SignatureVerificationError as e:
            logger.error(f"Signature verification failed: {str(e)} with params {params_dict}")
            order = get_object_or_404(Order, razorpay_order_id=razorpay_order_id)
            with transaction.atomic():
                order.payment_status = "failed"
                order.status = "cancelled"
                order.save()
                for item in order.items.all():
                    size_stock = ProductSizeStock.objects.get(
                        color_variant=item.color_variant,
                        size=item.size
                    )
                    size_stock.quantity += item.quantity
                    size_stock.save()
                cart = Cart.objects.get(user=order.user)
                for item in order.items.all():
                    size_stock = ProductSizeStock.objects.get(
                        color_variant=item.color_variant,
                        size=item.size
                    )
                    CartItem.objects.create(
                        cart=cart,
                        product=item.product,
                        color_variant=item.color_variant,
                        size_stock=size_stock,
                        quantity=item.quantity
                    )
            messages.error(request, f"Payment verification failed: {str(e)}")
            failure_url = reverse('payment_failed')
            return JsonResponse({"status": "failed", "redirect_url": failure_url})

        except Exception as e:
            logger.error(f"Payment handler error: {str(e)}", exc_info=True)
            order = get_object_or_404(Order, razorpay_order_id=razorpay_order_id)
            with transaction.atomic():
                order.payment_status = "failed"
                order.status = "cancelled"
                order.save()
                for item in order.items.all():
                    size_stock = ProductSizeStock.objects.get(
                        color_variant=item.color_variant,
                        size=item.size
                    )
                    size_stock.quantity += item.quantity
                    size_stock.save()
                cart = Cart.objects.get(user=order.user)
                for item in order.items.all():
                    size_stock = ProductSizeStock.objects.get(
                        color_variant=item.color_variant,
                        size=item.size
                    )
                    CartItem.objects.create(
                        cart=cart,
                        product=item.product,
                        color_variant=item.color_variant,
                        size_stock=size_stock,
                        quantity=item.quantity
                    )
            messages.error(request, f"Payment processing failed: {str(e)}")
            failure_url = reverse('payment_failed')
            return JsonResponse({"status": "failed", "redirect_url": failure_url})

    logger.warning("Invalid request method for payment_handler")
    return JsonResponse({"status": "failed", "redirect_url": reverse('payment_failed')})




def payment_failed(request):
    return render(request, 'payment_failed.html', {'message': 'Payment failed. Please try again.'})




#-----------------------------OrderManagement------------------------------------#

@login_required
@cache_control(no_store=True, no_cache=True, must_revalidate=True)
@no_cache_view
@never_cache
def order_success(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'order_success.html', {'order': order})


@login_required
@cache_control(no_store=True, no_cache=True, must_revalidate=True)
@never_cache
def orders_list_view(request):
    user = request.user
    query = request.GET.get('q', '').strip()
    sort = request.GET.get('sort', 'latest')
    orders = Order.objects.filter(user=user)
    if query:
        orders = orders.filter(items__product__name__icontains=query).distinct()
    sort_options = {
        'latest': '-created_at',
        'oldest': 'created_at',
        'amount_high': '-total_amount',
        'amount_low': 'total_amount',
    }
    sort_by = sort_options.get(sort, '-created_at')
    orders = orders.order_by(sort_by)
    paginator = Paginator(orders, 5)  
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    context = {
        'orders': page_obj,
        'query': query,
        'sort': sort,
    }
    return render(request, 'orders_list.html', context)



@login_required
@cache_control(no_store=True, no_cache=True, must_revalidate=True)
@never_cache
def download_invoice(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    if order.status == 'cancelled':
        messages.error(request, "Cannot download invoice for a cancelled order.",extra_tags="orders_list")
        return redirect('orders_list')

    all_items = order.items.all()
    active_items = all_items.exclude(status='cancelled')

    if not active_items:
        subtotal = Decimal('0.00')
        adjusted_discount = Decimal('0.00')
        tax = Decimal('0.00')
        total_amount = Decimal('0.00')
    else:
        total_original_amount = sum(Decimal(str(item.product.price)) * item.quantity for item in all_items)
        if total_original_amount == 0:
            total_original_amount = Decimal('0.01')  

        order_discount = order.discount or Decimal('0.00')
        item_discounts = {}
        for item in all_items:
            item_total = Decimal(str(item.product.price)) * item.quantity
            item_discount = (item_total / total_original_amount) * order_discount
            item_discounts[item.id] = item_discount

        subtotal = sum(Decimal(str(item.product.price)) * item.quantity for item in active_items)
        adjusted_discount = sum(item_discounts[item.id] for item in active_items if item.id in item_discounts)
        taxable_amount = subtotal - adjusted_discount
        tax = taxable_amount * Decimal('0.05') 
        total_amount = taxable_amount + tax
    
    context = {
        'order': order,
        'all_items': all_items,  
        'subtotal': subtotal,
        'discount': adjusted_discount,
        'tax': tax,
        'total_amount': total_amount,
    }
    template = get_template('invoice_template.html')
    html = template.render(context)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename=invoice_{order.order_id}.pdf'
    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        messages.error(request, "Error generating invoice PDF. Please try again.")
        return redirect('order_detail', order_id=order.id)

    return response



@login_required
@cache_control(no_store=True, no_cache=True, must_revalidate=True)
@never_cache
def order_detail(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    items = order.items.select_related('product').all()
    subtotal = Decimal('0.00')
    product_discount = Decimal('0.00')
    total_quantity = 0

    for item in items:
        original_price = item.price
        discount_price = item.discount_price if item.discount_price else original_price
        quantity = item.quantity

        item_total = original_price * quantity
        item_discount = (original_price - discount_price) * quantity if discount_price else Decimal('0.00')

        subtotal += item_total
        product_discount += item_discount
        total_quantity += quantity

    shipping_cost = order.shipping_cost
    taxes = order.tax
    final_total = order.total_amount
    coupon_discount = order.coupon_discount

    steps = ["Pending", "Confirmed", "Shipped", "Out for Delivery", "Delivered", "Returned", "Cancelled"]
    status_map = ["pending", "confirmed", "shipped", "out_for_delivery", "delivered", "returned", "cancelled"]
    icons = ["shopping-cart", "truck", "arrow-right-circle", "check-circle", "refresh", "x-circle", "x-circle"]
    current_step = status_map.index(order.status.lower()) if order.status.lower() in status_map else 0

    progress_data = []
    for index in range(len(steps)):
        status = "completed" if index < current_step else "current" if index == current_step else "future"
        progress_data.append({
            'step': steps[index],
            'icon': icons[index],  
            'status': status
        })
    cancellable_statuses = ['pending', 'processing', 'shipped','confirmed']
    context = {
        'order': order,
        'items': items,
        'subtotal': subtotal,
        'product_discount': product_discount,
        'coupon_discount': coupon_discount,
        'tax': taxes,
        'shipping': shipping_cost,
        'grand_total': final_total,
        'total_quantity': total_quantity,
        'progress_data': progress_data,
        'cancellable_statuses': cancellable_statuses,
        'order_status_lower': order.status.lower(),
    }
    return render(request, 'order_detail.html', context)


@cache_control(no_store=True, no_cache=True, must_revalidate=True)
@require_POST
@login_required
@never_cache
def cancel_order(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    item_id = request.POST.get('item_id')
    reason = request.POST.get('reason', '').strip()

    try:
        with transaction.atomic():
            items_to_cancel = []
            if item_id:
                item = get_object_or_404(OrderItem, id=item_id, order=order)
                if item.status == 'active':
                    items_to_cancel.append(item)
                else:
                    messages.error(request, f"Item {item_id} cannot be cancelled: already {item.status}.")
                    return redirect('order_detail', order_id=order.id)
            else:
                items_to_cancel = list(order.items.filter(status='active'))
                if not items_to_cancel:
                    messages.error(request, "No active items to cancel in this order.")
                    return redirect('order_detail', order_id=order.id)

            refund_amount = Decimal('0.00')
            total_net_before_coupon = sum(
                ((oi.discount_price if oi.discount_price else oi.price) * oi.quantity)
                for oi in order.items.all()
            )
            total_after_discounts = order.subtotal - order.discount - order.coupon_discount

            for item in items_to_cancel:
                item.status = 'cancelled'
                item.is_cancelled = True
                item.cancel_reason = reason if reason else None
            
                if order.payment_method in ['wallet', 'razorpay']:
                    item.payment_status = 'refunded'
                item.save()
                logger.info(f"Item {item.id} cancelled for order {order.order_id}")

                if item.color_variant and item.size:
                    try:
                        size_stock = ProductSizeStock.objects.get(color_variant=item.color_variant, size=item.size)
                        initial_quantity = size_stock.quantity
                        size_stock.quantity += item.quantity
                        size_stock.save()
                        logger.info(f"Stock updated for ProductSizeStock {size_stock.id} ({initial_quantity} → {size_stock.quantity})")
                    except ProductSizeStock.DoesNotExist:
                        logger.warning(f"Stock not found for item {item.id} (variant/size missing).")
                        messages.warning(request, f"Item cancelled, but stock not updated: variant/size not found.")
                else:
                    logger.warning(f"Skipping stock update for item {item.id}: missing variant/size data.")

                item_net_before_coupon = (item.discount_price if item.discount_price else item.price) * item.quantity
                item_coupon_share = order.coupon_discount * (item_net_before_coupon / total_net_before_coupon) if total_net_before_coupon > 0 else Decimal('0.00')
                item_effective = item_net_before_coupon - item_coupon_share
                item_tax_share = order.tax * (item_effective / total_after_discounts) if total_after_discounts > 0 else Decimal('0.00')
                refund_amount += item_effective + item_tax_share

            if not order.items.filter(status='active').exists():
                order.status = 'cancelled'
                order.cancelled_at = timezone.now()
                order.cancel_reason = reason if reason else None
                refund_amount += order.shipping_cost
                order.save()
                logger.info(f"Order {order.order_id} status updated to 'cancelled'")
            else:
                order.save()

            if refund_amount > 0 and order.payment_method in ['wallet', 'razorpay']:
                wallet, _ = Wallet.objects.get_or_create(user=order.user)
                txn_id = f"TXN-{uuid.uuid4().hex[:8].upper()}"

                WalletTransaction.objects.create(
                    wallet=wallet,
                    order=order,
                    amount=refund_amount,
                    transaction_type='credit',
                    description=f"Refund for cancellation of {'item' if item_id else 'order'} {order.order_id}",
                    transaction_id=txn_id
                )

                wallet.balance = (wallet.balance or Decimal('0.00')) + refund_amount
                wallet.save()
                formatted_refund_amount = "{:.2f}".format(refund_amount)
                messages.success(request, f"{'Item' if item_id else 'Order'} cancelled and ₹{formatted_refund_amount} refunded to wallet.")
                logger.info(f"Refunded ₹{formatted_refund_amount} to wallet for order {order.order_id}")
            else:
                messages.success(request, f"{'Item' if item_id else 'Order'} cancelled successfully.")

    except Exception as e:
        logger.error(f"Error cancelling order {order.order_id}: {str(e)}")
        messages.error(request, f"Error cancelling {'item' if item_id else 'order'}: {str(e)}")

    return redirect('order_detail', order_id=order.id)


@cache_control(no_store=True, no_cache=True, must_revalidate=True)
@require_POST
@login_required
@never_cache
def return_order(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    item_id = request.POST.get('item_id')
    reason = request.POST.get('reason', '').strip()

    if not reason:
        messages.error(request, "Return reason is required.")
        return redirect('order_detail', order_id=order.id)

    if order.status != 'delivered':
        messages.error(request, "Order must be delivered to request a return.")
        return redirect('order_detail', order_id=order.id)

    try:
        with transaction.atomic():
            if item_id:
                item = get_object_or_404(OrderItem, id=item_id, order=order)
                if item.status == 'active':
                    ReturnRequest.objects.create(order_item=item, user=request.user, reason=reason, status='pending')
                    item.status = 'return_requested'
                    item.is_return_requested = True
                    item.return_reason = reason
                    item.return_requested_at = timezone.now()
                    item.save()
                    logger.info(f"Return request submitted for item {item.id} in order {order.order_id}")
                else:
                    messages.error(request, f"Item {item_id} cannot be returned: already {item.status}.")
                    return redirect('order_detail', order_id=order.id)
            else:
                for item in order.items.filter(status='active'):
                    ReturnRequest.objects.create(order_item=item, user=request.user, reason=reason, status='pending')
                    item.status = 'return_requested'
                    item.is_return_requested = True
                    item.return_reason = reason
                    item.return_requested_at = timezone.now()
                    item.save()
                    logger.info(f"Return request submitted for item {item.id} in order {order.order_id}")

            messages.success(request, "Return request submitted for verification.")

    except Exception as e:
        logger.error(f"Error submitting return request for order {order.order_id}: {str(e)}")
        messages.error(request, f"Error submitting return request: {str(e)}")
        return redirect('order_detail', order_id=order.id)

    return redirect('order_detail', order_id=order.id)


def process_return_request(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    if order.payment_status == "Paid" and order.return_status == "Accepted":
        wallet, created = Wallet.objects.get_or_create(user=order.user)
        refund_amount = Decimal(order.total_price)
        wallet.balance += refund_amount
        wallet.save()
        unique_txn_id = f"TXN-{uuid.uuid4().hex[:8].upper()}"

        WalletTransaction.objects.create(
            wallet=wallet,
            order=order,
            amount=refund_amount,
            transaction_type="credit",
            description="Refund for returned order",
            transaction_id=unique_txn_id
        )

        order.payment_status = "Refunded"
        order.save()

        messages.success(request, f"₹{refund_amount} has been refunded to your wallet.")
    else:
        messages.error(request, "Return request is not eligible for refund.")

    return redirect("wallet_page")




@login_required
@cache_control(no_store=True, no_cache=True, must_revalidate=True)
@never_cache
def wallet_page(request):
    wallet, created = Wallet.objects.get_or_create(user=request.user)
    transactions = wallet.transactions.all().order_by('-created_at')
    paginator = Paginator(transactions, 8) 
    page_number = request.GET.get('page')
    try:
        transactions_page = paginator.get_page(page_number)
    except PageNotAnInteger:
        transactions_page = paginator.page(1)
    except EmptyPage:
        transactions_page = paginator.page(paginator.num_pages)

    return render(request, "wallet.html", {
        "wallet": wallet,
        "transactions": transactions_page,  
    })




@login_required
@cache_control(no_store=True, no_cache=True, must_revalidate=True)
@never_cache
def change_password(request):
    if SocialAccount.objects.filter(user=request.user, provider='google').exists():
        return render(request, "change_password.html", {"is_google_user": True})

    if request.method == "POST":
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  
            messages.success(request, "Password updated successfully.")
            return redirect('change_password')  
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = PasswordChangeForm(request.user)

    return render(request, "change_password.html", {"form": form, "is_google_user": False})


# -----------------Referral view---------------------------------#

@login_required
def referral_view(request):
    referrals = request.user.referrals.all().order_by('-date_joined')
    context = {
        'referrals': referrals,
    }
    return render(request, 'referral.html', context)


@login_required
def apply_referral(request):
    if request.method == 'POST':
        referral_code = request.POST.get('referral_code')
        user = request.user

        if user.referred_by:
            messages.error(request, 'You have already used a referral code.')
            return redirect('user_home')

        try:
            referrer = CustomUser.objects.get(referral_code=referral_code)
            if referrer == user:
                messages.error(request, 'You cannot use your own referral code.')
                return redirect('user_home')
        except CustomUser.DoesNotExist:
            messages.error(request, 'Invalid referral code.')
            return redirect('user_home')

        try:
            with transaction.atomic():
                user.referred_by = referrer
                user.save()
                referee_wallet, _ = Wallet.objects.get_or_create(user=user)
                referee_wallet.balance += 100
                referee_wallet.save()

                WalletTransaction.objects.create(
                    wallet=referee_wallet,
                    transaction_id=f"TXN-{uuid.uuid4().hex[:8].upper()}",
                    amount=100,
                    transaction_type='credit',
                    description=f"Referral reward from {referrer.username}"
                )

                referrer_wallet, _ = Wallet.objects.get_or_create(user=referrer)
                referrer_wallet.balance += 100
                referrer_wallet.save()

                WalletTransaction.objects.create(
                    wallet=referrer_wallet,
                    transaction_id=f"TXN-{uuid.uuid4().hex[:8].upper()}",
                    amount=100,
                    transaction_type='credit',
                    description=f"Referral reward for inviting {user.username}"
                )

                messages.success(request, 'Referral applied! ₹100 credited to your wallet.')
                return redirect('user_home')
        except Exception as e:
            messages.error(request, f'Error applying referral: {str(e)}')
            return redirect('user_home')

    messages.error(request, 'Invalid request method.')
    return redirect('user_home')
    