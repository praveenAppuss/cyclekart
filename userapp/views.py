from django.utils import timezone
from django.views.decorators.cache import cache_control
from .otp import generate_otp, send_otp_email
from decimal import Decimal
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
from django.db.models.functions import Coalesce
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404
from django.contrib.messages import get_messages
from django.contrib import messages
from adminapp.models import Product,Category,Brand,ProductSizeStock,ProductColorVariant
from userapp.models import CustomUser,Address,Cart,CartItem, ReturnRequest,Wishlist,Order,OrderItem,Wallet,WalletTransaction
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


@never_cache
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

    query = request.GET.get('search', '').strip()
    if query:
        products = products.filter(
            Q(name__icontains=query) | Q(description__icontains=query)
        ).distinct()

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
        'savings': savings,
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
            next_url = request.GET.get('next', 'address_list')
            return redirect(next_url)  
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
            next_url = request.GET.get('next', 'address_list')
            return redirect(next_url)  
    return redirect('address_list')


@login_required(login_url='user_login')
@cache_control(no_store=True, no_cache=True, must_revalidate=True)
@never_cache
def delete_address(request, pk):
    address = get_object_or_404(Address, pk=pk, user=request.user)
    address.delete()
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

    return redirect('cart_view')


def get_sizes(request, color_variant_id):
    size_stocks = ProductSizeStock.objects.filter(color_variant_id=color_variant_id).values('id', 'size')
    sizes = [{'id': ss['id'], 'size_display': dict(ProductSizeStock.SIZE_CHOICES).get(ss['size'], ss['size'])} for ss in size_stocks]
    return JsonResponse({'sizes': sizes})


