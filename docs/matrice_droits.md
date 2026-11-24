# Matrice des droits (copie du § 2.2 du cahier des charges V3.1)

Ce fichier sert à lire la matrice sans ouvrir le .docx. Le cahier des charges reste la référence.

## Qui est qui
- **Visiteur** : personne non connectée.
- **Client, Collaborateur, Owner** : rôle de la personne dans CE projet (table Member).
- **Encadrant** : l'encadrant attribué à CE projet (`Project.supervisor`), pas n'importe quel encadrant.
- **Admin** : adresse dans la liste blanche (`is_admin`). Il s'ajoute au rôle de base.

## Matrice
✓ = autorisé · – = non autorisé

| Action | Visiteur | Client | Collaborateur | Owner | Encadrant | Admin |
|---|---|---|---|---|---|---|
| Consulter les projets publiés et la page d'infos | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Partager un projet (LinkedIn, copie du lien) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Lire un projet non publié de son équipe | – | ✓ | ✓ | ✓ | ✓ | ✓ |
| Créer un projet (tout étudiant connecté) | – | – | – | ✓ | – | – |
| Inviter ou retirer des membres | – | – | – | ✓ | – | ✓ |
| Modifier le brouillon | – | – | ✓ | ✓ | ✓ | ✓ |
| Soumettre à la relecture | – | – | – | ✓ | – | – |
| Demander des modifications | – | – | – | – | ✓ | ✓ |
| Valider et publier, retirer du site public | – | – | – | – | ✓ | ✓ |
| Demander une réédition | – | – | – | ✓ | – | – |
| Accepter ou refuser une réédition | – | – | – | – | ✓ | ✓ |
| Choisir les projets phares de l'accueil | – | – | – | – | ✓ | ✓ |
| Laisser un commentaire | – | ✓ | – | – | – | – |
| Lire les commentaires | – | ✓ | ✓ | ✓ | ✓ | ✓ |
| Supprimer un projet | – | – | – | ✓ si jamais publié | – | ✓ |
| Transférer le rôle d'Owner | – | – | – | ✓ | – | ✓ |
| Liste blanche des admins, thèmes, réglages, attribution des encadrants | – | – | – | – | – | ✓ |

## Remarques
- « Créer un projet » : la colonne Owner veut dire « un étudiant connecté » (celui qui crée devient Owner). Un encadrant ne crée pas de projet.
- Les actions sur un projet dépendent aussi du statut (ex. brouillon verrouillé après publication) : voir § 3 du cahier des charges.
