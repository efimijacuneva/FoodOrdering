from django.urls import path
from . import views

urlpatterns = [
    # Menu (root)
    path('', views.menu_view, name='menu'),

    # Cart
    path('cart/', views.cart_view, name='cart'),
    path('cart/add/<int:product_id>/', views.add_to_cart_view, name='add_to_cart'),
    path('cart/remove/<int:item_id>/', views.remove_from_cart_view, name='remove_from_cart'),
    path('cart/update/<int:item_id>/', views.update_cart_view, name='update_cart'),

    # Checkout & Orders
    path('checkout/', views.checkout_view, name='checkout'),
    path('order/success/<int:order_id>/', views.order_success_view, name='order_success'),
    path('orders/', views.order_history_view, name='order_history'),
    path('orders/<int:order_id>/', views.order_detail_view, name='order_detail'),

    # Auth
    path('register/', views.register_view, name='register'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/password/', views.change_password_view, name='change_password'),

    # Admin Panel
    path('admin-panel/', views.admin_dashboard_view, name='admin_dashboard'),
    path('admin-panel/products/', views.admin_products_view, name='admin_products'),
    path('admin-panel/products/create/', views.admin_product_create_view, name='admin_product_create'),
    path('admin-panel/products/<int:product_id>/edit/', views.admin_product_edit_view, name='admin_product_edit'),
    path('admin-panel/products/<int:product_id>/delete/', views.admin_product_delete_view, name='admin_product_delete'),
    path('admin-panel/categories/', views.admin_categories_view, name='admin_categories'),
    path('admin-panel/categories/create/', views.admin_category_create_view, name='admin_category_create'),
    path('admin-panel/categories/<int:category_id>/edit/', views.admin_category_edit_view, name='admin_category_edit'),
    path('admin-panel/categories/<int:category_id>/delete/', views.admin_category_delete_view, name='admin_category_delete'),
    path('admin-panel/orders/', views.admin_orders_view, name='admin_orders'),
    path('admin-panel/orders/<int:order_id>/', views.admin_order_detail_view, name='admin_order_detail'),
    path('admin-panel/customers/', views.admin_customers_view, name='admin_customers'),
    path('admin-panel/customers/<int:user_id>/toggle/', views.admin_customer_toggle_view, name='admin_customer_toggle'),
]
