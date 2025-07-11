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


]
