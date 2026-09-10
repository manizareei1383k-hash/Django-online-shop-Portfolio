from django.core.cache import cache
from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Category, Product, ProductDiscount, Review, ReviewReply
from .selectors import get_product_detail_cache_key


def invalidate_product_detail_cache(product_id=None):
    def delete_cache():
        if product_id is not None:
            cache.delete(get_product_detail_cache_key(product_id))
            return

        if hasattr(cache, 'delete_pattern'):
            cache.delete_pattern('shop:product_detail:*')
        else:
            cache.clear()

    transaction.on_commit(delete_cache, robust=True)


@receiver([post_save, post_delete], sender=Category)
@receiver([post_save, post_delete], sender=Product)
@receiver([post_save, post_delete], sender=ProductDiscount)
def invalidate_public_shop_cache(**kwargs):
    def delete_public_cache():
        cache.delete_many(['shop:home:products', 'shop:home:categories'])
        if hasattr(cache, 'delete_pattern'):
            cache.delete_pattern('shop:catalog:*')
        else:
            cache.clear()

    transaction.on_commit(delete_public_cache, robust=True)
    invalidate_product_detail_cache()


@receiver([post_save, post_delete], sender=Review)
def invalidate_review_product_cache(instance, **kwargs):
    invalidate_product_detail_cache(instance.product_id)


@receiver([post_save, post_delete], sender=ReviewReply)
def invalidate_review_reply_product_cache(instance, **kwargs):
    invalidate_product_detail_cache(instance.review.product_id)
