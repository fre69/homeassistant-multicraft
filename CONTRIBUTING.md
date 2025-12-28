# Guide de contribution

Merci de votre intérêt pour contribuer à l'intégration Multicraft pour Home Assistant !

## Comment contribuer

### Signaler un bug

Si vous trouvez un bug, veuillez :
1. Vérifier qu'il n'existe pas déjà une issue ouverte
2. Créer une nouvelle issue avec le template de rapport de bug
3. Fournir autant d'informations que possible (logs, version, étapes pour reproduire)

### Proposer une fonctionnalité

1. Vérifier qu'elle n'a pas déjà été proposée
2. Créer une issue avec le template de demande de fonctionnalité
3. Décrire clairement le cas d'usage et les bénéfices

### Contribuer au code

1. Fork le projet
2. Créer une branche pour votre fonctionnalité (`git checkout -b feature/AmazingFeature`)
3. Commiter vos changements (`git commit -m 'Add some AmazingFeature'`)
4. Push vers la branche (`git push origin feature/AmazingFeature`)
5. Ouvrir une Pull Request

## Standards de code

- Suivre les conventions PEP 8 pour Python
- Ajouter des docstrings pour les fonctions et classes
- Tester vos changements avant de soumettre une PR
- Mettre à jour la documentation si nécessaire

## Structure du projet

```
multicraft/
├── __init__.py          # Initialisation de l'intégration
├── api.py               # Client API Multicraft
├── config_flow.py       # Configuration via UI
├── const.py             # Constantes
├── sensor.py            # Entités capteurs
├── switch.py            # Entité switch
├── manifest.json        # Métadonnées
└── translations/        # Traductions
    ├── en.json
    └── fr.json
```

## Tests

Avant de soumettre une PR, assurez-vous que :
- Le code fonctionne correctement
- Les traductions sont à jour
- Le manifest.json est valide
- Aucune erreur de linting

## Questions ?

N'hésitez pas à ouvrir une issue pour toute question !

