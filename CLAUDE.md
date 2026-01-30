# Instructions pour Claude

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

- `validate.yml` : Validation HACS + Hassfest sur chaque push/PR
- `release.yml` : Création automatique de release sur tag `v*.*.*`

## PR HACS

La PR pour ajouter l'intégration au dépôt HACS default est : https://github.com/hacs/default/pull/5320
