# Instructions pour Claude

## Vue d'ensemble du projet

Intégration Home Assistant pour contrôler des serveurs Minecraft via l'API Multicraft.
- **Domaine :** `multicraft`
- **Version actuelle :** voir `custom_components/multicraft/manifest.json`
- **Config version :** 3 (migration dans `__init__.py:async_migrate_entry`)
- **Dépendances externes :** aucune (uniquement les libs HA core)
- **HA minimum :** 2023.1.0
- **IOT class :** `local_polling` (DataUpdateCoordinator, 30s par défaut)
- **Langue du code :** anglais pour le code, bilingue EN/FR pour la documentation et les traductions

## Architecture et fichiers clés

```
custom_components/multicraft/
├── __init__.py        # Setup, DataUpdateCoordinator, service download_backup, ping Minecraft
├── api.py             # Client HTTP async Multicraft (HMAC-SHA256), parsing URL intelligent
├── config_flow.py     # Flow 2 étapes (credentials → sélection serveurs) + OptionsFlow
├── const.py           # Constantes : DOMAIN, CONF_*, DEFAULT_SCAN_INTERVAL
├── sensor.py          # 6 capteurs par serveur (status, onlinePlayers, maxPlayers, latency, version, backup_status)
├── switch.py          # 1 switch par serveur (start/stop)
├── button.py          # 1 bouton par serveur (déclencher backup)
├── services.yaml      # Définition du service download_backup (device selector)
├── manifest.json      # Métadonnées (version, domain, codeowners)
├── translations/
│   ├── en.json        # Traductions anglaises (config flow + options)
│   └── fr.json        # Traductions françaises
```

## Conventions de nommage des entités

```
Unique ID :  multicraft_{server_id}_{type}     ex: multicraft_5_status
Entity ID :  {platform}.multicraft_{slug}_{key} ex: sensor.multicraft_survival_server_status
Device ID :  (DOMAIN, f"{entry_id}_{server_id}")
```

Plateformes : `switch`, `sensor`, `button` (déclarées dans `PLATFORMS` de `__init__.py`)

## Structure de données du Coordinator

```python
coordinator.data = {
    "server_id": {
        "status": "online|offline|starting|stopping",
        "onlinePlayers": int,
        "maxPlayers": int,
        "latency": int|None,        # ms, via ping Minecraft protocol
        "version": str|None,        # depuis ping Minecraft
        "players": [...],
        "backup_status": "idle|running|completed|error",
        "backup_file": str, "backup_ftp": str, "backup_message": str, "backup_time": str,
        "server_name": str,
        "error": str|None,
    }
}
```

## API Multicraft (api.py)

**Authentification :** HMAC-SHA256 sur les paramètres triés alphabétiquement.

**Méthodes API utilisées :**
| Méthode Python | API Multicraft | Usage |
|---|---|---|
| `get_server_status(id)` | `getServerStatus` | Status + joueurs |
| `start_server(id)` | `startServer` | Démarrer serveur |
| `stop_server(id)` | `stopServer` | Arrêter serveur |
| `restart_server(id)` | `restartServer` | Redémarrer serveur |
| `start_server_backup(id)` | `startServerBackup` | Lancer backup |
| `get_server_backup_status(id)` | `getServerBackupStatus` | Status backup |
| `get_server(id)` | `getServer` | Détails serveur (IP, port) |
| `list_servers()` | `listServers` | Liste tous les serveurs |

**Parsing URL intelligent :** Accepte `192.168.8.8`, `http://ip`, `http://ip/multicraft` → complète en `http(s)://ip/multicraft/api.php`

**Résolution IP/Port :** Cascade `ip` → `daemon_ip` → `daemonIp` → `server_ip` → host API. Si 0.0.0.0, fallback sur l'IP de l'URL API. Port par défaut : 25565.

## Config Flow (config_flow.py)

- **Étape 1 (`async_step_user`)** : URL API, username, api_key, ftp_password (optionnel)
- **Étape 2 (`async_step_servers`)** : Multi-sélection des serveurs accessibles
- **Options Flow** : Modifier serveurs, scan_interval (10-300s slider), ftp_password
- **Erreurs** : `cannot_connect`, `invalid_auth`, `no_servers`, `no_server_selected`

