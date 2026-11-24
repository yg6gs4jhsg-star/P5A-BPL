# Maquettes de BluePrintLab (écrans de référence pour la mise en page)

Ces images viennent des maquettes du groupe G04 (fichier `BluePrintLab_parcours_maquettes_v2.pptx`, 51 diapositives). Chaque image est un écran. **Elles servent de référence pour l'aspect** (couleurs, bandeau, menu, cartes, boutons, placement des blocs).

## Règle d'or
**Le cahier des charges (CDC), la matrice des droits et le code actuel font foi pour le contenu et le comportement.** Les maquettes sont plus anciennes : quand elles disent autre chose, on garde le CDC et on reprend seulement l'aspect. Les écarts connus sont listés plus bas.

## Charte visuelle (lisible sur les images)
- Rouge `#DF231D`, violet `#470A68`, noir ; secondaires orange `#FF611B`, rose `#F7429F`, violet clair `#7A37E4`. Police Montserrat.
- Fond de page gris très clair, blocs blancs aux coins arrondis, bordure fine.
- Bandeau d'en-tête (accueil et liste) : dégradé violet → rouge → rose, titre blanc, logo EPF à droite.
- Menu horizontal sous le bandeau, onglet actif souligné en rouge ; icône de profil ronde noire à droite.
- Étiquettes de thème en pastilles colorées ; statuts en pastilles pâles (Brouillon, En relecture, Publié, Réédition demandée) ; rôle en pastille (Owner, Collaborateur).
- Boutons principaux violets, boutons secondaires blancs avec bordure.

## Les écrans

### Visiteur

- **`01-visiteur-accueil.jpg`** : Accueil
  - Action : Arrive directement sur le site, sans compte. Peut ouvrir un projet, la liste ou les informations générales.
  - Ce qui se passe : Un projet à la une (le plus récent) et les projets phares choisis par l'encadrant. L'icône profil mène à la connexion.
- **`02-visiteur-liste-des-projets.jpg`** : Liste des projets
  - Action : Choisit un thème, recherche un projet, ouvre une carte.
  - Ce qui se passe : Tous les projets publiés. Les thèmes ne sont proposés que sur cette page.
- **`03-visiteur-informations-generales.jpg`** : Informations générales
  - Action : Lit comment fonctionne la plateforme.
  - Ce qui se passe : Présentation, les 4 étapes pour présenter un projet, qui peut faire quoi, contact. Aucune action.
- **`04-visiteur-page-du-projet.jpg`** : Page du projet
  - Action : Lit les onglets (résumé, problème et solutions, documents, photos et vidéos). Copie le lien ou partage sur LinkedIn.
  - Ce qui se passe : Aucun bouton de modification. Des projets similaires en bas de page.
### Étudiant owner

- **`05-etudiant-owner-connexion.jpg`** : Connexion
  - Action : Clique sur « Se connecter avec Microsoft (EPF) ».
  - Ce qui se passe : Il doit s'identifier avant d'accéder à son espace.
- **`06-etudiant-owner-mon-espace-premiere-connexion.jpg`** : Mon espace, première connexion
  - Action : Découvre son espace. Il peut créer son premier projet.
  - Ce qui se passe : Aucun projet pour l'instant, et des projets à découvrir.
- **`07-etudiant-owner-editeur-je-redige-mon-projet.jpg`** : Éditeur : je rédige mon projet
  - Action : Rédige : titre, thème, texte en Markdown, fichiers. Invite son équipe. Enregistre, puis soumet à l'encadrant.
  - Ce qui se passe : L'encadrant du projet est affiché (défini en amont). Tous les membres de l'équipe peuvent modifier le brouillon.
- **`08-etudiant-owner-mon-espace-projet-soumis.jpg`** : Mon espace : projet soumis
  - Action : A soumis son projet.
  - Ce qui se passe : Le projet apparaît avec le statut « En relecture » : l'encadrant le relit.
- **`09-etudiant-owner-page-de-mon-projet-en-relecture.jpg`** : Page de mon projet en relecture
  - Action : Ouvre la page de son projet.
  - Ce qui se passe : Un bandeau indique qu'il est en relecture, en attente de l'encadrant.
- **`10-etudiant-owner-l-encadrant-demande-des-modifications.jpg`** : L'encadrant demande des modifications
  - Action : Clique sur « Reprendre l'édition ».
  - Ce qui se passe : Un bloc « À faire » apparaît. Retour à l'éditeur (étape 5), puis nouvelle soumission.
- **`11-etudiant-owner-projet-valide-et-publie.jpg`** : Projet validé et publié
  - Action : L'encadrant a validé le projet.
  - Ce qui se passe : Le projet est publié et rangé dans « Mes projets validés », avec le bouton « Demander une réédition ».
- **`12-etudiant-owner-page-de-mon-projet-publie.jpg`** : Page de mon projet publié
  - Action : Ouvre la page publique de son projet.
  - Ce qui se passe : Le projet est visible de tous. L'édition est verrouillée : un bandeau propose « Demander une réédition ».
- **`13-etudiant-owner-editeur-projet-publie-verrouille.jpg`** : Éditeur : projet publié, verrouillé
  - Action : Ouvre l'éditeur du projet publié.
  - Ce qui se passe : Les champs sont grisés. Seule action : « Demander une réédition », acceptée par l'encadrant.
- **`14-etudiant-owner-reedition-demandee-en-attente.jpg`** : Réédition demandée, en attente
  - Action : A demandé une réédition.
  - Ce qui se passe : Statut « Réédition demandée » : en attente de l'accord de l'encadrant.
