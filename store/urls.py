from django.urls import path
from . import views

urlpatterns = [
    # Core pages
    path('', views.home, name='home'),
    path('products/', views.products_list, name='products'),
    path('products/<int:pk>/', views.product_detail, name='product_detail'),
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),
    
    # Advanced Search
    path('search/', views.search, name='search'),
    path('search/suggest/', views.search_suggest, name='search_suggest'),
    
    # Checkout and Flash Sales
    path('flash-sales/', views.flash_sales_list, name='flash_sales'),
    path('checkout/', views.checkout_view, name='checkout'),
    path('checkout/coupon/', views.apply_coupon, name='apply_coupon'),
    
    # Order Tracking
    path('tracking/', views.order_tracking_view, name='order_tracking'),
    
    # Dashboard and Wishlist
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('dashboard/wishlist/toggle/<int:product_id>/', views.toggle_wishlist, name='toggle_wishlist'),
    path('dashboard/address/add/', views.add_address, name='add_address'),
    path('dashboard/address/delete/<int:pk>/', views.delete_address, name='delete_address'),
    path('dashboard/notifications/read-all/', views.mark_notifications_read, name='mark_notifications_read'),
    
    # Administrative Analytics
    path('admin-dashboard/', views.admin_dashboard_view, name='admin_dashboard'),
    
    # REST API Endpoints (For DDoS demonstration / Mobile integrations)
    path('api/products/search/', views.api_products_search, name='api_products_search'),
    path('api/products/inventory/', views.api_products_inventory, name='api_products_inventory'),
    path('api/orders/status/', views.api_orders_status, name='api_orders_status'),
    path('api/products/recommendations/', views.api_products_recommendations, name='api_products_recommendations'),
    path('api/customer/profile/', views.api_customer_profile, name='api_customer_profile'),
    path('api/dashboard/stats/', views.api_dashboard_stats, name='api_dashboard_stats'),
]
