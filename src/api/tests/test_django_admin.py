"""
Django admin pages that used to crash on this project's email-keyed User.

With public registration disabled, the admin "Add user" form is how staff
accounts are created, so it must work.
"""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from .factories import create_user

User = get_user_model()


class UserAdminTests(TestCase):
    def setUp(self):
        self.admin = create_user(email="root@example.com", staff=True,
                                 is_superuser=True)
        self.client = Client()
        self.client.force_login(self.admin)

    def test_add_user_page_renders(self):
        response = self.client.get("/admin/users/user/add/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="email"')
        self.assertNotContains(response, 'name="username"')

    def test_staff_account_can_be_created(self):
        response = self.client.post("/admin/users/user/add/", {
            "email": "new.staff@example.com", "first_name": "Yangi",
            "last_name": "Xodim", "password1": "Strong-Pass-123!",
            "password2": "Strong-Pass-123!", "is_active": "on",
            "is_staff": "on", "_save": "Save",
        })
        self.assertEqual(response.status_code, 302,
                         "a valid submission redirects after saving")

        user = User.objects.get(email="new.staff@example.com")
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.check_password("Strong-Pass-123!"))

    def test_mismatched_passwords_are_rejected(self):
        response = self.client.post("/admin/users/user/add/", {
            "email": "typo@example.com", "first_name": "T",
            "password1": "Strong-Pass-123!", "password2": "Other-Pass-123!",
            "_save": "Save",
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email="typo@example.com").exists())

    def test_new_accounts_start_active(self):
        response = self.client.get("/admin/users/user/add/")
        self.assertTrue(
            response.context["adminform"].form.initial.get("is_active"))

    def test_searching_user_related_admin_lists_works(self):
        for url in ("/admin/users/user/",
                    "/admin/users/userotpverifications/",
                    "/admin/users/userotpidverifications/",
                    "/admin/users/changepasswordlogs/",
                    "/admin/users/changeemaillogs/"):
            with self.subTest(url=url):
                self.assertEqual(
                    self.client.get(url, {"q": "root"}).status_code, 200)