- **`15-etudiant-owner-reedition-acceptee.jpg`** : Réédition acceptée
  - Action : L'encadrant a accepté. Clique sur « Rouvrir l'édition ».
  - Ce qui se passe : Retour à l'éditeur (étape 5), puis nouvelle relecture.
- **`16-etudiant-owner-mon-espace-toutes-les-situations.jpg`** : Mon espace : toutes les situations
  - Action : Consulte tout son espace.
  - Ce qui se passe : À faire, projets en cours (owner ou collabo), projets validés, projets à découvrir.
- **`17-etudiant-owner-mon-espace-toutes-les-situations-suite-de-la-pag.jpg`** : Mon espace : toutes les situations (suite de la page)
  - Action : Consulte tout son espace.
  - Ce qui se passe : À faire, projets en cours (owner ou collabo), projets validés, projets à découvrir.
### Encadrant

- **`18-encadrant-relecture.jpg`** : Relecture
  - Action : À relire : valider ou demander des modifs. Réédition : accepter ou refuser. Publiés : mettre en avant ou retirer du site.
  - Ce qui se passe : Seulement les projets dont il est l'encadrant, avec 4 compteurs.
- **`19-encadrant-relecture-suite-de-la-page.jpg`** : Relecture (suite de la page)
  - Action : À relire : valider ou demander des modifs. Réédition : accepter ou refuser. Publiés : mettre en avant ou retirer du site.
  - Ce qui se passe : Seulement les projets dont il est l'encadrant, avec 4 compteurs.
- **`20-encadrant-page-du-projet-en-relecture.jpg`** : Page du projet en relecture
  - Action : Lit le projet, puis clique sur « Valider et publier » ou « Demander une modification ».
  - Ce qui se passe : Une barre d'actions propre à l'encadrant en haut de la page.
- **`21-encadrant-page-du-projet-publie.jpg`** : Page du projet publié
  - Action : « Modifier » (à tout moment), « Retirer du site » ou « Mettre en avant ».
  - Ce qui se passe : Un projet mis en avant devient un projet phare de l'accueil.
### Admin global

- **`22-admin-global-tous-les-projets.jpg`** : Tous les projets
  - Action : Filtre par statut ou par encadrant. Modifie, retire du site ou met en avant.
  - Ce qui se passe : Tous les projets, pour intervenir en cas de problème.
- **`23-admin-global-administration.jpg`** : Administration
  - Action : Gère la liste blanche (encadrants et clients), attribue les encadrants, règle la configuration (poids des fichiers, types, mode développement).
  - Ce qui se passe : Page réservée à l'admin global, qui attribue aussi les encadrants aux projets.
- **`24-admin-global-administration-suite-de-la-page.jpg`** : Administration (suite de la page)
  - Action : Gère la liste blanche (encadrants et clients), attribue les encadrants, règle la configuration (poids des fichiers, types, mode développement).
  - Ce qui se passe : Page réservée à l'admin global, qui attribue aussi les encadrants aux projets.
### Client

- **`25-client-page-du-projet-lecture-et-commentaires.png`** : Page du projet : lecture et commentaires
  - Action : Lit le projet, quel que soit son statut, et laisse un commentaire.
  - Ce qui se passe : Le commentaire est visible par l'équipe et par l'encadrant. Aucun bouton pour modifier, soumettre ou publier.

## Écarts entre les maquettes et le CDC / le code (le CDC gagne)

| Sur les maquettes | Dans le CDC et le code | Quoi faire |
|---|---|---|
| Page projet à 4 onglets (Résumé, Problème + Solutions, Documents techniques, Photos & Vidéos), galerie, « projets similaires » | Deux niveaux : présentation rapide, puis page détaillée (adresse `/detail`) ; liste des fichiers ; pas de projets similaires | Garder la mise en page (titre, pastilles, équipe, colonne de droite, cartes de fichiers) avec le contenu du CDC |
| « Catégories » | « Thèmes » | Écrire « Thèmes » |
| « Collabo » | « Collaborateur » partout | Écrire « Collaborateur » |
| « Dépublier » | « Retirer du site public » | Écrire « Retirer du site public » |
| « Soumettre à l'encadrant » | « Soumettre à la relecture » | Garder les mots du code |
| Administration : « liste blanche (encadrants et clients) » | Liste blanche des **admins** seulement ; les rôles viennent du compte Microsoft | Ne pas reprendre cette formulation |
| Éditeur : onglets et boutons B / I / H1 / lien | Deux zones de texte avec aperçu à droite ; boutons Titre, Gras, Liste, Image | Garder le code ; reprendre la mise en page des cartes (titre + thème, éditeur, colonne équipe et fichiers) |
| Cartes avec photo et « N médias » | Cartes sans photo (titre, client, extrait) | À décider |
| Pagination 1, 2, 3 sous la liste | Pas de pagination | À décider |
| Bandeau « Portail » + logo EPF | Pas de bandeau ni de logo | Il faut le fichier du logo EPF (fourni par Perrine) |
| Page « Informations générales » riche (4 étapes, qui peut faire quoi, contact) | Texte court | À décider (contenu à écrire) |
| « Projets à découvrir » dans Mon espace | Pas dans le CDC | À décider |
| Menu : « Portail d'Accueil », « Liste des projets », « Informations générales » | « Projets », « Informations », « Mon espace » | À décider |

Les écrans de l'encadrant (4 compteurs), de l'admin (tous les projets, administration) et du client (commentaires) correspondent aux étapes 9 et suivantes : ne pas les coder avant.
