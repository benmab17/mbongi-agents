from django.urls import path
from .views import AgentLoginView, agent_dashboard
from django.contrib.auth.views import LogoutView


urlpatterns = [
    path("login/", AgentLoginView.as_view(), name="login"),
    path("dashboard/", agent_dashboard, name="dashboard"),
    path("logout/", LogoutView.as_view(), name="logout")
]