## Données stockées dans hass.data

```python
hass.data[DOMAIN][entry.entry_id] = {
    "api": MulticraftAPI,
    "coordinator": DataUpdateCoordinator,
    "server_ids": ["1", "4"],
    "servers_info": {"1": "Nom Serveur A", "4": "Nom Serveur B"},
    "backup_active": set(),  # server_ids avec backup en cours
}
```

## Guide : ajouter une nouvelle entité

1. Créer `custom_components/multicraft/{platform}.py`
2. Classe héritant de `CoordinatorEntity` + `{Platform}Entity`
3. Accéder aux données via `self.coordinator.data[self._server_id]`
4. Ajouter `device_info` avec identifiant `(DOMAIN, f"{self._entry_id}_{self._server_id}")`
5. Ajouter la plateforme dans `PLATFORMS` de `__init__.py`
6. Si besoin d'une nouvelle donnée API : ajouter l'appel dans `async_update_data()`

## Guide : ajouter une méthode API

1. Ajouter la méthode async dans `api.py` → appeler `self._call_api("nomMethodeMulticraft", {"param": val})`
2. L'authentification HMAC est gérée automatiquement par `_call_api`
3. Retour : `{"success": bool, "errors": [], "data": {...}}`

## Guide : ajouter/modifier une traduction

Mettre à jour les deux fichiers `translations/en.json` et `translations/fr.json` en parallèle.
Structure : `config.step.{step}.data.{field}`, `config.error.{code}`, `options.step.init.data.{field}`

## Guide : migration de config

Si la structure de `config_entry.data` change :
1. Incrémenter `VERSION` dans `config_flow.py`
2. Mettre à jour `async_migrate_entry()` dans `__init__.py`
3. Ajouter la valeur par défaut pour le nouveau champ

## Ping Minecraft

Implémenté dans `__init__.py` (pas dans api.py). Utilise le protocole Minecraft natif :
- Handshake avec encodage VarInt → Status request → Parse JSON response
- Récupère version et mesure latency round-trip
- Appelé uniquement si le serveur est `online`
- Fallback gracieux : retourne `None` pour latency/version en cas d'erreur

## Release Process

Quand l'utilisateur demande une nouvelle release :

1. **Mettre à jour la version** dans `custom_components/multicraft/manifest.json`

2. **Mettre à jour le CHANGELOG.md** avec les changements de la nouvelle version (format bilingue EN/FR)

3. **Créer le commit** :
   ```bash
   git add .
   git commit -m "Release vX.Y.Z - Description"
   ```

4. **Créer et pousser le tag** :
   ```bash
   git tag -a vX.Y.Z -m "Release vX.Y.Z"
   git push origin main
   git push origin vX.Y.Z
   ```

5. **La release GitHub sera créée automatiquement** par le workflow `.github/workflows/release.yml`

**Note :** Ne PAS créer manuellement la release avec `gh release create` - le workflow s'en charge automatiquement quand le tag est poussé.

## Workflows GitHub Actions

- `validate.yml` : Validation HACS + Hassfest sur chaque push/PR vers `main`
- `release.yml` : Création automatique de release sur tag `v*.*.*` (inclut validation HACS + Hassfest)
- `hassfest.yaml` / `hacs.yaml` : Validations planifiées quotidiennes

## PR HACS

La PR pour ajouter l'intégration au dépôt HACS default est : https://github.com/hacs/default/pull/5320

## Pièges courants

- **services.yaml** : Utiliser `device` selector (pas `target`), le champ s'appelle `device_id` côté code
- **IP 0.0.0.0** : Le serveur Multicraft peut retourner 0.0.0.0 → utiliser l'IP de l'URL API comme fallback
- **Backup polling** : Le service `download_backup` poll toutes les 5s avec timeout 10min
- **Options flow** : Utilise un cache `servers_info` pour éviter des appels API inutiles
- **Événements** : `multicraft_backup_completed` et `multicraft_backup_failed` sont fire depuis le service download_backup
