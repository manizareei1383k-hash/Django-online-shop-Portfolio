from datetime import timedelta

from django.core.exceptions import ValidationError
from django.core.cache import cache
from django.http import QueryDict
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from account.models import User

from .forms import ProductForm
from .models import Category, Message, Product, ProductDiscount, Review
from .selectors import get_product_detail_cache_key, get_shop_context


class ShopViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        category = Category.objects.create(
            name='Test category',
            image='category_images/test.jpg',
        )
        cls.product = Product.objects.create(
            name='Test product',
            price='100.00',
            status='available',
            quantity=2,
            category=category,
        )

    def test_public_pages_are_available(self):
        urls = (
            reverse('shop:home'),
            reverse('shop:shop'),
            reverse('shop:contact_us'),
            reverse('shop:rules'),
            reverse('shop:about_us'),
            reverse('shop:product_detail', args=[self.product.pk]),
        )

        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_contact_form_saves_message(self):
        response = self.client.post(
            reverse('shop:contact_us'),
            {
                'name': 'Customer',
                'email': 'customer@example.com',
                'message': 'Hello',
            },
        )

        self.assertRedirects(response, reverse('shop:contact_us'))
        self.assertTrue(Message.objects.filter(email='customer@example.com').exists())

    def test_review_is_connected_to_product(self):
        user = User.objects.create_user(
            phone_number='09120000003',
            password='safe-password-123',
        )
        self.client.force_login(user)
        response = self.client.post(
            reverse('shop:product_detail', args=[self.product.pk]),
            {
                'name': 'Customer',
                'email': 'customer@example.com',
                'review': 'A useful product',
            },
        )

        self.assertRedirects(
            response,
            reverse('shop:product_detail', args=[self.product.pk]),
        )
        review = Review.objects.get(email='customer@example.com')
        self.assertEqual(review.product, self.product)

    def test_product_detail_cache_is_invalidated_after_review(self):
        cache.clear()
        product_url = reverse('shop:product_detail', args=[self.product.pk])
        cache_key = get_product_detail_cache_key(self.product.pk)

        response = self.client.get(product_url)

        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(cache.get(cache_key))

        with self.captureOnCommitCallbacks(execute=True):
            Review.objects.create(
                product=self.product,
                name='Customer',
                email='customer@example.com',
                review='A useful product',
            )

        self.assertIsNone(cache.get(cache_key))

    def test_shop_list_uses_cache(self):
        cache.clear()
        params = QueryDict('')

        first_context = get_shop_context(params)
        self.assertEqual(len(first_context['page'].object_list), 1)

        with self.assertNumQueries(0):
            cached_context = get_shop_context(params)

        self.assertEqual(len(cached_context['page'].object_list), 1)

    def test_anonymous_user_cannot_submit_review(self):
        product_url = reverse('shop:product_detail', args=[self.product.pk])

        response = self.client.post(
            product_url,
            {
                'name': 'Anonymous',
                'email': 'anonymous@example.com',
                'review': 'Anonymous review',
            },
        )

        self.assertRedirects(
            response,
            f"{reverse('account:login')}?next={product_url}",
        )
        self.assertFalse(
            Review.objects.filter(email='anonymous@example.com').exists()
        )

    def test_anonymous_user_cannot_manage_products(self):
        response = self.client.get(reverse('shop:product_management'))
        self.assertRedirects(
            response,
            f"{reverse('account:login')}?next={reverse('shop:product_management')}",
        )

    def test_normal_user_cannot_use_product_management_actions(self):
        normal_user = User.objects.create_user(
            phone_number='09120000001',
            password='safe-password-123',
        )
        self.client.force_login(normal_user)
        urls = (
            reverse('shop:product_management'),
            reverse('shop:product_create'),
            reverse('shop:product_update', args=[self.product.pk]),
            reverse('shop:product_delete', args=[self.product.pk]),
        )

        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_staff_user_can_open_product_management(self):
        admin_user = User.objects.create_user(
            phone_number='09120000002',
            password='safe-password-123',
            is_staff=True,
        )
        self.client.force_login(admin_user)

        response = self.client.get(reverse('shop:product_management'))

        self.assertEqual(response.status_code, 200)

    def test_admin_can_create_update_and_delete_product(self):
        admin_user = User.objects.create_superuser(
            phone_number='09120000000',
            password='safe-password-123',
        )
        self.client.force_login(admin_user)
        category = self.product.category

        create_response = self.client.post(
            reverse('shop:product_create'),
            {
                'name': 'New product',
                'price': '250.00',
                'status': 'available',
                'description': 'Description',
                'quantity': 5,
                'category': category.pk,
            },
        )
        self.assertRedirects(create_response, reverse('shop:product_management'))
        product = Product.objects.get(name='New product')

        update_response = self.client.post(
            reverse('shop:product_update', args=[product.pk]),
            {
                'name': 'Updated product',
                'price': '300.00',
                'status': 'available',
                'description': 'Updated description',
                'quantity': 4,
                'category': category.pk,
            },
        )
        self.assertRedirects(update_response, reverse('shop:product_management'))
        product.refresh_from_db()
        self.assertEqual(product.name, 'Updated product')

        delete_response = self.client.post(
            reverse('shop:product_delete', args=[product.pk]),
        )
        self.assertRedirects(delete_response, reverse('shop:product_management'))
        self.assertFalse(Product.objects.filter(pk=product.pk).exists())

    def test_product_form_rejects_zero_price(self):
        form = ProductForm(
            data={
                'name': 'Invalid product',
                'price': '0',
                'status': 'available',
                'quantity': 1,
                'category': self.product.category.pk,
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn('price', form.errors)

    def test_product_discount_updates_calculated_price(self):
        ProductDiscount.objects.create(
            product=self.product,
            title='تخفیف جشنواره',
            percent=20,
            ends_at=timezone.now() + timedelta(days=1),
        )

        self.assertEqual(self.product.active_discount.percent, 20)
        self.assertEqual(self.product.price_after_discount, 80)

    def test_product_discount_cannot_be_greater_than_100_percent(self):
        discount = ProductDiscount(
            product=self.product,
            percent=101,
            ends_at=timezone.now() + timedelta(days=1),
        )

        with self.assertRaises(ValidationError):
            discount.full_clean()
