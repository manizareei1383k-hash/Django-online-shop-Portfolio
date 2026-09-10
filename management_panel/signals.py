from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from account.models import Ticket, User
from notifications.models import Notification
from orders.models import Order
from payments.models import Payment
from shop.models import Product

from .cache import invalidate_dashboard_stats_cache


@receiver([post_save, post_delete], sender=Product)
@receiver([post_save, post_delete], sender=User)
@receiver([post_save, post_delete], sender=Order)
@receiver([post_save, post_delete], sender=Ticket)
@receiver([post_save, post_delete], sender=Notification)
@receiver([post_save, post_delete], sender=Payment)
def invalidate_dashboard_after_change(**kwargs):
    invalidate_dashboard_stats_cache()
