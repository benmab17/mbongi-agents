from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError


class Service(models.Model):
    nom = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.nom


class Agent(models.Model):
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    matricule = models.CharField(max_length=50, unique=True)

    service = models.ForeignKey(
        Service,
        on_delete=models.PROTECT,
        related_name="agents"
    )

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    unite = models.CharField(max_length=100, blank=True, default="")
    fonction = models.CharField(max_length=100, blank=True, default="")
    actif = models.BooleanField(default=True)

    photo = models.ImageField(
        upload_to="agents/photos/",
        blank=True,
        null=True
    )

    date_creation = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nom} {self.prenom} ({self.matricule})"


class Contribution(models.Model):
    STATUT_CHOICES = [
        ("DRAFT", "Brouillon"),
        ("SUBMITTED", "Soumise"),
        ("VALIDATED", "Validée"),
        ("REJECTED", "Rejetée"),
    ]

    agent = models.ForeignKey(
        Agent,
        on_delete=models.PROTECT,
        related_name="contributions"
    )

    titre = models.CharField(max_length=160)
    contenu = models.TextField()

    statut = models.CharField(
        max_length=20,
        choices=STATUT_CHOICES,
        default="DRAFT"
    )

    priorite = models.IntegerField(default=2)

    date_creation = models.DateTimeField(auto_now_add=True)
    date_mise_a_jour = models.DateTimeField(auto_now=True)

    # Validation hiérarchique
    validated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="validated_contributions"
    )
    validated_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.CharField(max_length=255, blank=True, default="")

    def __str__(self):
        return f"{self.titre} ({self.statut})"

class ContributionShare(models.Model):
    contribution = models.ForeignKey(Contribution, on_delete=models.CASCADE, related_name='shares')
    service_source = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='sent_shares')
    service_destinataire = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='received_shares')
    shared_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='made_shares')
    motif = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ('contribution', 'service_destinataire',) # A contribution can only be shared once with a specific service

    def __str__(self):
        return f"Partage de '{self.contribution.titre}' de {self.service_source.nom} à {self.service_destinataire.nom}"


