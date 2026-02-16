# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

Tous les changements notables de ce projet seront documentés dans ce fichier.

Le format est basé sur [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/),
et ce projet adhère à [Semantic Versioning](https://semver.org/lang/fr/).

---

## [1.1.0] - 2026-02-15

### Added / Ajouté
- Backup button entity to trigger server backups from Home Assistant
- Backup status sensor with real-time progress tracking
- `multicraft.download_backup` service for automated backup download via FTP
- FTP password field in integration configuration (optional)
- Events `multicraft_backup_completed` and `multicraft_backup_failed` for automations

---

- Bouton de sauvegarde pour déclencher les backups serveur depuis Home Assistant
- Capteur d'état de sauvegarde avec suivi en temps réel
- Service `multicraft.download_backup` pour le téléchargement automatisé des sauvegardes via FTP
- Champ mot de passe FTP dans la configuration de l'intégration (optionnel)
- Événements `multicraft_backup_completed` et `multicraft_backup_failed` pour les automatisations

## [1.0.1] - 2025-01-30

### Fixed / Corrigé
- Fix Latency and Version sensors showing "Unknown" when Multicraft API returns IP 0.0.0.0
- Automatic use of Multicraft panel IP as fallback for Minecraft ping
- Fix Minecraft ping protocol (correct VarInt reading)
- Fix 500 error when opening integration options (Home Assistant 2024.x+ compatibility)
- Improve cache handling to avoid unnecessary API calls in options flow

---

- Correction du capteur Latence et Version qui affichaient "Inconnu" quand l'API Multicraft retournait l'IP 0.0.0.0
- Utilisation automatique de l'IP du panneau Multicraft comme fallback pour le ping Minecraft
- Correction du protocole de ping Minecraft (lecture correcte des VarInt)
- Correction de l'erreur 500 lors de l'ouverture des options de l'intégration (compatibilité Home Assistant 2024.x+)
- Amélioration de la gestion du cache pour éviter les appels API inutiles dans le flux d'options

## [1.0.0] - 2025-01-28

### Added / Ajouté
- Initial Multicraft integration for Home Assistant
- Switch entity to start/stop Minecraft servers
- Sensors for server status and player count
- Configuration via user interface (config flow)
- Multilingual support (French/English)
- Complete documentation

---

- Intégration initiale de Multicraft pour Home Assistant
- Entité switch pour démarrer/arrêter les serveurs Minecraft
- Capteurs pour le statut du serveur et le nombre de joueurs
- Configuration via l'interface utilisateur (config flow)
- Support multilingue (Français/Anglais)
- Documentation complète

[1.1.0]: https://github.com/fre69/homeassistant-multicraft/releases/tag/v1.1.0
[1.0.1]: https://github.com/fre69/homeassistant-multicraft/releases/tag/v1.0.1
[1.0.0]: https://github.com/fre69/homeassistant-multicraft/releases/tag/v1.0.0
