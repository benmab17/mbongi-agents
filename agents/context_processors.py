def current_context(request):
    current_service = "ANR"
    current_role = "AGENT"
    has_briefing_presidence = False

    user = getattr(request, "user", None)
    if user and getattr(user, "is_authenticated", False):
        service_order = ["ANR", "PNC", "FARDC", "DEMIAP", "DGM", "AMBASSADE", "CNS"]
        user_groups = set(user.groups.values_list("name", flat=True))

        for name in service_order:
            if name in user_groups:
                current_service = name
                break

        for role_name in ["AG", "AP", "DIRECTEUR", "AGENT"]:
            if role_name in user_groups:
                current_role = role_name
                break

        if "BRIEFING PRESIDENCE" in user_groups or "BRIEFING_PRESIDENCE" in user_groups:
            has_briefing_presidence = True

    return {
        "current_service": current_service,
        "current_role": current_role,
        "has_briefing_presidence": has_briefing_presidence,
    }