class AuditLog(models.Model):
    """
    Journal d'audit pour les actions importantes.
    """
    ACTION_CHOICES = [
        ("LOGIN", "Connexion"),
        ("CREATE_CONTRIBUTION", "Création de contribution"),
        ("SUBMIT_CONTRIBUTION", "Soumission de contribution"),
        ("VALIDATE_CONTRIBUTION", "Validation de contribution"),
        ("CONTRIBUTION_SHARED", "Partage de contribution"), # Added new action
        ("TRANSMIT", "Transmission"),
        ("READ", "Lecture"),
        ("PRES_DECISION", "Validation Chef"),
        ("MIGRATE_STATUS", "Migration statut"),
        ("CNS_AVIS_CREATED", "CNS: creation avis"),
        ("UPDATE_MISSION", "Mise à jour de mission"),
        ("CREATE_DECISION", "Création de Décision"),
        ("VIEW_RDC_MAP_STATUS", "Vue Statut Carte RDC"),
        ("SYSTEM_WEAK_SIGNALS", "Calcul des signaux faibles"),
        ("CHEF_CREATE_RECOUPEMENT", "Chef: ouverture recoupement"),
        ("CHEF_TAKE_RECOUPEMENT", "Chef: prise en charge recoupement"),
        ("CHEF_CLOSE_RECOUPEMENT", "Chef: clôture recoupement"),
        ("CHEF_ASSIGN_RECOUPEMENT", "Chef: assignation recoupement"),
        ("AGENT_REPLY_RECOUPEMENT", "Agent: réponse recoupement"),
        ("CHEF_ESCALATE_RECOUPEMENT", "Chef: escalade en mission"),
        ("PRESIDENCE_CREATE_ORDER", "Présidence: création ordre"),
        ("PRESIDENCE_SIGN_ORDER", "Présidence: signature ordre"),
        ("PRESIDENCE_EXECUTE_ORDER", "Présidence: exécution ordre"),
        ("AGENT_STATUS_CHANGE", "Agent: changement statut"),
        ("MICROTASK_CLAIMED", "Agent: micro-tâche prise en charge"),
        ("MICROTASK_COMPLETED", "Agent: micro-tâche complétée"),
        ("FIELD_OBSERVATION_CREATED", "Agent: observation terrain créée"),
        ("CRISIS_MODE_ON", "Crise: mode activé"),
        ("CRISIS_MODE_OFF", "Crise: mode désactivé"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    action = models.CharField(max_length=40, choices=ACTION_CHOICES)
    target_repr = models.CharField(
        max_length=255, blank=True, help_text="Représentation textuelle de la cible de l'action"
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.user} a effectué '{self.get_action_display()}' le {self.timestamp}"

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding:
            raise ValidationError("AuditLog is append-only.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("AuditLog is append-only.")


class CNSAvis(models.Model):
    """
    Avis stratégique du CNS (lecture seule hors CNS).
    """
    URGENCY_CHOICES = [
        ("FAIBLE", "Faible"),
        ("MOYENNE", "Moyenne"),
        ("ELEVEE", "Elevee"),
        ("CRITIQUE", "Critique"),
    ]
    STATUS_CHOICES = [
        ("DRAFT", "Brouillon"),
        ("SENT", "Transmis"),
        ("TRANSMITTED", "Transmis"),
    ]
    DECISION_CHOICES = [
        ("PENDING", "En attente"),
        ("APPROVED", "Approuve"),
        ("REJECTED", "Rejete"),
    ]

    title = models.CharField(max_length=120)
    content = models.TextField()
    urgency = models.CharField(max_length=20, choices=URGENCY_CHOICES, default="MOYENNE")
    recommendation = models.TextField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    presidency_decision = models.CharField(
        max_length=20,
        choices=DECISION_CHOICES,
        default="PENDING",
    )
    decision_at = models.DateTimeField(null=True, blank=True)
    decision_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cns_avis_decisions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cns_avis",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="SENT")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} ({self.get_urgency_display()})"


class AgentStatus(models.Model):
    """
    Statut opérationnel actuel d'un agent.
    """
    STATUS_CHOICES = [
        ('AVAILABLE', 'Disponible'),
        ('PATROL', 'En patrouille'),
        ('RECOUPEMENT', 'En recoupement'),
        ('MISSION', 'En mission'),
    ]
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='agent_status')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='AVAILABLE')
    last_activity_at = models.DateTimeField(null=True, blank=True) # Pour tracking
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}: {self.get_status_display()}"