@login_required(login_url='user_login')
@cache_control(no_store=True, no_cache=True, must_revalidate=True)
@no_cache_view
@never_cache
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
    TAX_RATE = Decimal('0.05')  

    for item in cart_items:
        item.subtotal = item.quantity * item.product.price
        total_subtotal += item.subtotal
        item.color_variant = item.color_variant
        item.image = item.color_variant.images.first().image.url if item.color_variant.images.exists() else item.product.thumbnail.url if item.product.thumbnail else ''
        item.size_stock = item.size_stock
        item.stock = item.size_stock.quantity
        item.max_quantity = min(item.stock, 5)
        item.size_display = item.size_stock.get_size_display()

        if (item.product.is_deleted or not item.product.is_active or 
            item.product.category.is_deleted or not item.product.category.is_active or 
            item.quantity > item.stock):
            has_unavailable_items = True
            item.is_available = False
        else:
            item.is_available = True

        if item.product.discount_price and item.product.discount_price < item.product.price:
            item_savings = (item.product.price - item.product.discount_price) * item.quantity
            item.savings = item_savings
            total_discount += item.savings
        else:
            item.savings = Decimal('0')

    taxes = total_subtotal * TAX_RATE
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
@cache_control(no_store=True, no_cache=True, must_revalidate=True)
@never_cache
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
        subtotal = new_quantity * cart_item.product.price
        savings = (cart_item.product.price - (cart_item.product.discount_price or cart_item.product.price)) * new_quantity if cart_item.product.discount_price and cart_item.product.discount_price < cart_item.product.price else Decimal('0')
        cart = cart_item.cart
        cart_items = cart.items.select_related('product', 'size_stock').all()
        new_cart_total = sum(item.quantity * item.product.price for item in cart_items)  
        new_total_discount = sum((item.product.price - (item.product.discount_price or item.product.price)) * item.quantity for item in cart_items if item.product.discount_price and item.product.discount_price < item.product.price)
        new_taxes = new_cart_total * Decimal('0.05')
        new_total = new_cart_total + new_taxes - new_total_discount

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            storage = get_messages(request)
            message = storage._queued_messages[-1].message if storage._queued_messages else ''
            return JsonResponse({
                'success': True,
                'quantity': new_quantity,
                'subtotal': float(subtotal),
                'savings': float(savings),
                'cart_total': float(new_cart_total),
                'total_discount': float(new_total_discount),
                'taxes': float(new_taxes),
                'total': float(new_total),
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

    subtotal = 0
    total_discount = 0
    total_quantity = 0

    for item in cart_items:
        original_price = item.product.price
        discount_price = item.product.discount_price if item.product.discount_price and item.product.discount_price < original_price else original_price
        quantity = item.quantity

        item_total = original_price * quantity
        item_discount = (original_price - discount_price) * quantity

        subtotal += item_total
        total_discount += item_discount
        total_quantity += quantity

    shipping_cost = 0  
    taxes = subtotal * Decimal('0.05')  
    final_total = subtotal - total_discount + shipping_cost + taxes

    context = {
        'addresses': addresses,
        'default_address': default_address,
        'cart_items': cart_items,
        'subtotal': subtotal,
        'total_discount': total_discount,
        'shipping_cost': shipping_cost,
        'final_total': final_total,
        'total_quantity': total_quantity,
        'taxes': taxes,
    }

    return render(request, 'checkout.html', context)




@login_required
@never_cache
@cache_control(no_store=True, no_cache=True, must_revalidate=True)
def place_order(request):
    if request.method == 'POST':

        address_id = request.POST.get('selected_address')
        payment_method = request.POST.get('payment_method')
        logger.debug(f"Form data: selected_address={address_id}, payment_method={payment_method}")

        if not address_id or not payment_method:
            messages.error(request, "Please select address and payment method.")
            logger.error("Missing address_id or payment_method")
            return redirect('checkout')

        address = get_object_or_404(Address, id=address_id, user=request.user)
        logger.debug(f"Address found: {address}")
        cart = get_object_or_404(Cart, user=request.user)
        cart_items = CartItem.objects.filter(cart=cart)
        logger.debug(f"Cart items: {[(item.product.name, item.size_stock.size, item.quantity) for item in cart_items]}")
        if not cart_items.exists():
            messages.error(request, "Your cart is empty.")
            logger.error("Cart is empty")
            return redirect('cart_view')
        subtotal = Decimal('0.00')
        discount = Decimal('0.00')
        for item in cart_items:
            original_price = item.product.price
            item_discount_price = item.product.discount_price or original_price
            subtotal += original_price * item.quantity
            discount += (original_price - item_discount_price) * item.quantity

        tax_rate = Decimal('0.05')  
        tax = subtotal * tax_rate
        shipping_cost = Decimal('0.00')  
        total_amount = (subtotal - discount) + tax + shipping_cost
        logger.debug(f"Calculated: subtotal={subtotal}, discount={discount}, tax={tax}, shipping={shipping_cost}, total={total_amount}")
        if payment_method == 'cod' and total_amount > Decimal('100000'):
            messages.error(request, "Cash on Delivery not available for orders above ₹100000.")
            logger.error("COD not allowed for total > ₹100000")
            return redirect('checkout')

        for item in cart_items:
            size_stock = item.size_stock
            logger.debug(f"Stock check for {item.product.name} (Size {size_stock.size}): {size_stock.quantity}")
            if size_stock.quantity < item.quantity:
                messages.error(request, f"Insufficient stock for {item.product.name} (Size {size_stock.size}). Available: {size_stock.quantity}")
                logger.error(f"Insufficient stock for {item.product.name} (Size {size_stock.size}): {size_stock.quantity} < {item.quantity}")
                return redirect('cart_view')

        try:
            with transaction.atomic():
                unique_order_id = f"ORDER-{uuid.uuid4().hex[:8].upper()}"
                logger.debug(f"Generated order_id: {unique_order_id}")
                order = Order.objects.create(
                    user=request.user,
                    address=address,
                    payment_method=payment_method,
                    order_id=unique_order_id,
                    subtotal=subtotal,
                    discount=discount,
                    tax=tax,
                    shipping_cost=shipping_cost,
                    total_amount=total_amount,
                    status='pending'
                )
                logger.debug(f"Order created: {order.order_id}")
                for item in cart_items:
                    size_stock = item.size_stock
                    logger.debug(f"Reducing stock for {item.product.name} (Size {size_stock.size}): {size_stock.quantity} -> {size_stock.quantity - item.quantity}")
                    size_stock.quantity -= item.quantity
                    size_stock.save()
                    OrderItem.objects.create(
                        order=order,
                        product=item.product,
                        color_variant=item.color_variant,  
                        size=size_stock.size,
                        quantity=item.quantity,
                        price=item.product.discount_price or item.product.price,
                        discount_price=item.product.discount_price  
                    )
                    logger.debug(f"OrderItem created for {item.product.name} (Color: {item.color_variant}, Size: {size_stock.size}, Qty: {item.quantity})")

                cart_items.delete()
                logger.debug("Cart cleared")

                return redirect('order_success', order_id=order.id)
        except Exception as e:
            logger.error(f"Order creation failed: {str(e)}", exc_info=True)
            messages.error(request, f"An error occurred while placing the order: {str(e)}")
            return redirect('checkout')
    return redirect('checkout')



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
    try:
        order = Order.objects.get(id=order_id, user=request.user)
        if order.status == 'cancelled':
            return HttpResponse("Cannot download invoice for cancelled order", status=400)
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
        return HttpResponse('Error generating invoice PDF', status=500)
    return response

@login_required
@cache_control(no_store=True, no_cache=True, must_revalidate=True)
@never_cache
def order_detail(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    items = order.items.select_related('product').all()
    subtotal = Decimal('0.00')
    total_discount = Decimal('0.00')
    total_quantity = 0

    for item in items:
        original_price = item.price
        discount_price = item.discount_price if item.discount_price else original_price
        quantity = item.quantity

        item_total = original_price * quantity
        item_discount = (original_price - discount_price) * quantity if discount_price else Decimal('0.00')

        subtotal += item_total
        total_discount += item_discount
        total_quantity += quantity

    
    shipping_cost = order.shipping_cost
    taxes = order.tax
    final_total = order.total_amount

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

    context = {
        'order': order,
        'items': items,
        'subtotal': order.subtotal,
        'discount': order.discount,
        'tax': taxes,
        'shipping': shipping_cost,
        'grand_total': final_total,
        'total_quantity': total_quantity,
        'progress_data': progress_data,
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
            for item in items_to_cancel:
                item.status = 'cancelled'
                item.is_cancelled = True
                item.cancel_reason = reason if reason else None
                item.save()
                logger.info(f"Item {item.id} status updated to 'cancelled' for order {order.order_id}")

                if item.color_variant and item.size:
                    try:
                        size_stock = ProductSizeStock.objects.get(color_variant=item.color_variant, size=item.size)
                        initial_quantity = size_stock.quantity
                        size_stock.quantity += item.quantity
                        size_stock.save()
                        logger.info(f"Stock adjusted for ProductSizeStock {size_stock.id} (from {initial_quantity} to {size_stock.quantity})")
                    except ProductSizeStock.DoesNotExist:
                        logger.error(f"ProductSizeStock not found for item {item.id} (color_variant: {item.color_variant}, size: {item.size})")
                        messages.warning(request, f"Item cancelled, but stock not updated: variant/size not found.")
                    except Exception as e:
                        logger.error(f"Stock adjustment failed for item {item.id}: {str(e)}")
                        messages.warning(request, f"Item cancelled, but stock adjustment failed.")
                else:
                    logger.warning(f"Skipping stock update for item {item.id}: color_variant={item.color_variant}, size={item.size}")
                    messages.warning(request, f"Item cancelled, but stock not updated: missing variant/size data.")

                refund_amount += (item.discount_price or item.price) * item.quantity

            if not order.items.filter(status='active').exists():
                order.status = 'cancelled'
                order.cancelled_at = timezone.now()
                order.cancel_reason = reason if reason else None
                order.save()
                logger.info(f"Order {order.order_id} status updated to 'cancelled'")

            if refund_amount > 0 and order.payment_method != 'cod':
                try:
                    wallet = order.user.wallet
                    WalletService.add_balance(wallet, refund_amount, f"Refund for Order {order.order_id}", order)
                    if order.payment_status == 'paid':
                        order.payment_status = 'pending'  
                        order.save()
                    messages.success(request, f"{'Item' if item_id else 'Order'} cancelled and ₹{refund_amount} refunded.")
                except Exception as e:
                    logger.error(f"Refund failed for order {order.order_id}: {str(e)}")
                    messages.warning(request, f"{'Item' if item_id else 'Order'} cancelled, but refund failed.")
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

            if order.items.filter(status='return_requested').exists() and order.status not in ['returned', 'cancelled']:
                order.status = 'return request'  
                order.save()
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

        WalletTransaction.objects.create(
            wallet=wallet,
            order=order,
            amount=refund_amount,
            transaction_type="credit",
            description="Refund for returned order"
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
    return render(request, "wallet.html", {"wallet": wallet, "transactions": transactions})




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