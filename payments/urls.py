from django.urls import path

from . import views


app_name = 'payments'

urlpatterns = [
    path('order/<int:order_id>/start/', views.payment_start, name='start'),
    path('test/<uuid:token>/', views.test_gateway, name='test_gateway'),
    path(
        'test/<uuid:token>/callback/',
        views.test_gateway_callback,
        name='test_gateway_callback',
    ),
]

