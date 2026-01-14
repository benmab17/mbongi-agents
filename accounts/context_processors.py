from agents.security import is_chef_service

def nav_context(request):
    user = getattr(request, "user", None)
    return {
        "is_chef": is_chef_service(user),
    }
