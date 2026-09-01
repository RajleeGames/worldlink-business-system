from functools import wraps
from django.contrib import messages
from django.shortcuts import redirect

def admin_required(view):
    @wraps(view)
    def wrapped(request,*args,**kwargs):
        if not request.user.is_authenticated: return redirect("login")
        if not request.user.is_company_admin():
            messages.error(request,"Admin permission is required.")
            return redirect("dashboard")
        return view(request,*args,**kwargs)
    return wrapped
