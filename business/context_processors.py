from django.utils import timezone
from .models import CompanySetting


def company_context(request):
    try:
        company = CompanySetting.objects.first()
    except Exception:
        company = None

    hour = timezone.localtime().hour
    if hour < 12:
        greeting = "Good morning"
    elif hour < 17:
        greeting = "Good afternoon"
    else:
        greeting = "Good evening"

    return {"company": company, "greeting": greeting}
