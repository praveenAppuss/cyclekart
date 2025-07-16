from django.urls import path
from . import views

urlpatterns = [
    path('', views.user_signup, name='user_signup'),
    path('login/', views.user_login, name='user_login'),
    path('logout/', views.user_logout, name='user_logout'),
    path('verify-otp/', views.verify_otp, name='verify_otp'),
    path('resend-otp/', views.resend_otp, name='resend_otp'),  
    path('home/', views.user_home, name='user_home'),
    path('userproducts/', views.user_product_list, name='userproduct_list'),
    path('product/<int:product_id>/', views.product_detail, name='product_detail'),
    path('profile/', views.profile_view, name='profile'),
    path('upload_profile_image/',views.upload_profile_image,name='upload_profile_image'),
    path('update-profile/', views.update_profile, name='update_profile'),
    path('addresses/', views.address_list, name='address_list'),
    path('addresses/add/', views.add_address, name='add_address'),
    path('addresses/update/<int:pk>/', views.update_address, name='update_address'),
    path('addresses/delete/<int:pk>/', views.delete_address, name='delete_address'),
    path('cart/',views.cart_view, name='cart_view'),
    path('cart/add/<int:product_id>/',views.add_to_cart, name='add_to_cart'),
    path('cart/update/<int:cart_item_id>/',views.update_cart_quantity, name='update_cart_quantity'),
    path('cart/remove/<int:cart_item_id>/',views.remove_from_cart, name='remove_from_cart'),
    path('wishlist/', views.wishlist_view, name='wishlist_view'),
    path('wishlist/add/<int:product_id>/', views.add_to_wishlist, name='add_to_wishlist'),
    path('wishlist/remove/<int:wishlist_id>/', views.remove_from_wishlist, name='remove_from_wishlist'),
    path('wishlist/add-to-cart/', views.add_to_cart_from_wishlist, name='add_to_cart_from_wishlist'),




]
