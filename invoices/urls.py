from django.urls import path

from . import views


app_name = 'invoices'

urlpatterns = [
    path('<str:number>/', views.invoice_detail, name='detail'),
]

