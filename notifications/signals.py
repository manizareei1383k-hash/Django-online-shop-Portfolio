from django.db.models.signals import post_save
from django.dispatch import receiver

from account.models import TicketMessage

from .selectors import notify_ticket_reply


@receiver(post_save, sender=TicketMessage)
def create_ticket_reply_notification(sender, instance, created, **kwargs):
    if not created or instance.sender_id is None:
        return
    if instance.sender_id == instance.ticket.user_id:
        return
    if instance.sender.is_staff:
        notify_ticket_reply(instance)

