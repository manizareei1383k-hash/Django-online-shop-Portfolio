from django.urls import path

from . import views


app_name = 'management_panel'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('products/', views.product_list, name='products'),
    path('products/add/', views.product_create, name='product_create'),
    path('products/<int:pk>/edit/', views.product_update, name='product_update'),
    path('products/<int:pk>/delete/', views.product_delete, name='product_delete'),
    path('categories/', views.category_list, name='categories'),
    path('categories/add/', views.category_create, name='category_create'),
    path('categories/<int:pk>/edit/', views.category_update, name='category_update'),
    path('categories/<int:pk>/delete/', views.category_delete, name='category_delete'),
    path('shipping/', views.shipping_list, name='shipping_methods'),
    path('shipping/add/', views.shipping_create, name='shipping_create'),
    path('shipping/<int:pk>/edit/', views.shipping_update, name='shipping_update'),
    path('shipping/<int:pk>/delete/', views.shipping_delete, name='shipping_delete'),
    path('orders/', views.order_list, name='orders'),
    path('orders/<int:pk>/', views.order_detail, name='order_detail'),
    path('orders/<int:pk>/cancel/', views.order_cancel, name='order_cancel'),
    path('tickets/', views.ticket_list, name='tickets'),
    path('tickets/<int:pk>/', views.ticket_detail, name='ticket_detail'),
    path('reviews/', views.review_list, name='reviews'),
    path('reviews/<int:pk>/', views.review_detail, name='review_detail'),
    path('payments/', views.payment_list, name='payments'),
    path('payments/<int:pk>/', views.payment_detail, name='payment_detail'),
    path('invoices/', views.invoice_list, name='invoices'),
    path('invoices/<int:pk>/', views.invoice_detail, name='invoice_detail'),
    path('users/', views.user_list, name='users'),
    path('users/<int:pk>/', views.user_detail, name='user_detail'),
    path('activities/', views.activity_list, name='activities'),
]
