"""
Module de gestion du système de fichiers.
Calcul de tailles, listing de dossiers, exclusions.
"""

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


def est_chemin_exclu(chemin: str, chemins_exclus: list[str]) -> bool:
    """
    Vérifie si un chemin doit être exclu du scan.
    Retourne True si le chemin commence par l'un des chemins exclus.
    La comparaison est insensible à la casse (Windows).
    """
    chemin_normalise = os.path.normcase(os.path.normpath(chemin))
    for chemin_exclu in chemins_exclus:
        exclu_normalise = os.path.normcase(os.path.normpath(chemin_exclu))
        if chemin_normalise == exclu_normalise or chemin_normalise.startswith(
            exclu_normalise + os.sep
        ):
            return True
    return False


def lister_tous_les_dossier(
    chemin_racine: str, chemins_exclus: list[str] | None = None
) -> list[str]:
    """
    Liste tous les dossiers à partir d'un chemin racine.
    Si chemins_exclus est fourni, les dossiers correspondants et leurs
    sous-dossiers sont ignorés.
    """
    liste_des_dossiers = [chemin_racine]
    for dossier, sous_dossiers, fichiers in os.walk(chemin_racine, followlinks=False):
        if chemins_exclus:
            # Filtre en place pour empêcher os.walk de descendre dans les dossiers exclus
            sous_dossiers[:] = [
                sd
                for sd in sous_dossiers
                if not est_chemin_exclu(os.path.join(dossier, sd), chemins_exclus)
            ]
        for sous_dossier in sous_dossiers:
            # Ajoute le chemin complet du sous-dossier à la liste
            liste_des_dossiers.append(os.path.join(dossier, sous_dossier))
    return liste_des_dossiers


def scanner_arborescence(
    chemin_racine: str, chemins_exclus: list[str] | None = None
) -> dict[str, int]:
    """
    Parcourt l'arborescence en un seul pass (bottom-up) et retourne un dictionnaire
    {chemin_dossier: taille_en_octets} incluant les sous-dossiers.
    """
    tailles: dict[str, int] = {}

    for dossier, sous_dossiers, fichiers in os.walk(
        chemin_racine, topdown=False, followlinks=False
    ):
        # Vérifie si le dossier est exclu
        if chemins_exclus and est_chemin_exclu(dossier, chemins_exclus):
            continue

        # Calcule la taille des fichiers directs du dossier
        taille_fichiers = 0
        for fichier in fichiers:
            try:
                taille_fichiers += os.path.getsize(os.path.join(dossier, fichier))
            except (OSError, PermissionError):
                pass

        # Ajoute la taille des sous-dossiers (déjà calculés car topdown=False)
        taille_sous_dossiers = sum(
            tailles.get(os.path.join(dossier, sd), 0) for sd in sous_dossiers
        )

        tailles[dossier] = taille_fichiers + taille_sous_dossiers

    return tailles


def filtrer_dossiers_redondants(dossiers: list[dict]) -> list[dict]:
    """
    Filtre les dossiers parents redondants dans la liste de notification.
    Un dossier est redondant s'il est un parent d'un autre dossier dans la liste.
    Seuls les dossiers les plus profonds (feuilles) sont conservés.
    """
    chemins = [os.path.normcase(os.path.normpath(d["chemin"])) for d in dossiers]
    resultat = []
    for i, dossier in enumerate(dossiers):
        chemin = chemins[i]
        # Vérifie si un autre dossier de la liste est un enfant de celui-ci
        est_parent = any(
            autre.startswith(chemin + os.sep)
            for j, autre in enumerate(chemins)
            if j != i
        )
        if not est_parent:
            resultat.append(dossier)
    return resultat
