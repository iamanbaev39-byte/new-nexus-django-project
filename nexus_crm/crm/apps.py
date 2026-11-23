import os

from django.apps import AppConfig
from django.db.models.signals import post_migrate


def create_initial_data(sender, **kwargs):
    from django.contrib.auth import get_user_model

    from .models import Course

    user_model = get_user_model()
    username = os.environ.get("ADMIN_USERNAME", "admin")
    if not user_model.objects.filter(username=username).exists():
        user_model.objects.create_superuser(
            username=username,
            email="",
            password=os.environ.get("ADMIN_PASSWORD", "Admin123!"),
            first_name="NEXUS",
            last_name="Administrator",
        )

    defaults = (
        ("Python Backend", 600000, "Python, Django, REST API va PostgreSQL"),
        ("Frontend", 550000, "HTML, CSS, JavaScript va React"),
        ("Graphic Design", 500000, "Photoshop, Illustrator va Figma"),
        ("Cybersecurity", 650000, "Tarmoq xavfsizligi va tahlil"),
        ("English", 450000, "General va IT English"),
        ("Computer Literacy", 350000, "Kompyuter savodxonligi"),
    )
    for name, monthly_fee, description in defaults:
        Course.objects.get_or_create(
            name=name,
            defaults={"monthly_fee": monthly_fee, "description": description},
        )


class CrmConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "crm"

    def ready(self):
        post_migrate.connect(create_initial_data, sender=self)
