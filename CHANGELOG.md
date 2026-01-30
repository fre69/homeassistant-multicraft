# Changelog

Tous les changements notables de ce projet seront documentés dans ce fichier.

Le format est basé sur [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/),
et ce projet adhère à [Semantic Versioning](https://semver.org/lang/fr/).

## [1.0.1] - 2025-01-30

### Corrigé
- Correction du capteur Latence et Version qui affichaient "Inconnu" quand l'API Multicraft retournait l'IP 0.0.0.0
- Utilisation automatique de l'IP du panneau Multicraft comme fallback pour le ping Minecraft
- Correction du protocole de ping Minecraft (lecture correcte des VarInt)
- Correction de l'erreur 500 lors de l'ouverture des options de l'intégration (compatibilité Home Assistant 2024.x+)
- Amélioration de la gestion du cache pour éviter les appels API inutiles dans le flux d'options

## [1.0.0] - 2025-01-XX

### Ajouté
- Intégration initiale de Multicraft pour Home Assistant
- Entité switch pour démarrer/arrêter les serveurs Minecraft
- Capteurs pour le statut du serveur et le nombre de joueurs
- Configuration via l'interface utilisateur (config flow)
- Support multilingue (Français/Anglais)
- Documentation complète

[1.0.1]: https://github.com/fre69/homeassistant-multicraft/releases/tag/v1.0.1
[1.0.0]: https://github.com/fre69/homeassistant-multicraft/releases/tag/v1.0.0

