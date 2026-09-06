from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings

from account.models import User

from .middleware import UserRateLimitMiddleware


@override_settings(
    RATE_LIMIT_ENABLED=True,
    RATE_LIMIT_REQUESTS=5,
    RATE_LIMIT_WINDOW_SECONDS=60,
)
class UserRateLimitMiddlewareTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()
        self.middleware = UserRateLimitMiddleware(
            lambda request: HttpResponse('ok')
        )

    def make_request(self, path='/', user=None, ip='127.0.0.1'):
        request = self.factory.get(path, REMOTE_ADDR=ip)
        request.user = user or AnonymousUser()
        return self.middleware(request)

    def test_sixth_request_to_same_path_is_rejected(self):
        responses = [self.make_request('/shop/') for _ in range(6)]

        self.assertTrue(all(response.status_code == 200 for response in responses[:5]))
        self.assertEqual(responses[5].status_code, 429)
        self.assertEqual(responses[5].headers['X-RateLimit-Remaining'], '0')
        self.assertIn('Retry-After', responses[5].headers)

    def test_each_path_has_a_separate_limit(self):
        for _ in range(5):
            self.make_request('/shop/')

        response = self.make_request('/contact-us/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['X-RateLimit-Remaining'], '4')

    def test_anonymous_visitors_are_separated_by_ip(self):
        for _ in range(5):
            self.make_request('/shop/', ip='192.0.2.1')

        blocked = self.make_request('/shop/', ip='192.0.2.1')
        allowed = self.make_request('/shop/', ip='192.0.2.2')

        self.assertEqual(blocked.status_code, 429)
        self.assertEqual(allowed.status_code, 200)

    def test_authenticated_users_are_separated_by_user_id(self):
        first_user = User(pk=10, phone_number='09120000010')
        second_user = User(pk=11, phone_number='09120000011')
        for _ in range(5):
            self.make_request('/orders/', user=first_user)

        blocked = self.make_request('/orders/', user=first_user)
        allowed = self.make_request('/orders/', user=second_user)

        self.assertEqual(blocked.status_code, 429)
        self.assertEqual(allowed.status_code, 200)

    def test_staff_users_are_not_limited(self):
        staff_user = User(pk=20, phone_number='09120000020', is_staff=True)

        responses = [
            self.make_request('/admin/', user=staff_user)
            for _ in range(10)
        ]

        self.assertTrue(all(response.status_code == 200 for response in responses))
