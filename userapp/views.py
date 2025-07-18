from decimal import Decimal
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
from adminapp.models import Product,Category,Brand,ProductSizeStock
from userapp.models import CustomUser,Address,Cart,CartItem,Wishlist,Order,OrderItem
import re
from django.views.decorators.cache import never_cache
from .utils import no_cache_view,calculate_cart_total

from .forms import AddressForm
import json
from django.utils.safestring import mark_safe

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

    savings = 0
    if product.discount_price and product.discount_price < product.price:
        savings = product.price - product.discount_price

    return render(request, 'product_detail.html', {
        'product': product,
        'color': color,
        'related_products': related_products,
        'savings':savings
    })



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
@login_required
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    # Check if product or category is unavailable
    if not product.is_active or product.is_deleted or not product.category.is_active or product.category.is_deleted:
        messages.error(request, "This product is unavailable.")
        return redirect('product_detail', product_id=product.id)

    size = request.POST.get('size')
    quantity = request.POST.get('quantity', 1)  # Default to 1 if not provided
    try:
        quantity = int(quantity)
    except (ValueError, TypeError):
        messages.error(request, "Invalid quantity.")
        return redirect('product_detail', product_id=product.id)

    try:
        stock_entry = ProductSizeStock.objects.get(product=product, size=size)
    except ProductSizeStock.DoesNotExist:
        messages.error(request, "Invalid size selected.")
        return redirect('product_detail', product_id=product.id)

    if stock_entry.quantity < 1:
        messages.warning(request, f"Size {size} is out of stock.")
        return redirect('product_detail', product_id=product.id)

    max_quantity = min(stock_entry.quantity, 5)  # Limit to 5 or stock, whichever is lower
    if quantity < 1 or quantity > max_quantity:
        messages.warning(request, f"Quantity must be between 1 and {max_quantity}.")
        return redirect('product_detail', product_id=product.id)

    cart, _ = Cart.objects.get_or_create(user=request.user)

    cart_item, created = CartItem.objects.get_or_create(
        cart=cart,
        product=product,
        size=size,
        defaults={'quantity': quantity}
    )

    if not created:
        new_quantity = min(cart_item.quantity + quantity, max_quantity)
        if new_quantity > max_quantity:
            messages.warning(request, f"Cannot add more. Max limit is {max_quantity}.")
        else:
            cart_item.quantity = new_quantity
            cart_item.save()
            messages.success(request, f"{product.name} quantity updated in cart.")
    else:
        cart_item.quantity = quantity
        cart_item.save()
        messages.success(request, f"{product.name} added to cart.")

    # Remove from wishlist if exists
    Wishlist.objects.filter(user=request.user, product=product).delete()
    return redirect('product_detail',product_id=product_id)

@login_required(login_url='user_login')
def cart_view(request):
    cart = Cart.objects.filter(user=request.user).first()
    cart_items = cart.items.select_related('product') if cart else []

    total_subtotal = 0
    total_discount = 0
    has_unavailable_items = False
    taxes = 0
    discount = 0  # Will be calculated as total_discount

    for item in cart_items:
        # Calculate subtotal for each item
        item.subtotal = item.quantity * item.product.price
        total_subtotal += item.subtotal

        try:
            stock_record = ProductSizeStock.objects.get(product=item.product, size=item.size)
            item.stock = stock_record.quantity
            item.max_quantity = min(item.stock, 5)  # Max 5 items
            # Check availability
            if (item.product.is_deleted or not item.product.is_active or 
                not item.product.category.is_active or item.quantity > item.stock):
                has_unavailable_items = True
        except ProductSizeStock.DoesNotExist:
            has_unavailable_items = True
            item.stock = 0
            item.max_quantity = 0

        # Calculate savings (discount) for each item
        if hasattr(item.product, 'discount_price') and item.product.discount_price is not None:
            item_savings = item.product.price - item.product.discount_price if item.product.discount_price < item.product.price else 0
            item.savings = item_savings * item.quantity  # Total savings for this item's quantity
            total_discount += item.savings
        else:
            item.savings = 0

    # Calculate taxes (5% of subtotal as per example ₹190 on ₹4000)
    taxes = total_subtotal * Decimal('0.05')  # Convert 0.05 to Decimal
    # Calculate total (subtotal + taxes - total_discount)
    final_total = total_subtotal + taxes - total_discount

    return render(request, 'cart.html', {
        'cart_items': cart_items,
        'cart_total': total_subtotal,  # Subtotal
        'total_discount': total_discount,  # Total savings across all items
        'taxes': taxes,
        'total': final_total,
        'has_unavailable_items': has_unavailable_items,
    })

@login_required
def update_cart_quantity(request, cart_item_id):
    cart_item = get_object_or_404(CartItem, id=cart_item_id, cart__user=request.user)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        try:
            stock_entry = ProductSizeStock.objects.get(product=cart_item.product, size=cart_item.size)
            max_quantity = min(stock_entry.quantity, 5)  # Max 5 items
        except ProductSizeStock.DoesNotExist:
            messages.error(request, "Selected size stock not found.")
            return redirect('cart_view')

        if action == 'increment' and cart_item.quantity < max_quantity:
            cart_item.quantity += 1
            messages.success(request, f"Quantity updated for {cart_item.product.name}.")
        elif action == 'decrement' and cart_item.quantity > 1:
            cart_item.quantity -= 1
            messages.success(request, f"Quantity updated for {cart_item.product.name}.")
        else:
            messages.warning(request, f"Cannot update quantity. Max limit: {max_quantity} or minimum reached.")

        cart_item.save()
    return redirect('cart_view')

