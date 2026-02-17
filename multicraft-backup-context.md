# Context pour Claude Code : Ajout de la fonctionnalité Backup à l'intégration Multicraft HA

## Objectif

Ajouter une fonctionnalité de backup automatisé des serveurs Minecraft à l'intégration Home Assistant Multicraft (`homeassistant-multicraft`). L'intégration existe déjà et est publiée sur HACS.

## Fonctionnalités à implémenter

### 1. Nouvelles méthodes API (`api.py`)

Ajouter à la classe `MulticraftAPI` les méthodes suivantes basées sur la doc officielle Multicraft (https://www.multicraft.org/site/docs/api) :

```python
async def start_server_backup(self, server_id: int) -> dict[str, Any]:
    """Start a server backup."""
    return await self._call_api("startServerBackup", id=server_id)

async def get_server_backup_status(self, server_id: int) -> dict[str, Any]:
    """Get server backup status.
    
    Returns:
        dict with keys:
        - status: 'running' | 'completed' | etc.
        - time: backup duration
        - message: progress message (e.g., '[World: world]')
        - file: path to backup file on server
        - ftp: FTP address (e.g., '192.168.8.8:21')
    """
    return await self._call_api("getServerBackupStatus", id=server_id)
```

### 2. Nouveau sensor backup_status (`sensor.py`)

Ajouter un nouveau `SensorEntityDescription` pour le statut du backup :

```python
SensorEntityDescription(
    key="backup_status",
    translation_key="backup_status",
    icon="mdi:backup-restore",
)
```

Le sensor doit afficher : "Inactif", "En cours", "Terminé", "Erreur"

Le statut du backup doit être récupéré dans `async_update_data()` de `__init__.py` en appelant `get_server_backup_status()` et stocké dans `server_data["backup_status"]`.

Les extra_state_attributes du sensor backup doivent inclure :
- `backup_file` : chemin du fichier backup
- `backup_ftp` : adresse FTP
- `backup_message` : message de progression
- `last_backup_time` : timestamp du dernier backup terminé

### 3. Nouveau bouton backup (`button.py`) — NOUVEAU FICHIER

Créer un nouveau fichier `button.py` avec une entité `ButtonEntity` :

- Entité : `button.multicraft_{server_name}_backup`
- Nom affiché : "Backup"
- Icône : `mdi:backup-restore`
- Action `async_press()` : appelle `api.start_server_backup(server_id)` puis force un refresh du coordinator

Ne pas oublier d'ajouter `"button"` à la liste `PLATFORMS` dans `__init__.py`.

### 4. Service `multicraft.download_backup` — NOUVEAU

Enregistrer un service HA dans `__init__.py` qui :

1. Appelle `startServerBackup(server_id)`
2. Polling de `getServerBackupStatus(server_id)` toutes les 5 secondes jusqu'à ce que le statut ne soit plus `running` (timeout 10 minutes)
3. Une fois terminé, récupère le fichier via FTP (les infos FTP sont dans la réponse de `getServerBackupStatus`)
4. Télécharge le fichier backup vers un chemin configurable (par défaut `/media/multicraft_backups/`)

Le service doit accepter ces paramètres :
- `server_id` (requis) : ID du serveur
- `destination_path` (optionnel) : chemin de destination, défaut `/media/multicraft_backups/`

Les identifiants FTP sont construits automatiquement :
- FTP host : extrait de la réponse `getServerBackupStatus` (champ `ftp`, format `IP:port`)
- FTP username : `admin.{server_id}` (convention Multicraft)
- FTP password : stocké dans la config de l'intégration (ajouté au config_flow)

### 4b. Mise à jour du config_flow (`config_flow.py`)

Ajouter un champ optionnel `ftp_password` dans le step de configuration utilisateur. Ce champ est de type `password` (masqué dans l'UI). Il est optionnel — s'il n'est pas renseigné, la fonctionnalité de téléchargement FTP sera désactivée mais le bouton backup (qui lance juste le backup côté Multicraft sans télécharger) fonctionnera quand même.

Ajouter `CONF_FTP_PASSWORD = "ftp_password"` dans `const.py`.

Créer un fichier `services.yaml` pour déclarer le service.

Pour le téléchargement FTP, utiliser `aioftp` ou le module standard `ftplib` en async wrapper. Attention : HA OS a un accès limité au filesystem, `/media/` est le bon endroit pour stocker des fichiers accessibles.

### 5. Mises à jour des traductions

Mettre à jour `translations/en.json` et `translations/fr.json` pour ajouter :
- Les labels du sensor backup_status
- Les labels du bouton backup  
- La description du service

### 6. Mise à jour du README

Ajouter une section documentant :
- Le nouveau sensor backup_status
- Le nouveau bouton backup
- Le service multicraft.download_backup
- Un exemple d'automatisation qui :
  1. Déclenche un backup tous les jours à 4h du matin
  2. Télécharge le backup vers /media/
  3. Envoie une notification quand c'est terminé

Exemple d'automatisation pour le README :

```yaml
automation:
  - alias: "Backup quotidien Minecraft"
    trigger:
      - platform: time
        at: "04:00:00"
    action:
      - service: multicraft.download_backup
        data:
          server_id: 4
          destination_path: "/media/multicraft_backups/"
      
  - alias: "Notification backup terminé"
    trigger:
      - platform: event
        event_type: multicraft_backup_completed
    action:
      - service: notify.mobile_app_votre_telephone
        data:
          message: "Backup Minecraft terminé : {{ trigger.event.data.file }}"
```

## Architecture actuelle du projet

```
custom_components/multicraft/
├── __init__.py        # Setup, coordinator, platforms = ["switch", "sensor"]
├── api.py             # MulticraftAPI class avec _call_api(), get_server_status(), start/stop/restart_server()
├── config_flow.py     # Config flow UI
├── const.py           # DOMAIN, CONF_*, DEFAULT_SCAN_INTERVAL
├── manifest.json      # version 1.0.1
├── sensor.py          # Sensors: status, onlinePlayers, maxPlayers, latency, version
├── switch.py          # Switch on/off serveur
└── translations/
    ├── en.json
    └── fr.json
```

## Points importants

- L'API Multicraft utilise HMAC-SHA256 pour la signature (déjà implémenté dans `_call_api`)
- Le coordinator (`DataUpdateCoordinator`) refresh toutes les 30 secondes par défaut
- Chaque serveur a son propre set d'entités, identifié par `server_id`
- Les entités sont groupées par device (`DeviceInfo` avec `identifiers={(DOMAIN, f"{entry_id}_{server_id}")}`)
- Le `slugify()` est défini localement (pas celui de HA)
- La version actuelle est 1.0.1, la prochaine sera 1.1.0
- Le projet utilise un workflow GitHub Actions pour les releases automatiques sur tag `v*.*.*`
- Le CHANGELOG est bilingue (EN/FR)

## Réponse API Multicraft pour le backup

```
startServerBackup(id) → { success: true, errors: [], data: {} }

getServerBackupStatus(id) → {
    success: true,
    errors: [],
    data: {
        status: 'running',        // ou 'completed', etc.
        time: '0',                // durée
        message: '[World: world] ',
        file: '/path/to/world.zip',
        ftp: '192.168.8.8:21'     // adresse FTP pour télécharger
    }
}
```

## Configuration FTP Multicraft

Chaque serveur hébergé sur Multicraft a son propre accès FTP :
- **FTP Address** : même IP que le panel Multicraft (ex: 192.168.8.8)
- **FTP Port** : 21
- **FTP Username** : format `admin.{server_id}` (ex: `admin.4` pour le serveur ID 4)
- **FTP Password** : mot de passe Multicraft de l'utilisateur (PAS la clé API, c'est le password du compte panel)

Le mot de passe FTP doit être ajouté à la configuration de l'intégration. Ajouter un champ optionnel `ftp_password` dans le config_flow (step user ou step séparé). Ce champ est nécessaire uniquement pour la fonctionnalité backup/download.

Le fichier backup est un .zip du world, déposé dans le répertoire du serveur sur le FTP.

## Considérations HA OS

- Les fichiers doivent être écrits dans `/media/` pour être accessibles depuis HA
- Le propriétaire a un partage Samba NAS monté sur HA à `//192.168.8.2/WD` via l'addon "Samba NAS". Ce partage est accessible depuis HA comme stockage réseau. Le chemin de destination idéal serait configurable, avec `/media/` comme défaut.
- Pas de `pip install` possible dans HA OS, utiliser uniquement les modules Python standard (`ftplib`) ou les dépendances déjà disponibles dans HA
- Le service doit fire un event `multicraft_backup_completed` quand le backup est terminé (pour permettre des automatisations)

## Statut du backup Multicraft

D'après les tests sur le panel Multicraft, les statuts du backup sont :
- **En cours** : le panel affiche "Backup in progress" — l'API retourne probablement `status: 'running'`
- **Terminé** : le panel affiche "Backup completed. (Last backup: 2026-02-15 21:10)" — l'API retourne probablement `status: 'completed'`
- Quand aucun backup n'a été lancé, le statut est probablement vide ou absent

Il faudra gérer ces cas et éventuellement d'autres valeurs inconnues avec un fallback.

## Ne PAS faire de release

Ne pas créer de tag, ne pas push, ne pas faire de release. Juste implémenter le code et mettre à jour les fichiers nécessaires. Je ferai la release moi-même.
