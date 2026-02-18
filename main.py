import os


def calculer_taille_dossier(chemin_dossier: str) -> int:
    """
    Calcule la taille totale d'un dossier en incluant tous les sous-dossiers et fichiers.
    """
    taille_totale = 0
    # os.walk() parcourt tous les dossiers et fichiers de manière itérative
    for dossier, sous_dossiers, fichiers in os.walk(chemin_dossier, followlinks=False):
        for fichier in fichiers:
            try:
                # Ajoute la taille du fichier à la taille totale
                taille_totale += os.path.getsize(os.path.join(dossier, fichier))
            except (OSError, PermissionError):
                # Ignore les erreurs d'accès
                pass
    return taille_totale


def lister_tous_les_dossier(chemin_racine: str) -> list[str]:
    """
    Liste tous les dossiers à partir d'un chemin racine.
    """
    liste_des_dossiers = [chemin_racine]
    for dossier, sous_dossiers, fichiers in os.walk(chemin_racine, followlinks=False):
        for sous_dossier in sous_dossiers:
            # Ajoute le chemin complet du sous-dossier à la liste
            liste_des_dossiers.append(os.path.join(dossier, sous_dossier))
    return liste_des_dossiers


liste_des_dossiers = lister_tous_les_dossier("D:\\Exemple\\")
print(liste_des_dossiers)