@login_required
def remove_from_cart(request, cart_item_id):
    cart_item = get_object_or_404(CartItem, id=cart_item_id, cart__user=request.user)
    product_name = cart_item.product.name
    cart_item.delete()
    messages.success(request, f"{product_name} removed from cart.")
    return redirect('cart_view')

# Wishlist Management
@login_required
def wishlist_view(request):
    wishlist_items = Wishlist.objects.filter(user=request.user).select_related('product')
    sizes = ProductSizeStock.objects.filter(
        product__in=[item.product for item in wishlist_items]
    ).values('product_id', 'size', 'quantity')
    size_map = {}
    for item in sizes:
        if item['quantity'] > 0:  # Only include sizes with stock
            size_map.setdefault(item['product_id'], []).append(item['size'])

    return render(request, 'wishlist.html', {
        'wishlist_items': wishlist_items,
        'sizes': size_map,  # Ensure this is passed even if empty
    })

@login_required
def add_to_wishlist(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    if not product.is_active or not product.category.is_active or product.is_deleted or product.category.is_deleted:
        messages.error(request, "This product is unavailable.")
        return redirect('product_detail', product_id=product.id)

    wishlist_item, created = Wishlist.objects.get_or_create(user=request.user, product=product)
    if created:
        messages.success(request, f"{product.name} added to wishlist.")
    else:
        messages.info(request, f"{product.name} is already in your wishlist.")
    return redirect('product_detail',product_id=product_id)

@login_required
def remove_from_wishlist(request, wishlist_id):
    item = get_object_or_404(Wishlist, id=wishlist_id, user=request.user)
    product_name = item.product.name
    item.delete()
    messages.success(request, f"{product_name} removed from wishlist.")
    return redirect('wishlist_view')

@login_required
def add_to_cart_from_wishlist(request):
    if request.method == 'POST':
        product_id = request.POST.get('product_id')
        size = request.POST.get('size')
        product = get_object_or_404(Product, id=product_id)

        # Check product/category availability
        if not product.is_active or not product.category.is_active or product.is_deleted or product.category.is_deleted:
            messages.error(request, "This product is unavailable.")
            return redirect('wishlist_view')

        # Validate size
        if not size:
            messages.error(request, "Please select a size.")
            return redirect('wishlist_view')

        # Check stock availability
        try:
            stock_entry = ProductSizeStock.objects.get(product=product, size=size)
            if stock_entry.quantity < 1:
                messages.warning(request, f"Size {size} is out of stock.")
                return redirect('wishlist_view')
        except ProductSizeStock.DoesNotExist:
            messages.error(request, "Invalid size selected.")
            return redirect('wishlist_view')

        # Add to cart
        cart, _ = Cart.objects.get_or_create(user=request.user)
        max_quantity = min(stock_entry.quantity, 5)  # Max 5 items per product
        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            product=product,
            size=size,
            defaults={'quantity': 1}
        )

        if not created:
            if cart_item.quantity < max_quantity:
                cart_item.quantity += 1
                cart_item.save()
                messages.success(request, f"{product.name} quantity updated in cart.")
            else:
                messages.warning(request, f"Cannot add more. Only {stock_entry.quantity} left or max limit reached.")
                return redirect('wishlist_view')
        else:
            cart_item.save()
            messages.success(request, f"{product.name} added to cart.")

        # Remove from wishlist
        Wishlist.objects.filter(user=request.user, product=product).delete()
        return redirect('cart_view')

    return redirect('wishlist_view')


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

    shipping_cost = 0  # Free shipping logic can be modified later
    taxes = subtotal * Decimal('0.05')  # Convert 0.05 to Decimal
    # Calculate total (subtotal + taxes - total_discount)
    final_total = subtotal + taxes - total_discount
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



@login_required
def place_order(request):
    if request.method == 'POST':
        address_id = request.POST.get('address_id')
        payment_method = request.POST.get('payment_method')

        if not address_id or not payment_method:
            messages.error(request, "Please select address and payment method.")
            return redirect('checkout')

        address = get_object_or_404(Address, id=address_id, user=request.user)
        cart_items = CartItem.objects.filter(user=request.user)

        if not cart_items.exists():
            messages.error(request, "Your cart is empty.")
            return redirect('cart')

        # Create Order
        order = Order.objects.create(
            user=request.user,
            address=address,
            payment_method=payment_method,
            total_amount=calculate_cart_total(cart_items),  # Create this helper if needed
            status='Order Placed'
        )

        # Create OrderItems
        for item in cart_items:
            OrderItem.objects.create(
                order=order,
                product=item.product,
                quantity=item.quantity,
                price=item.product.price
            )
            # Optionally decrease stock

        # Clear cart
        cart_items.delete()

        return redirect('order_success', order_id=order.id)
    

@login_required
def order_success(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'order_success.html', {'order': order})