class RecoupementTicket(models.Model):
    """
    Ticket pour le suivi d'un recoupement d'information par un Chef de service,
    souvent initié à partir d'un signal faible.
    """
    STATUS_CHOICES = [
        ('OPEN', 'Ouvert'),
        ('IN_PROGRESS', 'En cours'),
        ('CLOSED', 'Clôturé'),
    ]
    LEVEL_CHOICES = [
        ('YELLOW', 'Jaune'),
        ('ORANGE', 'Orange'),
        ('RED', 'Rouge'),
    ]

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='created_recoupements')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='OPEN')
    level = models.CharField(max_length=10, choices=LEVEL_CHOICES, default='YELLOW')
    
    title = models.CharField(max_length=180)
    evidence = models.TextField()
    keywords = models.CharField(max_length=255, blank=True)
    
    window_hours = models.IntegerField(default=72)
    source = models.CharField(max_length=50, default="weak_signals")

    # Un chef peut prendre en charge un ticket avant de le clôturer
    taken_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='taken_recoupements')
    # Agents assignés pour répondre
    assigned_agents = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="assigned_recoupements", blank=True)
    due_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Recoupement [{self.level}] {self.title}"

    @property
    def is_overdue(self):
        """ Le ticket est-il en retard ? """
        if self.due_at and self.status != 'CLOSED':
            return timezone.now() > self.due_at
        return False

    @property
    def overdue_hours(self):
        """ Retourne le nombre d'heures de retard. """
        if self.is_overdue:
            delta = timezone.now() - self.due_at
            return int(delta.total_seconds() // 3600)
        return 0

    @property
    def overdue_level(self):
        """ Retourne un niveau de sévérité basé sur le retard. """
        hours = self.overdue_hours
        if hours > 24:
            return "RED"
        if hours > 12:
            return "ORANGE"
        if hours > 0:
            return "YELLOW"
        return None


class MicroTask(models.Model):
    """
    Petite tâche ponctuelle assignée automatiquement ou par un chef.
    """
    STATUS_CHOICES = [
        ('OPEN', 'Ouverte'),
        ('CLAIMED', 'Prise en charge'),
        ('DONE', 'Terminée'),
    ]
    TASK_TYPE_CHOICES = [
        ('SUMMARIZE', 'Résumer contenu'),
        ('TAG_KEYWORDS', 'Taguer mots-clés'),
        ('RATE_RELIABILITY', 'Évaluer fiabilité'),
        ('WATCH_THEME', 'Surveiller thème'),
        ('VERIFY_INFO', 'Vérifier information'),
    ]

    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='OPEN')
    task_type = models.CharField(max_length=30, choices=TASK_TYPE_CHOICES)
    title = models.CharField(max_length=180)
    instructions = models.TextField()
    
    # Liens vers des objets pertinents
    related_contribution = models.ForeignKey(Contribution, on_delete=models.SET_NULL, null=True, blank=True)
    related_recoupement = models.ForeignKey(RecoupementTicket, on_delete=models.SET_NULL, null=True, blank=True)

    claimed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='claimed_microtasks')
    claimed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Micro-tâche [{self.task_type}] - {self.title} ({self.status})"


class MicroMission(models.Model):
    """
    Micro-mission assignée à un agent (utilisateur).
    """
    STATUS_CHOICES = [
        ("PROPOSED", "Proposée"),
        ("TODO", "À faire"),
        ("IN_PROGRESS", "En cours"),
        ("DONE", "Terminée"),
    ]

    agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="micro_missions",
    )
    title = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="TODO",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} ({self.status})"


class MicroTaskResult(models.Model):
    """
    Résultat soumis par un agent pour une micro-tâche.
    """
    CONFIDENCE_CHOICES = [
        (1, 'Faible'),
        (2, 'Moyen'),
        (3, 'Élevé'),
    ]
    task = models.ForeignKey(MicroTask, on_delete=models.CASCADE, related_name="results")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='microtask_responses')
    created_at = models.DateTimeField(auto_now_add=True)
    content = models.TextField()
    confidence = models.IntegerField(choices=CONFIDENCE_CHOICES, default=2, help_text="Niveau de confiance du résultat")

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Résultat Micro-tâche #{self.task.id} par {self.author.username}"


class FieldObservation(models.Model):
    """
    Observation rapide rapportée par un agent sur le terrain.
    """
    MOOD_CHOICES = [
        ('CALM', 'Calme'),
        ('TENSE', 'Tendue'),
        ('UNUSUAL', 'Inhabituelle'),
        ('CRITICAL', 'Critique'),
    ]
    created_at = models.DateTimeField(auto_now_add=True)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='field_observations')
    zone = models.CharField(max_length=80)
    subject = models.CharField(max_length=120)
    mood = models.CharField(max_length=20, choices=MOOD_CHOICES, default='CALM')
    note = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Observation [{self.zone}] - {self.subject} ({self.get_mood_display()})"


