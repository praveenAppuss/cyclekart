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

from adminapp.models import Product,Category, Brand


User = get_user_model()


# User Signup View
def user_signup(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        mobile = request.POST.get('mobile', '').strip()
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')
        errors = {}

        if not username:
            errors['username'] = "Username is required."
        if not email:
            errors['email'] = "Email is required."
        elif User.objects.filter(email=email).exists():
            errors['email'] = "Email already exists."
        if not mobile:
            errors['mobile'] = "Mobile number is required."
        if not password:
            errors['password'] = "Password is required."
        if password != confirm_password:
            errors['confirm_password'] = "Passwords do not match."

        if errors:
            return render(request, 'user_signup.html', {
                'errors': errors,
                'username': username,
                'email': email,
                'mobile': mobile
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



def verify_otp(request):
    if request.method == 'POST':
        entered_otp = request.POST.get('otp')
        session_otp = request.session.get('otp')
        signup_data = request.session.get('signup_data')

        if entered_otp == session_otp and signup_data:
            email = signup_data['email']
            username = signup_data['username']
            mobile = signup_data['mobile']
            password = signup_data['password']

            user = User.objects.filter(email=email).first()

            # If user exists already
            if user:
                # If mobile is already set and different => throw error
                if user.mobile and user.mobile != mobile:
                    return render(request, 'verify_otp.html', {
                        'error': 'This email is already linked to a different mobile number.'
                    })
                # If same mobile or mobile not set, continue safely
                if not user.mobile:
                    user.mobile = mobile
                if not user.username:
                    user.username = username
                if not user.password:
                    user.password = password
            else:
                # Create new user
                user = User(
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




# User Login View
def user_login(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        errors = {}

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            errors['email'] = "Email not found."
            return render(request, 'user_login.html', {'errors': errors})

        if not user.check_password(password):
            errors['password'] = "Incorrect password."
            return render(request, 'user_login.html', {'errors': errors})

        if hasattr(user, 'is_blocked') and user.is_blocked:
            errors['email'] = "Your account is blocked."
            return render(request, 'user_login.html', {'errors': errors})

        if not user.is_active:
            otp = str(random.randint(100000, 999999))
            request.session['otp'] = otp
            request.session['signup_data'] = {
                'email': email,
                'username': user.username,
                'mobile': user.mobile,
                'password': user.password,
            }

            send_mail(
                subject='CycleKart - Email Verification',
                message=f'Your OTP is: {otp}',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )
            return redirect('verify_otp')

        # ✅ Fix the ValueError by specifying backend explicitly
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        return redirect('user_home')

    return render(request, 'user_login.html')

# Resend OTP View
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

# Logout View
def user_logout(request):
    logout(request)
    return redirect('user_login')

# Home View


@login_required(login_url='user_login')
def user_home(request):
    all_products = list(Product.objects.filter(is_active=True, is_deleted=False))
    featured_products = random.sample(all_products, min(len(all_products), 4))  # Picks 4 or less
    return render(request, 'user_home.html', {'featured_products': featured_products})






@login_required(login_url='user_login')
def user_product_list(request):
    products = Product.objects.filter(is_active=True, is_deleted=False)

    # --- SEARCH ---
    query = request.GET.get('search', '').strip()
    if query:
        products = products.filter(Q(name__icontains=query) | Q(description__icontains=query))

    # --- FILTERS ---
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
            pass  # Invalid number input, ignore

    # --- SORTING ---
    sort_by = request.GET.get('sort')
    if sort_by == 'price_asc':
        products = products.order_by('price')
    elif sort_by == 'price_desc':
        products = products.order_by('-price')
    elif sort_by == 'name_asc':
        products = products.order_by('name')
    elif sort_by == 'name_desc':
        products = products.order_by('-name')

    # --- PAGINATION ---
    paginator = Paginator(products, 2)  # Adjust products per page as needed
    page_number = request.GET.get('page')
    products_page = paginator.get_page(page_number)

    # --- FILTER OPTIONS ---
    categories = Category.objects.filter(is_deleted=False, is_active=True)
    brands = Brand.objects.filter(is_deleted=False, is_active=True)
    colors = ['Red', 'Blue', 'Green', 'Black', 'White']  # Customize if dynamic
    sizes = ['S', 'M', 'L']  # Customize if needed

    context = {
        'products': products_page,
        'categories': categories,
        'brands': brands,
        'colors': colors,
        'sizes': sizes,

        # Persist selections
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

    # Related products logic
    related_products = Product.objects.filter(
        category=product.category,
        is_active=True,
        is_deleted=False
    ).exclude(id=product.id)[:4]

    return render(request, 'product_detail.html', {
        'product': product,
        'related_products': related_products,
    })
