# Multicraft Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

This integration allows you to control your Minecraft servers managed by Multicraft from Home Assistant.

*[Version française ci-dessous](#intégration-multicraft-pour-home-assistant)*

## Features

- **Switch**: Start/stop your Minecraft server
- **Sensors**:
  - Server status (Online/Offline/Starting/Stopping)
  - Number of players online
  - Maximum players
- UI-based configuration
- Multilingual support (English/French)

## Installation

### Method 1: Via HACS (recommended)

1. Make sure [HACS](https://hacs.xyz/) is installed
2. Go to HACS > Integrations
3. Click the three dots in the top right corner > Custom repositories
4. Add this URL: `https://github.com/fre69/homeassistant-multicraft`
5. Search for "Multicraft" and install
6. Restart Home Assistant

### Method 2: Manual installation

1. Download or clone this repository
2. Copy the `custom_components/multicraft` folder to your Home Assistant `custom_components/` directory
3. Restart Home Assistant
4. Go to **Settings** > **Devices & Services** > **Add Integration**
5. Search for "Multicraft" and follow the instructions

## Configuration

You will need:
- **API URL**: The URL of your Multicraft panel
  - For a local server: `http://192.168.8.8/multicraft` (or your local IP)
  - For a remote server: `https://example.com/multicraft`
- **Username**: Your Multicraft username
- **API Key**: Your API key (generated in your Multicraft user profile)
- **Server ID**: The numeric ID of your Minecraft server

### Local configuration example

If your Multicraft is on the local network (e.g., `192.168.8.8`), use:
- **API URL**: `http://192.168.8.8/multicraft`
  - Note: Use `http://` (without s) for local connections
  - The full URL will be automatically completed with `/api.php`
  - You can also simply enter `http://192.168.8.8` and the integration will automatically add `/multicraft/api.php`

**Valid URL examples:**
- `http://192.168.8.8/multicraft`
- `http://192.168.8.8` (will be automatically completed)
- `192.168.8.8` (will be completed with http:// and /multicraft/api.php)
- `https://example.com/multicraft` (for remote servers)

### Generate an API key

1. Log in to your Multicraft panel
2. Go to your user profile
3. Click "Generate API Key" in the left menu
4. Copy the generated key

> **Note**: Make sure the API is enabled in the Multicraft panel settings (Settings > Panel Configuration)

## Usage

Once configured, you will find:
- A **switch** entity to start/stop the server: `switch.multicraft_server_X`
- **Sensors** for status and players:
  - `sensor.multicraft_server_X_status`
  - `sensor.multicraft_server_X_players_online`
  - `sensor.multicraft_server_X_max_players`

You can use these entities in your Home Assistant automations.

## Automation examples

### Start the server at a specific time

```yaml
automation:
  - alias: "Start Minecraft server in the evening"
    trigger:
      - platform: time
        at: "18:00:00"
    action:
      - service: switch.turn_on
        target:
          entity_id: switch.multicraft_server_1
```

### Stop the server when no one is connected

```yaml
automation:
  - alias: "Stop server if empty"
    trigger:
      - platform: numeric_state
        entity_id: sensor.multicraft_server_1_players_online
        below: 1
        for:
          minutes: 30
    condition:
      - condition: state
        entity_id: switch.multicraft_server_1
        state: "on"
    action:
      - service: switch.turn_off
        target:
          entity_id: switch.multicraft_server_1
```

### Notification when the server starts

```yaml
automation:
  - alias: "Server start notification"
    trigger:
      - platform: state
        entity_id: sensor.multicraft_server_1_status
        to: "Online"
    action:
      - service: notify.mobile_app_your_phone
        data:
          message: "The Minecraft server is now online!"
```

## Support

- **Multicraft API Documentation**: https://www.multicraft.org/site/docs/api
- **GitHub Issues**: [Open an issue](https://github.com/fre69/homeassistant-multicraft/issues)

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

---

# Intégration Multicraft pour Home Assistant

Cette intégration permet de contrôler vos serveurs Minecraft gérés par Multicraft depuis Home Assistant.

## Fonctionnalités

- **Switch** : Démarrer/arrêter votre serveur Minecraft
- **Capteurs** :
  - Statut du serveur (En ligne/Hors ligne/Démarrage/Arrêt)
  - Nombre de joueurs en ligne
  - Nombre maximum de joueurs
- Configuration via l'interface utilisateur
- Support multilingue (Français/Anglais)

## Installation

### Méthode 1 : Via HACS (recommandé)

1. Assurez-vous que [HACS](https://hacs.xyz/) est installé
2. Allez dans HACS > Intégrations
3. Cliquez sur les trois points en haut à droite > Dépôts personnalisés
4. Ajoutez cette URL : `https://github.com/fre69/homeassistant-multicraft`
5. Recherchez "Multicraft" et installez
6. Redémarrez Home Assistant

### Méthode 2 : Installation manuelle

1. Téléchargez ou clonez ce dépôt
2. Copiez le dossier `custom_components/multicraft` dans le répertoire `custom_components/` de votre installation Home Assistant
3. Redémarrez Home Assistant
4. Allez dans **Paramètres** > **Appareils et services** > **Ajouter une intégration**
5. Recherchez "Multicraft" et suivez les instructions

## Configuration

Vous aurez besoin de :
- **URL de l'API** : L'URL de votre panel Multicraft
  - Pour un serveur local : `http://192.168.8.8/multicraft` (ou votre IP locale)
  - Pour un serveur distant : `https://example.com/multicraft`
- **Nom d'utilisateur** : Votre nom d'utilisateur Multicraft
- **Clé API** : Votre clé API (générée dans le profil utilisateur de Multicraft)
- **ID du serveur** : L'ID numérique de votre serveur Minecraft

### Exemple de configuration locale

Si votre Multicraft est sur le réseau local (ex: `192.168.8.8`), utilisez :
- **URL de l'API** : `http://192.168.8.8/multicraft`
  - Note : Utilisez `http://` (sans s) pour les connexions locales
  - L'URL complète sera automatiquement complétée avec `/api.php`
  - Vous pouvez aussi simplement entrer `http://192.168.8.8` et l'intégration ajoutera automatiquement `/multicraft/api.php`

**Exemples d'URLs valides :**
- `http://192.168.8.8/multicraft`
- `http://192.168.8.8` (sera complété automatiquement)
- `192.168.8.8` (sera complété avec http:// et /multicraft/api.php)
- `https://example.com/multicraft` (pour les serveurs distants)

### Générer une clé API

1. Connectez-vous à votre panel Multicraft
2. Allez dans votre profil utilisateur
3. Cliquez sur "Generate API Key" dans le menu de gauche
4. Copiez la clé générée

> **Note** : Assurez-vous que l'API est activée dans les paramètres du panel Multicraft (Settings > Panel Configuration)

## Utilisation

Une fois configurée, vous trouverez :
- Une entité **switch** pour démarrer/arrêter le serveur : `switch.multicraft_server_X`
- Des **capteurs** pour le statut et les joueurs :
  - `sensor.multicraft_server_X_status`
  - `sensor.multicraft_server_X_joueurs_en_ligne`
  - `sensor.multicraft_server_X_joueurs_maximum`

Vous pouvez utiliser ces entités dans vos automatisations Home Assistant.

## Exemples d'automatisations

### Démarrer le serveur à une heure précise

```yaml
automation:
  - alias: "Démarrer le serveur Minecraft le soir"
    trigger:
      - platform: time
        at: "18:00:00"
    action:
      - service: switch.turn_on
        target:
          entity_id: switch.multicraft_server_1
```

### Arrêter le serveur quand personne n'est connecté

```yaml
automation:
  - alias: "Arrêter le serveur si vide"
    trigger:
      - platform: numeric_state
        entity_id: sensor.multicraft_server_1_joueurs_en_ligne
        below: 1
        for:
          minutes: 30
    condition:
      - condition: state
        entity_id: switch.multicraft_server_1
        state: "on"
    action:
      - service: switch.turn_off
        target:
          entity_id: switch.multicraft_server_1
```

### Notification quand le serveur démarre

```yaml
automation:
  - alias: "Notification démarrage serveur"
    trigger:
      - platform: state
        entity_id: sensor.multicraft_server_1_status
        to: "En ligne"
    action:
      - service: notify.mobile_app_votre_telephone
        data:
          message: "Le serveur Minecraft est maintenant en ligne !"
```

## Support

- **Documentation API Multicraft** : https://www.multicraft.org/site/docs/api
- **Issues GitHub** : [Ouvrir une issue](https://github.com/fre69/homeassistant-multicraft/issues)

## Licence

Ce projet est sous licence MIT. Voir le fichier [LICENSE](LICENSE) pour plus de détails.
