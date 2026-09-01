from .models import AuditLog
def client_ip(request):
    x=request.META.get("HTTP_X_FORWARDED_FOR")
    return (x.split(",")[0].strip() if x else request.META.get("REMOTE_ADDR"))
def audit(request, action, detail=""):
    if request.user.is_authenticated:
        AuditLog.objects.create(user=request.user, action=action, detail=detail[:255], ip_address=client_ip(request))
