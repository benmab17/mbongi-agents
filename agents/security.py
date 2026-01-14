from functools import wraps
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import redirect


def is_chef_service(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    # staff/superuser passent toujours
    if user.is_staff or user.is_superuser:
        return True
    # groupe "CHEF_SERVICE"
    return user.groups.filter(name="CHEF_SERVICE").exists()


def chef_required(view_func):
    """
    Bloque l'accès si l'utilisateur n'est pas chef.
    Redirige vers dashboard avec message.
    """
    @login_required
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not is_chef_service(request.user):
            messages.error(request, "Accès refusé : vue réservée au Chef de service.")
            return redirect("dashboard")
        return view_func(request, *args, **kwargs)
    return _wrapped


def is_presidence(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    # staff/superuser passent toujours
    if user.is_staff or user.is_superuser:
        return True
    # groupe "PRESIDENCE"
    return user.groups.filter(name="PRESIDENCE").exists()

def is_cns(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    return user.groups.filter(name="CNS").exists()

def presidence_or_cns_required(view_func):
    """
    Bloque l'accés si l'utilisateur n'est pas autorisé pour la Présidence ou le CNS.
    """
    @login_required
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not (is_presidence(request.user) or is_cns(request.user)):
            messages.error(request, "Accés refusé : vue réservée à la Présidence/CNS.")
            return redirect("dashboard") # ou une autre page d'accueil
        return view_func(request, *args, **kwargs)
    return _wrapped


def presidence_required(view_func):
    """
    Bloque l'accès si l'utilisateur n'est pas autorisé pour la Présidence.
    """
    @login_required
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not is_presidence(request.user):
            messages.error(request, "Accès refusé : vue réservée à la Présidence.")
            return redirect("dashboard") # ou une autre page d'accueil
        return view_func(request, *args, **kwargs)
    return _wrapped

