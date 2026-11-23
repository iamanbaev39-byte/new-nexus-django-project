from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from .models import Course, Student, StudyGroup, Teacher


class CrmViewsTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username="test-admin",
            email="",
            password="Test-password-123",
        )

    def test_login_page_has_csrf_and_dashboard_requires_authentication(self):
        client = Client(enforce_csrf_checks=True)
        login_page = client.get(reverse("login"))
        self.assertEqual(login_page.status_code, 200)
        self.assertContains(login_page, 'name="csrfmiddlewaretoken"')
        self.assertRedirects(client.get(reverse("dashboard")), f"{reverse('login')}?next=/")
        response = client.post(
            reverse("login"),
            {
                "username": "test-admin",
                "password": "Test-password-123",
                "csrfmiddlewaretoken": client.cookies["csrftoken"].value,
            },
        )
        self.assertRedirects(response, reverse("dashboard"))
        logout_response = client.post(
            reverse("logout"),
            {"csrfmiddlewaretoken": client.cookies["csrftoken"].value},
        )
        self.assertRedirects(logout_response, reverse("login"))

    def test_authenticated_crm_pages_render(self):
        self.client.force_login(self.admin)
        for name in (
            "dashboard",
            "account_settings",
            "teachers_list",
            "students_list",
            "courses_view",
            "attendance_view",
            "payroll_view",
        ):
            with self.subTest(page=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)
        self.assertEqual(self.client.get(reverse("teacher_create")).status_code, 200)
        self.assertEqual(self.client.get(reverse("student_create")).status_code, 200)
        self.assertEqual(self.client.get("/not-a-real-page").status_code, 404)

    def test_account_settings_updates_username_and_password(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("account_settings"),
            {
                "username": "new-admin",
                "current_password": "Test-password-123",
                "new_password": "New-password-456",
                "confirm_password": "New-password-456",
            },
        )
        self.assertRedirects(response, reverse("account_settings"))
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.username, "new-admin")
        self.assertTrue(self.admin.check_password("New-password-456"))

    def test_student_creation_and_staff_role_restrictions(self):
        course = Course.objects.create(name="Test Course", monthly_fee=250000)
        teacher = Teacher.objects.create(
            full_name="Test Teacher",
            phone="998900000000",
            subject="Test",
        )
        group = StudyGroup.objects.create(name="Test Group", course=course, teacher=teacher)
        response = self.client.post(
            reverse("student_create"),
            {
                "full_name": "Test Student",
                "phone": "998911111111",
                "course_id": course.id,
                "group_id": group.id,
                "monthly_fee": "250000",
                "payment_status": "unpaid",
            },
        )
        self.assertRedirects(response, reverse("login") + "?next=/students/new")
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("student_create"),
            {
                "full_name": "Test Student",
                "phone": "998911111111",
                "course_id": course.id,
                "group_id": group.id,
                "monthly_fee": "250000",
                "payment_status": "unpaid",
            },
        )
        self.assertRedirects(response, reverse("students_list"))
        self.assertEqual(Student.objects.get().group, group)
