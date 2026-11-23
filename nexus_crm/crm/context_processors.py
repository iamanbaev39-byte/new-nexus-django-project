from types import SimpleNamespace

from django.conf import settings
from django.utils import timezone
from .models import OrganizationSettings


def template_globals(request):
    user = request.user
    current_user = SimpleNamespace(
        full_name=(user.get_full_name() or user.get_username()) if user.is_authenticated else "",
        role="admin" if user.is_authenticated and user.is_staff else "staff",
        is_authenticated=user.is_authenticated,
    )
    organization = OrganizationSettings.objects.filter(pk=1).first()
    brand_name = organization.name if organization else settings.BRAND_NAME
    return {
        "brand_name": brand_name,
        "current_year": timezone.now().year,
        "current_user": current_user,
    }
