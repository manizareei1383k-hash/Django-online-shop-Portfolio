from django.urls import path

from . import views


app_name = 'cart'

urlpatterns = [
    path('', views.cart_detail, name='detail'),
    path('add/<int:product_id>/', views.cart_add, name='add'),
    path('items/<int:item_id>/update/', views.cart_item_update, name='item_update'),
    path('items/<int:item_id>/remove/', views.cart_item_remove, name='item_remove'),
    path('clear/', views.cart_clear, name='clear'),
]
