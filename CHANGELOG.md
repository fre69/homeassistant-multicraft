# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

Tous les changements notables de ce projet seront documentés dans ce fichier.

Le format est basé sur [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/),
et ce projet adhère à [Semantic Versioning](https://semver.org/lang/fr/).

---

## [1.2.0] - 2026-02-18

### Added / Ajouté
- FTP backup rotation: after each backup, files are renamed with date suffix (e.g., `world_20260218_093124.zip`) on both local storage and FTP server
- 4 new configurable backup options in integration settings (Options flow):
  - **Default backup destination path** (default: empty, fallback to `/media/multicraft_backups/`)
  - **Backup rotation** toggle (default: disabled)
  - **Backup retention** in days (default: 7, 0 = keep all) — automatic cleanup on both local storage and FTP server
  - **Keep backup on server** after download (default: enabled)
- Automatic cleanup of old backups (local + FTP) based on retention setting after each backup
- Option to automatically delete backup from Minecraft server after successful FTP download

---

- Rotation des sauvegardes : après chaque sauvegarde, les fichiers sont renommés avec un suffixe date (ex : `world_20260218_093124.zip`) sur le stockage local et le serveur FTP
- 4 nouvelles options de sauvegarde configurables dans les paramètres de l'intégration (flux Options) :
  - **Chemin de destination par défaut** (défaut : vide, fallback vers `/media/multicraft_backups/`)
  - **Rotation des sauvegardes** activable/désactivable (défaut : désactivé)
  - **Conservation des sauvegardes** en jours (défaut : 7, 0 = tout garder) — nettoyage automatique sur le stockage local et le serveur FTP
  - **Conserver la sauvegarde sur le serveur** après téléchargement (défaut : activé)
- Nettoyage automatique des anciennes sauvegardes (local + FTP) basé sur la durée de rétention après chaque sauvegarde
- Option de suppression automatique de la sauvegarde du serveur Minecraft après téléchargement FTP réussi

### Fixed / Corrigé
- Fix backup polling exiting too early before backup actually started (wait for "running" status)
- Fix backup polling failing on transient connection errors (retry up to 5 times)

---

- Correction du polling de sauvegarde qui sortait trop tôt avant le démarrage effectif du backup (attente du statut "running")
- Correction du polling de sauvegarde qui échouait sur les erreurs de connexion transitoires (réessai jusqu'à 5 fois)

### Changed / Modifié
- Backup button and `download_backup` service now share the same unified code path (`async_backup_and_download`)
- Button press runs backup in background; service call is blocking (same logic, different execution mode)
- Service `destination_path` parameter now overrides the default destination from settings (previously was always required)
- Without FTP password: both button and service gracefully fall back to a simple server-side backup (no error)

---

- Le bouton de sauvegarde et le service `download_backup` utilisent désormais le même chemin de code unifié (`async_backup_and_download`)
- Le bouton lance la sauvegarde en arrière-plan ; l'appel de service est bloquant (même logique, mode d'exécution différent)
- Le paramètre `destination_path` du service surcharge désormais la destination par défaut des paramètres (auparavant toujours requis)
- Sans mot de passe FTP : le bouton et le service font un simple backup côté serveur sans erreur (fallback gracieux)

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

[1.2.0]: https://github.com/fre69/homeassistant-multicraft/releases/tag/v1.2.0
[1.1.0]: https://github.com/fre69/homeassistant-multicraft/releases/tag/v1.1.0
[1.0.1]: https://github.com/fre69/homeassistant-multicraft/releases/tag/v1.0.1
[1.0.0]: https://github.com/fre69/homeassistant-multicraft/releases/tag/v1.0.0
