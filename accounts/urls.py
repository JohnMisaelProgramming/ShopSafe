from django.urls import path
from accounts import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('verify-2fa/', views.verify_2fa_view, name='verify_2fa'),
    path('resend-otp/', views.resend_otp_view, name='resend_otp'),
    path('forgot-password/', views.forgot_password_view, name='forgot_password'),
]
