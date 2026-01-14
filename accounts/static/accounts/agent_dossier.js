/**
 * Script d'animation pour le Dossier Agent
 * Conçu pour fonctionner sans dépendances externes.
 */
document.addEventListener('DOMContentLoaded', () => {

    // Élément pour l'heure du journal
    const logTimeElement = document.getElementById('log-time');
    // Éléments pour la biométrie
    const heartRateElement = document.getElementById('bio-heart-rate');
    const tempElement = document.getElementById('bio-temp');
    // Élément pour l'effet de frappe
    const nameElement = document.getElementById('agent-name-typewriter');
    // Nœuds de la carte tactique
    const mapNodes = document.querySelectorAll('.map-node');

    /**
     * Met à jour l'horloge en temps réel.
     */
    function updateTime() {
        if (logTimeElement) {
            const now = new Date();
            const hours = String(now.getHours()).padStart(2, '0');
            const minutes = String(now.getMinutes()).padStart(2, '0');
            const seconds = String(now.getSeconds()).padStart(2, '0');
            logTimeElement.textContent = `${hours}:${minutes}:${seconds}`;
        }
    }

    /**
     * Simule les changements de données biométriques.
     */
    function updateBiometrics() {
        if (heartRateElement) {
            const baseRate = 70;
            const randomFluctuation = Math.floor(Math.random() * 5); // 0 à 4
            heartRateElement.textContent = String(baseRate + randomFluctuation);
        }
        if (tempElement) {
            const baseTemp = 37.0;
            const randomFluctuation = (Math.random() * 0.5).toFixed(1); // 0.0 à 0.4
            tempElement.textContent = String((baseTemp + parseFloat(randomFluctuation)).toFixed(1));
        }
    }
    
    /**
     * Anime les nœuds sur la carte tactique.
     */
    function updateMapActivity() {
        if (mapNodes.length === 0) return;
        
        // Désactive un nœud au hasard
        const activeNode = document.querySelector('.map-node.active');
        if (activeNode) {
            activeNode.classList.remove('active');
        }

        // Active un nouveau nœud au hasard
        const randomIndex = Math.floor(Math.random() * mapNodes.length);
        mapNodes[randomIndex].classList.add('active');
    }

    /**
     * Crée un effet de machine à écrire pour le texte d'un élément.
     * @param {HTMLElement} element - L'élément HTML cible.
     * @param {number} speed - Vitesse de frappe en millisecondes.
     */
    function typewriterEffect(element, speed = 75) {
        if (!element) return;
        const text = element.textContent;
        element.textContent = '';
        let i = 0;

        function type() {
            if (i < text.length) {
                element.textContent += text.charAt(i);
                i++;
                setTimeout(type, speed);
            }
        }
        type();
    }

    // Lancement des fonctions à intervalles réguliers
    setInterval(updateTime, 1000);
    setInterval(updateBiometrics, 3000);
    setInterval(updateMapActivity, 2000);

    // Initialisation immédiate
    updateTime();
    updateBiometrics();
    updateMapActivity();
    typewriterEffect(nameElement);
});