class Mission(models.Model):
    """
    Représente une mission assignée à un agent par un supérieur.
    """
    STATUS_CHOICES = [
        ('PENDING', 'En attente'),
        ('IN_PROGRESS', 'En cours'),
        ('COMPLETED', 'Terminée'),
        ('FAILED', 'Échouée'),
    ]

    PRIORITY_CHOICES = [
        (1, 'Basse'),
        (2, 'Moyenne'),
        (3, 'Haute'),
        (4, 'Critique'),
    ]

    titre = models.CharField(max_length=200)
    description = models.TextField()
    agent_assigned = models.ForeignKey(
        Agent,
        on_delete=models.CASCADE,
        related_name='missions',
        verbose_name="Agent assigné"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_missions'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    priority = models.IntegerField(choices=PRIORITY_CHOICES, default=2)
    due_date = models.DateField(null=True, blank=True, verbose_name="Date limite")
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    report = models.TextField(blank=True, default="", verbose_name="Rapport de mission")
    reported_at = models.DateTimeField(null=True, blank=True)

    # Lien vers le recoupement d'origine si la mission est une escalade
    related_recoupement = models.ForeignKey(
        RecoupementTicket,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='escalated_missions'
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Mission {self.titre}"


class PresidentialOrder(models.Model):
    """
    Représente un ordre présidentiel formel initiant une action opérationnelle.
    """
    ORDER_TYPE_CHOICES = [
        ('DIRECTIVE', 'Directive'),
        ('OPERATION', 'Opération'),
        ('URGENCE', 'Urgence'),
    ]
    CLASSIFICATION_CHOICES = [
        ('CONFIDENTIEL', 'Confidentiel'),
        ('SECRET', 'Secret'),
        ('TRES_SECRET', 'Très Secret'),
    ]
    STATUS_CHOICES = [
        ('DRAFT', 'Brouillon'),
        ('SIGNED', 'Signé'),
        ('EXECUTED', 'Exécuté'),
        ('CANCELLED', 'Annulé'),
    ]

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='created_orders')
    
    title = models.CharField(max_length=255)
    content = models.TextField()
    
    order_type = models.CharField(max_length=20, choices=ORDER_TYPE_CHOICES, default='DIRECTIVE')
    classification = models.CharField(max_length=20, choices=CLASSIFICATION_CHOICES, default='CONFIDENTIEL')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    
    signed_at = models.DateTimeField(null=True, blank=True)
    due_at = models.DateTimeField(null=True, blank=True)
    
    target_service = models.ForeignKey(Service, on_delete=models.SET_NULL, null=True, blank=True)
    
    related_recoupement = models.ForeignKey(RecoupementTicket, on_delete=models.SET_NULL, null=True, blank=True, related_name='presidential_orders')
    related_mission = models.ForeignKey(Mission, on_delete=models.SET_NULL, null=True, blank=True, related_name='presidential_orders')
    related_contribution = models.ForeignKey(Contribution, on_delete=models.SET_NULL, null=True, blank=True, related_name='presidential_orders')

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Ordre #{self.id} [{self.order_type}] - {self.title} ({self.status})"


class Decision(models.Model):
    """
    Représente une décision formelle issue d'une contribution validée ou rejetée.
    """
    DECISION_TYPE_CHOICES = [
        ('OPERATIONNEL', 'Opérationnel'),
        ('STRATEGIQUE', 'Stratégique'),
    ]

    DECISION_LEVEL_CHOICES = [
        ('CHEF', 'Chef de service'),
        ('PRESIDENCE', 'Présidence'),
    ]

    DECISION_RESULT_CHOICES = [
        ('VALIDEE', 'Validée'),
        ('REFUSEE', 'Refusée'),
        ('ORDONNEE', 'Ordonnée'), # Pour les décisions initiées sans contribution directe
    ]

    title = models.CharField(max_length=255, verbose_name="Titre de la décision")
    decision_type = models.CharField(max_length=20, choices=DECISION_TYPE_CHOICES, default='OPERATIONNEL')
    level = models.CharField(max_length=20, choices=DECISION_LEVEL_CHOICES, default='CHEF')
    contribution = models.ForeignKey(Contribution, on_delete=models.CASCADE, related_name='decisions', null=True, blank=True)
    decision = models.CharField(max_length=20, choices=DECISION_RESULT_CHOICES)
    comment = models.TextField(blank=True, verbose_name="Commentaire de décision")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='made_decisions')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Décision {self.get_decision_display()} sur '{self.title}' (Niveau: {self.level})"
