# Contributing Guide / Guide de contribution

Thank you for your interest in contributing to the Multicraft integration for Home Assistant!

Merci de votre intérêt pour contribuer à l'intégration Multicraft pour Home Assistant !

---

## How to contribute / Comment contribuer

### Report a bug / Signaler un bug

**EN:**
1. Check that an open issue doesn't already exist
2. Create a new issue with the bug report template
3. Provide as much information as possible (logs, version, steps to reproduce)

**FR:**
1. Vérifier qu'il n'existe pas déjà une issue ouverte
2. Créer une nouvelle issue avec le template de rapport de bug
3. Fournir autant d'informations que possible (logs, version, étapes pour reproduire)

### Propose a feature / Proposer une fonctionnalité

**EN:**
1. Check that it hasn't already been proposed
2. Create an issue with the feature request template
3. Clearly describe the use case and benefits

**FR:**
1. Vérifier qu'elle n'a pas déjà été proposée
2. Créer une issue avec le template de demande de fonctionnalité
3. Décrire clairement le cas d'usage et les bénéfices

### Contribute code / Contribuer au code

1. Fork the project / Fork le projet
2. Create a branch for your feature / Créer une branche pour votre fonctionnalité
   ```bash
   git checkout -b feature/AmazingFeature
   ```
3. Commit your changes / Commiter vos changements
   ```bash
   git commit -m 'Add some AmazingFeature'
   ```
4. Push to the branch / Push vers la branche
   ```bash
   git push origin feature/AmazingFeature
   ```
5. Open a Pull Request / Ouvrir une Pull Request

---

## Code standards / Standards de code

- Follow PEP 8 conventions for Python / Suivre les conventions PEP 8 pour Python
- Add docstrings for functions and classes / Ajouter des docstrings pour les fonctions et classes
- Test your changes before submitting a PR / Tester vos changements avant de soumettre une PR
- Update documentation if necessary / Mettre à jour la documentation si nécessaire

---

## Project structure / Structure du projet

```
multicraft/
├── __init__.py          # Integration initialization / Initialisation de l'intégration
├── api.py               # Multicraft API client / Client API Multicraft
├── config_flow.py       # UI configuration / Configuration via UI
├── const.py             # Constants / Constantes
├── sensor.py            # Sensor entities / Entités capteurs
├── switch.py            # Switch entity / Entité switch
├── manifest.json        # Metadata / Métadonnées
└── translations/        # Translations / Traductions
    ├── en.json
    └── fr.json
```

---

## Tests

**EN:** Before submitting a PR, make sure that:
- The code works correctly
- Translations are up to date
- manifest.json is valid
- No linting errors

**FR:** Avant de soumettre une PR, assurez-vous que :
- Le code fonctionne correctement
- Les traductions sont à jour
- Le manifest.json est valide
- Aucune erreur de linting

---

## Questions?

Feel free to open an issue for any questions!

N'hésitez pas à ouvrir une issue pour toute question !
