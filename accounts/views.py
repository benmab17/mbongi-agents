from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils import timezone

from agents.models import AuditLog
from agents.security import is_chef_service, is_presidence


class AgentLoginView(LoginView):
    template_name = "accounts/login.html"

    def form_valid(self, form):
        # --- Journalisation de l'accès à l'audit ---
        ip_address = self.request.META.get("REMOTE_ADDR")
        AuditLog.objects.create(
            user=form.get_user(),
            action="LOGIN",
            ip_address=ip_address,
            target_repr="Système"
        )
        return super().form_valid(form)

    def get_success_url(self):
        nxt = self.get_redirect_url()
        if nxt:
            return nxt
        if self.request.user.groups.filter(name="PRESIDENCE").exists():
            return reverse("presidence_briefing")
        if self.request.user.groups.filter(name="CNS").exists():
            return reverse("cns_dashboard")
        if self.request.user.groups.filter(name="CHEF_SERVICE").exists():
            return reverse("team_view")      # /agents/team/
        return reverse("dashboard")          # /dashboard/


@login_required
def agent_dashboard(request):
    if request.user.groups.filter(name="CNS").exists():
        return redirect("cns_dashboard")
    agent = getattr(request.user, "agent_profile", None)

    # si aucun agent lié au user
    if not agent:
        return render(request, "accounts/dashboard.html", {"agent": None})

    from agents.models import Contribution

    now = timezone.now()
    since_week = now - timedelta(days=7)

    qs = Contribution.objects.filter(agent=agent)

    stats = {
        "total": qs.count(),
        "draft": qs.filter(statut="DRAFT").count(),
        "submitted": qs.filter(statut="SUBMITTED").count(),
        "validated": qs.filter(statut="VALIDATED").count(),
        "week": qs.filter(date_creation__gte=since_week).count(),
    }

    last_items = qs.order_by("-date_creation")[:6]

    return render(
        request,
        "accounts/dashboard.html",
        {"agent": agent, "stats": stats, "last_items": last_items},
    )
