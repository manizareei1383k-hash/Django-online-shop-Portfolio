from django.urls import path

from . import views

app_name = 'shop'

urlpatterns = [
    path('', views.home, name='home'),
    path('shop/', views.shop, name='shop'),
    path('product/<int:pk>/', views.product_detail, name='product_detail'),
    path('contact-us/', views.contact_us, name='contact_us'),
    path('rules/', views.rules, name='rules'),
    path('about-us/', views.about_us, name='about_us'),
    path('management/products/', views.product_management, name='product_management'),
    path(
        'management/products/add/',
        views.product_create,
        name='product_create',
    ),
    path(
        'management/products/<int:pk>/edit/',
        views.product_update,
        name='product_update',
    ),
    path(
        'management/products/<int:pk>/delete/',
        views.product_delete,
        name='product_delete',
    ),
]
