"""
Team task checklist.

One test per assigned task, hitting the real endpoint end to end. This exists
so "is my part done?" is answered by a green test rather than by reading code.

Task owners are named in each test's docstring.
"""

from decimal import Decimal

from django.core import mail
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.content.models import Article, Banner, Promotion
from apps.orders.models import Order, OrderItem

from .factories import (PASSWORD, auth_client, create_category, create_product,
                        create_user)


class AuthChecklistTests(TestCase):
    """Register / Verify / Resend / Login / Forgot password / Logout."""

    def setUp(self):
        self.client = APIClient()

    def test_register(self):
        """Register — creates an unverified user and emails a code."""
        # The email is queued with transaction.on_commit, which never fires
        # inside TestCase's rolled-back transaction unless captured here.
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post("/api/v1/auth/register/", {
                "email": "new@example.com", "password": PASSWORD,
                "password2": PASSWORD, "first_name": "Yangi",
                "last_name": "Foydalanuvchi"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        from apps.users.models import User, UserOTPVerifications
        user = User.objects.get(email="new@example.com")
        self.assertFalse(user.is_active, "must start unverified")

        otp = UserOTPVerifications.objects.filter(user=user).first()
        self.assertIsNotNone(otp, "a verification code must be generated")
        self.assertEqual(len(otp.code), 6)
        self.assertEqual(len(mail.outbox), 1, "the code must be emailed")
        self.assertIn(otp.code, mail.outbox[0].body)

    def test_verify_code(self):
        """Verify code — emailed 6-digit code activates the account."""
        from apps.users import services
        user = create_user(email="verify@example.com", verified=False)
        otp = services.send_code(user, services.PURPOSE_VERIFY)

        response = self.client.post("/api/v1/auth/verify/", {
            "email": user.email, "code": otp.code}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertTrue(user.is_active)

    def test_resend_verification_code(self):
        """Resend verify code — old code dies, a new one is issued."""
        from apps.users import services
        from apps.users.models import UserOTPVerifications
        user = create_user(email="resend@example.com", verified=False)
        first = services.send_code(user, services.PURPOSE_VERIFY)

        # Bypass the cooldown, which is a separate behaviour tested elsewhere.
        UserOTPVerifications.objects.filter(pk=first.pk).update(
            created_at=timezone.now() - timezone.timedelta(minutes=10))

        response = self.client.post("/api/v1/auth/resend-verification/",
                                    {"email": user.email}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        first.refresh_from_db()
        self.assertTrue(first.is_used, "the previous code must be invalidated")
        self.assertEqual(
            UserOTPVerifications.objects.filter(
                user=user, is_used=False).count(), 1)

    def test_login(self):
        """Login — returns a JWT access/refresh pair."""
        user = create_user(email="login@example.com")
        response = self.client.post("/api/v1/auth/login/", {
            "email": user.email, "password": PASSWORD}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data["tokens"])
        self.assertIn("refresh", response.data["tokens"])

    def test_forgot_password_full_flow(self):
        """Forgot password — request, verify code, set a new password."""
        from apps.users.models import UserOTPVerifications
        user = create_user(email="forgot@example.com")

        self.assertEqual(self.client.post(
            "/api/v1/auth/forgot-password/", {"email": user.email},
            format="json").status_code, status.HTTP_200_OK)

        otp = UserOTPVerifications.objects.filter(
            user=user, for_forget_password=True).latest("created_at")

        self.assertEqual(self.client.post(
            "/api/v1/auth/verify-reset-code/",
            {"email": user.email, "code": otp.code},
            format="json").status_code, status.HTTP_200_OK)

        self.assertEqual(self.client.post("/api/v1/auth/reset-password/", {
            "email": user.email, "code": otp.code,
            "new_password": "BrandNew1!", "new_password2": "BrandNew1!"},
            format="json").status_code, status.HTTP_200_OK)

        user.refresh_from_db()
        self.assertTrue(user.check_password("BrandNew1!"))

    def test_logout(self):
        """Logout — the refresh token is genuinely revoked."""
        user = create_user(email="logout@example.com")
        tokens = self.client.post("/api/v1/auth/login/", {
            "email": user.email, "password": PASSWORD},
            format="json").data["tokens"]

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        self.assertEqual(client.post(
            "/api/v1/auth/logout/", {"refresh": tokens["refresh"]},
            format="json").status_code, status.HTTP_200_OK)

        # The revoked refresh token can no longer mint an access token.
        self.assertEqual(self.client.post(
            "/api/v1/auth/token/refresh/", {"refresh": tokens["refresh"]},
            format="json").status_code, status.HTTP_401_UNAUTHORIZED)


class CatalogChecklistTests(TestCase):
    """Product list / category list / filters / detail / comparison."""

    def setUp(self):
        self.client = APIClient()
        self.category = create_category("Asboblar", "asboblar")
        self.cheap = create_product(
            category=self.category, name="Bolg'a", slug="bolga",
            article="A-1", price="50.00", stock=5)
        self.pricey = create_product(
            category=self.category, name="Perforator", slug="perforator",
            article="A-2", price="500.00", old_price="700.00", stock=2)

    def test_product_list(self):
        """Product list — paginated."""
        response = self.client.get("/api/v1/catalog/products/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)
        for key in ("count", "pages", "next", "previous", "results"):
            self.assertIn(key, response.data)

    def test_category_list(self):
        """Product category list — with a product count per category."""
        response = self.client.get("/api/v1/catalog/categories/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["results"][0]["product_count"], 2)

    def test_price_range_filter(self):
        """Product filter — price range, the explicitly requested case."""
        response = self.client.get(
            "/api/v1/catalog/products/?min_price=100&max_price=600")
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["slug"], "perforator")

    def test_combined_filters(self):
        """Product filter — several filters at once."""
        response = self.client.get(
            f"/api/v1/catalog/products/?category={self.category.pk}"
            "&min_price=10&stock=true&discount=true&ordering=-price")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1,
                         "only the discounted product qualifies")

    def test_search(self):
        """Product filter — free-text search."""
        response = self.client.get(
            "/api/v1/catalog/products/?search=Perforator")
        self.assertEqual(response.data["count"], 1)

    def test_product_detail(self):
        """Product detail — images, attributes, stock, rating."""
        response = self.client.get("/api/v1/catalog/products/perforator/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for field in ("images", "attributes", "stock", "rating",
                      "review_count", "discount_percent", "old_price",
                      "category", "brand"):
            self.assertIn(field, response.data, f"detail missing '{field}'")

    def test_product_comparison(self):
        """Product comparison (sravneniya) — matrix of shared attributes."""
        response = self.client.post(
            "/api/v1/catalog/products/compare/",
            {"product_ids": [self.cheap.pk, self.pricey.pk]}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)
        self.assertIn("attributes", response.data)


class HomePageChecklistTests(TestCase):
    """Home page — every section the brief asks for."""

    def setUp(self):
        # The home payload is cached; without this a payload built by an
        # earlier test class would be served here.
        cache.clear()

    def test_home_sections(self):
        """Home page — categories, news, popular and best-selling products."""
        category = create_category("Uy", "uy")
        for index in range(12):
            create_product(
                category=category, name=f"Mahsulot {index}",
                slug=f"mahsulot-{index}", article=f"H-{index}",
                price="100.00", old_price="150.00", stock=5,
                is_featured=index % 2 == 0)
        Article.objects.create(type="news", title="Yangilik", slug="yangilik",
                               published_at=timezone.now())
        Banner.objects.create(title="Banner", image="banners/b.png", sort=1)
        Promotion.objects.create(title="Aksiya", slug="aksiya-home")

        response = APIClient().get("/api/v1/home/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        for section in ("categories", "news", "popular_products",
                        "best_selling_products", "new_products",
                        "discounted_products", "featured_products",
                        "promotions", "banners"):
            self.assertIn(section, response.data,
                          f"home page missing '{section}'")

        self.assertEqual(len(response.data["new_products"]), 10,
                         "sections must return up to 10 items")


class UserProfileChecklistTests(TestCase):
    """Password update, profile update, orders, wishlist, addresses."""

    def setUp(self):
        self.user = create_user(email="profil@example.com")
        self.client = auth_client(APIClient(), self.user)
        self.product = create_product(slug="p-1", article="P-1", stock=10)

    def test_update_password(self):
        """User profile — update password."""
        response = self.client.post("/api/v1/user/password/change/", {
            "old_password": PASSWORD, "new_password": "Changed1!",
            "new_password2": "Changed1!"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Changed1!"))

    def test_update_user_info(self):
        """User profile — update personal information."""
        response = self.client.patch("/api/v1/user/profile/", {
            "first_name": "Yangi", "phone_number": "+998901234567"},
            format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["first_name"], "Yangi")

    def test_orders(self):
        """User orders — list and detail, scoped to the caller."""
        order = Order.objects.create(
            number="CHK-1", user=self.user, subtotal=Decimal("100"),
            total=Decimal("100"))
        OrderItem.objects.create(
            order=order, product=self.product, name_snapshot="P",
            article_snapshot="P-1", price=Decimal("100"), quantity=1)

        listed = self.client.get("/api/v1/user/orders/")
        self.assertEqual(listed.data["count"], 1)

        detail = self.client.get(f"/api/v1/user/orders/{order.pk}/")
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(len(detail.data["items"]), 1)

    def test_wishlist(self):
        """User wishlist — add, list, status, remove."""
        self.assertEqual(self.client.post(
            "/api/v1/user/wishlist/add/", {"product_id": self.product.pk},
            format="json").status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            self.client.get("/api/v1/user/wishlist/").data["count"], 1)
        self.assertTrue(self.client.get(
            f"/api/v1/user/wishlist/{self.product.pk}/status/"
        ).data["in_wishlist"])
        self.assertEqual(self.client.delete(
            f"/api/v1/user/wishlist/{self.product.pk}/").status_code,
            status.HTTP_204_NO_CONTENT)

    def test_delivery_address_crud(self):
        """User delivery address — full CRUD plus default selection."""
        created = self.client.post("/api/v1/user/addresses/", {
            "city": "Toshkent", "street": "Amir Temur", "house": "1",
            "phone": "+998901234567"}, format="json")
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        pk = created.data["id"]

        self.assertEqual(
            self.client.get("/api/v1/user/addresses/").status_code,
            status.HTTP_200_OK)
        self.assertEqual(self.client.patch(
            f"/api/v1/user/addresses/{pk}/", {"city": "Samarqand"},
            format="json").data["city"], "Samarqand")
        self.assertTrue(self.client.post(
            f"/api/v1/user/addresses/{pk}/set-default/").data["is_default"])
        self.assertEqual(
            self.client.delete(f"/api/v1/user/addresses/{pk}/").status_code,
            status.HTTP_204_NO_CONTENT)


class ContentChecklistTests(TestCase):
    """Otziv (review) CRUD, Aksiya list, News list."""

    def setUp(self):
        self.user = create_user(email="content@example.com")
        self.client = auth_client(APIClient(), self.user)
        self.product = create_product(slug="c-1", article="C-1", stock=10)

    def _purchase(self):
        """Reviews are gated to verified buyers."""
        order = Order.objects.create(
            number="REV-1", user=self.user, status=Order.Status.COMPLETED,
            subtotal=Decimal("100"), total=Decimal("100"))
        OrderItem.objects.create(
            order=order, product=self.product, name_snapshot="C",
            article_snapshot="C-1", price=Decimal("100"), quantity=1)

    def test_review_crud(self):
        """Otziv — create, read, update and delete one's own review."""
        self._purchase()
        created = self.client.post("/api/v1/user/reviews/", {
            "product": self.product.pk, "rating": 5, "comment": "Zo'r",
            "author_name": "Test"}, format="json")
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        pk = created.data["id"]

        self.assertEqual(self.client.get("/api/v1/user/reviews/").data["count"],
                         1)
        self.assertEqual(self.client.patch(
            f"/api/v1/user/reviews/{pk}/", {"rating": 4},
            format="json").data["rating"], 4)
        self.assertEqual(
            self.client.delete(f"/api/v1/user/reviews/{pk}/").status_code,
            status.HTTP_204_NO_CONTENT)

    def test_public_review_list(self):
        """Otziv — public list of a product's published reviews."""
        from apps.reviews.models import Review
        Review.objects.create(product=self.product, author_name="Ali",
                              rating=5, comment="Yaxshi", is_published=True)
        response = APIClient().get(
            f"/api/v1/catalog/products/{self.product.pk}/reviews/")
        self.assertEqual(response.data["count"], 1)

    def test_promotion_list(self):
        """Aksiya — list, excluding expired promotions."""
        Promotion.objects.create(title="Bahor", slug="bahor",
                                 discount_label="-20%")
        Promotion.objects.create(
            title="Eskirgan", slug="eskirgan",
            valid_until=timezone.now().date() - timezone.timedelta(days=1))
        response = APIClient().get("/api/v1/promotions/")
        self.assertEqual(response.data["count"], 1,
                         "expired promotions must not appear")

    def test_news_list_and_detail(self):
        """News — list and detail, published items only."""
        Article.objects.create(type="news", title="Yangilik", slug="yangilik",
                               body="matn", published_at=timezone.now())
        Article.objects.create(type="news", title="Qoralama",
                               slug="qoralama")  # unpublished

        listed = APIClient().get("/api/v1/news/")
        self.assertEqual(listed.data["count"], 1,
                         "unpublished news must stay hidden")
        detail = APIClient().get("/api/v1/news/yangilik/")
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(detail.data["body"], "matn")
