from django.urls import path

from . import views


app_name = 'account'

urlpatterns = [
    path('register/', views.register, name='register'),
    path('login/', views.login, name='login'),
    path('logout/', views.logout, name='logout'),
    path(
        'password/change/',
        views.password_change,
        name='password_change',
    ),
    path(
        'password/change/done/',
        views.password_change_done,
        name='password_change_done',
    ),
    path(
        'password/reset/',
        views.password_reset,
        name='password_reset',
    ),
    path(
        'password/reset/done/',
        views.password_reset_done,
        name='password_reset_done',
    ),
    path(
        'password/reset/<uidb64>/<token>/',
        views.password_reset_confirm,
        name='password_reset_confirm',
    ),
    path(
        'password/reset/complete/',
        views.password_reset_complete,
        name='password_reset_complete',
    ),
    path('profile/', views.profile, name='profile'),
    path('profile/edit/', views.profile_edit, name='profile_edit'),
    path('addresses/', views.address_list, name='address_list'),
    path('addresses/add/', views.address_create, name='address_create'),
    path('addresses/<int:pk>/edit/', views.address_update, name='address_update'),
    path('addresses/<int:pk>/delete/', views.address_delete, name='address_delete'),
    path('tickets/', views.ticket_list, name='ticket_list'),
    path('tickets/add/', views.ticket_create, name='ticket_create'),
    path('tickets/<int:pk>/', views.ticket_detail, name='ticket_detail'),
    path('wallet/', views.wallet, name='wallet'),
]
