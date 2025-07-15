from django.shortcuts import render, redirect
from django.contrib.auth import get_user_model, authenticate, login, logout
from django.contrib.auth.hashers import make_password
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.conf import settings
from django.db import transaction, IntegrityError
from django.contrib.auth import BACKEND_SESSION_KEY
import random
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.contrib import messages
from adminapp.models import Product,Category, Brand
from userapp.models import CustomUser
import re
from django.views.decorators.cache import never_cache
from .utils import no_cache_view

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
    products = Product.objects.filter(is_active=True, is_deleted=False)
    query = request.GET.get('search', '').strip()
    if query:
        products = products.filter(Q(name__icontains=query) | Q(description__icontains=query))
    category_ids = request.GET.getlist('category')
    brand_id = request.GET.get('brand')
    size_list = request.GET.getlist('size')
    color_list = request.GET.getlist('color')
    price_max = request.GET.get('price_max')

    if category_ids:
        products = products.filter(category__id__in=category_ids)
    if brand_id:
        products = products.filter(brand__id=brand_id)
    if size_list:
        products = products.filter(size_stocks__size__in=size_list)
    if color_list:
        products = products.filter(colors__name__in=color_list)

    if price_max:
        try:
            products = products.filter(price__lte=float(price_max))
        except ValueError:
            pass  
   
    sort_by = request.GET.get('sort')
    if sort_by == 'price_asc':
        products = products.order_by('price')
    elif sort_by == 'price_desc':
        products = products.order_by('-price')
    elif sort_by == 'name_asc':
        products = products.order_by('name')
    elif sort_by == 'name_desc':
        products = products.order_by('-name')
    paginator = Paginator(products, 8)  
    page_number = request.GET.get('page')
    products_page = paginator.get_page(page_number)
    categories = Category.objects.filter(is_deleted=False, is_active=True)
    brands = Brand.objects.filter(is_deleted=False, is_active=True)
    colors = ['Red', 'Blue', 'Green', 'Black', 'White']  
    sizes = ['S', 'M', 'L']  
    context = {
        'products': products_page,
        'categories': categories,
        'brands': brands,
        'colors': colors,
        'sizes': sizes,

        'query': query,
        'selected_categories': category_ids,
        'selected_brand': brand_id,
        'selected_sizes': size_list,
        'selected_colors': color_list,
        'price_max': price_max,
        'sort_by': sort_by,
    }

    return render(request, 'user_product_list.html', context)



@login_required(login_url='user_login')
def product_detail(request, product_id):
    try:
        product = Product.objects.get(id=product_id)
        if not product.is_active or product.is_deleted:
            return redirect('userproduct_list')
    except Product.DoesNotExist:
        return redirect('userproduct_list')
    color = product.colors.first()  
    related_products = Product.objects.filter(
        category=product.category,
        is_active=True,
        is_deleted=False
    ).exclude(id=product.id)[:4]

    return render(request, 'product_detail.html', {
        'product': product,
        'color': color,
        'related_products': related_products,
    })
