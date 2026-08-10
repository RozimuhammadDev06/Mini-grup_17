from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.orders.models import Order, OrderItem
from apps.reviews.models import Review

from .factories import auth_client, create_product, create_user


def mark_purchased(user, product):
    """Give the user a completed order containing the product."""
    order = Order.objects.create(
        number=f"T-{product.pk}-{user.pk.hex[:6]}", user=user,
        status=Order.Status.COMPLETED, subtotal=product.price,
        total=product.price)
    OrderItem.objects.create(
        order=order, product=product, name_snapshot=product.name,
        article_snapshot=product.article, price=product.price, quantity=1)
    return order


class ReviewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = create_user(email="rev@example.com")
        auth_client(self.client, self.user)
        self.product = create_product()
        mark_purchased(self.user, self.product)
        self.payload = {"product": self.product.pk, "rating": 5,
                        "comment": "Excellent tool", "author_name": "Rev"}

    def test_authenticated_purchaser_can_review(self):
        response = self.client.post("/api/v1/user/reviews/", self.payload,
                                    format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(response.data["is_published"],
                         "new reviews await moderation")

    def test_anonymous_cannot_review(self):
        response = APIClient().post("/api/v1/user/reviews/", self.payload,
                                    format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_non_purchaser_is_blocked(self):
        stranger = create_user(email="stranger@example.com")
        client = auth_client(APIClient(), stranger)
        response = client.post("/api/v1/user/reviews/", self.payload,
                               format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_duplicate_review_rejected(self):
        self.client.post("/api/v1/user/reviews/", self.payload, format="json")
        duplicate = self.client.post("/api/v1/user/reviews/", self.payload,
                                     format="json")
        self.assertEqual(duplicate.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Review.objects.count(), 1)

    def test_rating_out_of_range_rejected(self):
        for rating in (0, 6, -1):
            response = self.client.post(
                "/api/v1/user/reviews/", {**self.payload, "rating": rating},
                format="json")
            self.assertEqual(response.status_code,
                             status.HTTP_400_BAD_REQUEST)

    def test_update_and_delete_own_review(self):
        created = self.client.post("/api/v1/user/reviews/", self.payload,
                                   format="json")
        review_id = created.data["id"]

        updated = self.client.patch(
            f"/api/v1/user/reviews/{review_id}/", {"rating": 3},
            format="json")
        self.assertEqual(updated.status_code, status.HTTP_200_OK)
        self.assertEqual(updated.data["rating"], 3)

        deleted = self.client.delete(f"/api/v1/user/reviews/{review_id}/")
        self.assertEqual(deleted.status_code, status.HTTP_204_NO_CONTENT)


class PublicReviewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.product = create_product()
        self.user = create_user(email="author@example.com")
        Review.objects.create(product=self.product, user=self.user,
                              author_name="A", rating=5, comment="Great",
                              is_published=True)
        Review.objects.create(product=self.product, author_name="B",
                              rating=3, comment="Fine", is_published=True)
        Review.objects.create(product=self.product, author_name="C",
                              rating=1, comment="Hidden", is_published=False)

    def test_only_published_reviews_are_public(self):
        response = self.client.get(
            f"/api/v1/catalog/products/{self.product.pk}/reviews/")
        self.assertEqual(response.data["count"], 2)
        self.assertNotIn(
            "Hidden", [r["comment"] for r in response.data["results"]])

    def test_rating_filter_and_ordering(self):
        filtered = self.client.get(
            f"/api/v1/catalog/products/{self.product.pk}/reviews/",
            {"rating": 5})
        self.assertEqual(filtered.data["count"], 1)

        ordered = self.client.get(
            f"/api/v1/catalog/products/{self.product.pk}/reviews/",
            {"ordering": "rating"})
        ratings = [r["rating"] for r in ordered.data["results"]]
        self.assertEqual(ratings, sorted(ratings))

    def test_rating_summary_is_server_computed(self):
        response = self.client.get(
            f"/api/v1/catalog/products/{self.product.pk}/rating/")
        self.assertEqual(response.data["average_rating"], 4.0)
        self.assertEqual(response.data["review_count"], 2)
        self.assertEqual(response.data["distribution"]["5"], 1)
        self.assertEqual(response.data["distribution"]["1"], 0)

    def test_product_detail_reports_the_same_aggregate(self):
        response = self.client.get(
            f"/api/v1/catalog/products/{self.product.pk}/")
        self.assertEqual(response.data["review_count"], 2)
        self.assertEqual(str(response.data["rating"]), "4.00")
