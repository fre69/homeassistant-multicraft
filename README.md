# Intégration Multicraft pour Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Cette intégration permet de contrôler vos serveurs Minecraft gérés par Multicraft depuis Home Assistant.

## Fonctionnalités

- ✅ **Switch** : Démarrer/arrêter votre serveur Minecraft
- ✅ **Capteurs** : 
  - Statut du serveur (En ligne/Hors ligne/Démarrage/Arrêt)
  - Nombre de joueurs en ligne
  - Nombre maximum de joueurs
- ✅ Configuration via l'interface utilisateur
- ✅ Support multilingue (Français/Anglais)

## Installation

### Méthode 1 : Via HACS (recommandé)

1. Assurez-vous que [HACS](https://hacs.xyz/) est installé
2. Allez dans HACS > Intégrations
3. Cliquez sur les trois points en haut à droite > Intégrations personnalisées
4. Ajoutez cette URL : `https://github.com/VOTRE-USERNAME/homeassistant-multicraft`
5. Recherchez "Multicraft" et installez
6. Redémarrez Home Assistant

### Méthode 2 : Installation manuelle

1. Téléchargez ou clonez ce dépôt
2. Copiez le dossier `multicraft` dans `custom_components/` de votre installation Home Assistant
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
- `http://192.168.8.8/multicraft` ✅
- `http://192.168.8.8` ✅ (sera complété automatiquement)
- `192.168.8.8` ✅ (sera complété avec http:// et /multicraft/api.php)
- `https://example.com/multicraft` ✅ (pour les serveurs distants)

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

## Captures d'écran

*(Ajoutez des captures d'écran de l'intégration dans Home Assistant si vous en avez)*

## Développement

### Structure du projet

```
multicraft/
├── __init__.py          # Initialisation de l'intégration
├── api.py               # Client API Multicraft
├── config_flow.py       # Configuration via UI
├── const.py             # Constantes
├── sensor.py            # Entités capteurs
├── switch.py            # Entité switch
├── manifest.json        # Métadonnées
├── translations/        # Traductions
│   ├── en.json
│   └── fr.json
└── README.md
```

## Contribution

Les contributions sont les bienvenues ! N'hésitez pas à :
- Ouvrir une issue pour signaler un bug ou proposer une fonctionnalité
- Créer une pull request pour améliorer le code

## Support

- **Documentation API Multicraft** : https://www.multicraft.org/site/docs/api
- **Issues GitHub** : [Ouvrir une issue](https://github.com/VOTRE-USERNAME/homeassistant-multicraft/issues)

## Licence

Ce projet est sous licence MIT. Voir le fichier [LICENSE](LICENSE) pour plus de détails.

## Auteur

Créé avec ❤️ pour la communauté Home Assistant

