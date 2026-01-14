from django import forms
from .models import (
    Contribution, Agent, Mission,
    PresidentialOrder, Service, RecoupementTicket, ContributionShare, CNSAvis
)
from django.forms import DateTimeInput


class ContributionForm(forms.ModelForm):
    class Meta:
        model = Contribution
        fields = ["titre", "contenu", "priorite"]


class AgentPhotoForm(forms.ModelForm):
    class Meta:
        model = Agent
        fields = ["photo"]

class MissionForm(forms.ModelForm):
    class Meta:
        model = Mission
        fields = ['titre', 'description', 'agent_assigned', 'priority', 'due_date']
        widgets = {
            'due_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        # Limiter le choix des agents à ceux du service du chef
        service = kwargs.pop('service', None)
        super().__init__(*args, **kwargs)
        if service:
            self.fields['agent_assigned'].queryset = Agent.objects.filter(service=service)

class MissionUpdateForm(forms.ModelForm):

    class Meta:

        model = Mission

        fields = ['status', 'report']

        widgets = {

            'report': forms.Textarea(attrs={'rows': 6}),

        }



    def clean(self):

        cleaned_data = super().clean()

        status = cleaned_data.get("status")

        report = cleaned_data.get("report")



        if status == 'COMPLETED' and (not report or len(report) < 30):

            raise forms.ValidationError(

                "Un rapport de mission d'au moins 30 caractères est obligatoire pour marquer la mission comme 'Terminée'."

            )

        return cleaned_data


class ContributionShareForm(forms.ModelForm):
    class Meta:
        model = ContributionShare
        fields = ['service_destinataire', 'motif']
        widgets = {
            'motif': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Exclure le service source de la liste des services destinataires
        # Le service source sera déterminé dans la vue
        # Pour V1, on peut simplement lister tous les services sauf l'actuel
        # si on le passe en paramètre. Pour l'instant, on liste tout.
        self.fields['service_destinataire'].queryset = Service.objects.all().order_by('nom')


class DGMAnomalyForm(forms.Form):
    ANOMALY_CHOICES = [
        ("Document", "Document"),
        ("Identité", "Identité"),
        ("Comportement", "Comportement"),
        ("Flux", "Flux"),
        ("Autre", "Autre"),
    ]
    URGENCY_CHOICES = [
        ("Faible", "Faible"),
        ("Moyenne", "Moyenne"),
        ("Élevée", "Élevée"),
    ]

    anomaly_type = forms.ChoiceField(choices=ANOMALY_CHOICES)
    location = forms.CharField()
    description = forms.CharField(widget=forms.Textarea)
    urgency = forms.ChoiceField(choices=URGENCY_CHOICES)


class EmbassyDiplomaticReportForm(forms.Form):
    REPORT_TYPE_CHOICES = [
        ("Réseau / influence", "R&eacute;seau / influence"),
        ("Pression / menace", "Pression / menace"),
        ("Document / visa", "Document / visa"),
        ("Incident consulaire", "Incident consulaire"),
        ("Autre", "Autre"),
    ]
    URGENCY_CHOICES = [
        ("Faible", "Faible"),
        ("Moyenne", "Moyenne"),
        ("Élevée", "&Eacute;lev&eacute;e"),
    ]

    report_type = forms.ChoiceField(
        choices=REPORT_TYPE_CHOICES,
        label="Type de signalement",
    )
    country_city = forms.CharField(label="Pays / Ville")
    description = forms.CharField(
        label="Description",
        widget=forms.Textarea,
    )
    urgency = forms.ChoiceField(
        choices=URGENCY_CHOICES,
        label="Urgence",
    )


class DGMWatchlistForm(forms.Form):
    RISK_CHOICES = [
        ("Faible", "Faible"),
        ("Moyen", "Moyen"),
        ("Élevé", "Élevé"),
    ]

    identity_hint = forms.CharField(label="Identité / Alias (si connu)")
    border_post = forms.CharField(label="Poste / Lieu")
    reason = forms.CharField(
        label="Motif de vigilance",
        widget=forms.Textarea,
    )
    risk_level = forms.ChoiceField(choices=RISK_CHOICES, label="Niveau de risque")
    optional_notes = forms.CharField(
        label="Notes (optionnel)",
        widget=forms.Textarea,
        required=False,
    )


class AgentProposeMicroMissionForm(forms.Form):
    title = forms.CharField(max_length=120, label="Titre")
    description = forms.CharField(
        label="Détails (optionnel)",
        widget=forms.Textarea,
        required=False,
    )


class ChefCreateMicroMissionForm(forms.Form):
    agent = forms.ModelChoiceField(queryset=Agent.objects.none(), label="Agent")
    title = forms.CharField(max_length=120, label="Titre")
    description = forms.CharField(
        label="Détails (optionnel)",
        widget=forms.Textarea,
        required=False,
    )
    initial_status = forms.ChoiceField(
        choices=[("TODO", "À faire")],
        label="Statut initial",
        initial="TODO",
    )

    def __init__(self, *args, **kwargs):
        service = kwargs.pop("service", None)
        super().__init__(*args, **kwargs)
        if service:
            self.fields["agent"].queryset = Agent.objects.filter(
                service=service,
                user__isnull=False,
            ).order_by("nom")


class CNSAvisForm(forms.ModelForm):
    class Meta:
        model = CNSAvis
        fields = ["title", "content", "urgency", "recommendation"]
        labels = {
            "title": "Titre",
            "content": "Contenu",
            "urgency": "Urgence",
            "recommendation": "Recommandation (optionnel)",
        }
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "content": forms.Textarea(attrs={"rows": 6, "class": "form-control"}),
            "urgency": forms.Select(attrs={"class": "form-select"}),
            "recommendation": forms.Textarea(attrs={"rows": 4, "class": "form-control"}),
        }
