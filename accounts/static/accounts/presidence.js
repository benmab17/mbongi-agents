document.addEventListener('DOMContentLoaded', function() {
    const mapZoneGroups = document.querySelectorAll('.rdc-map-svg .map-zone'); // Cibler les groupes de zones SVG
    const detailPanel = document.querySelector('.cc-map-detail-panel');
    if (!detailPanel) return; // Quitter si le panneau n'existe pas

    const detailLabel = detailPanel.querySelector('.detail-label');
    const detailLevel = detailPanel.querySelector('.detail-level');
    const detailCount = detailPanel.querySelector('.detail-count');
    const detailJustification = detailPanel.querySelector('.detail-justification');
    const detailLastActivity = detailPanel.querySelector('.detail-last-activity');
    
    // Fonction pour afficher le panneau de détail
    function showDetailPanel(zoneGroup, event) {
        const level = zoneGroup.dataset.level;
        const label = zoneGroup.dataset.label;
        const count = zoneGroup.dataset.count;
        const justification = zoneGroup.dataset.justification;
        const lastActivity = zoneGroup.dataset.lastActivity;
        
        detailLabel.textContent = label;
        detailLevel.textContent = `Niveau: ${level.toUpperCase()}`;
        detailCount.textContent = `Contributions (7j): ${count}`;
        detailJustification.textContent = `Justification: ${justification}`;
        detailLastActivity.textContent = `Dern. activité: ${lastActivity}`;
        
        // Positionner le panneau près du curseur ou de la zone cliquée
        let panelX = event.clientX + 15;
        let panelY = event.clientY + 15;

        // Ajuster si le panneau sort de l'écran à droite ou en bas
        if (panelX + detailPanel.offsetWidth > window.innerWidth) {
            panelX = event.clientX - detailPanel.offsetWidth - 15;
        }
        if (panelY + detailPanel.offsetHeight > window.innerHeight) {
            panelY = window.innerHeight - detailPanel.offsetHeight - 15;
        }
        detailPanel.style.left = `${panelX}px`;
        detailPanel.style.top = `${panelY}px`;

        detailPanel.classList.add('visible');
        zoneGroup.classList.add('active'); // Mettre en évidence la zone sur la carte
    }

    // Fonction pour cacher le panneau
    function hideDetailPanel(zoneGroup) {
        detailPanel.classList.remove('visible');
        zoneGroup.classList.remove('active');
    }

    mapZoneGroups.forEach(zoneGroup => {
        // Hover (MouseEnter) - pour afficher les détails
        zoneGroup.addEventListener('mouseenter', function(event) {
            showDetailPanel(this, event);
        });

        // Hover (MouseLeave) - pour cacher les détails
        zoneGroup.addEventListener('mouseleave', function() {
            hideDetailPanel(this);
        });

        // Clic - pour naviguer
        zoneGroup.addEventListener('click', function() {
            const zoneName = this.dataset.zone;
            if (zoneName) {
                window.location.search = `zone=${zoneName}`;
            }
        });
    });
});

