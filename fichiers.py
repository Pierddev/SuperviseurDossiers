"""
Module de gestion du système de fichiers.
Calcul de tailles, listing de dossiers, exclusions.
"""

import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

# Nombre de threads pour le calcul parallèle des tailles (configurable via .env)
NB_THREADS_SCAN = int(os.getenv("NB_THREADS_SCAN", "8"))


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


def _calculer_taille_fichiers_dossier(
    dossier: str, fichiers: list[str]
) -> tuple[str, int]:
    """
    Calcule la taille totale des fichiers directs d'un seul dossier.
    Utilisé comme unité de travail pour le ThreadPoolExecutor.
    """
    total = 0
    for fichier in fichiers:
        try:
            total += os.path.getsize(os.path.join(dossier, fichier))
        except (OSError, PermissionError):
            pass
    return dossier, total


def scanner_arborescence(
    chemin_racine: str, chemins_exclus: list[str] | None = None
) -> dict[str, int]:
    """
    Parcourt l'arborescence en 3 phases et retourne un dictionnaire
    {chemin_dossier: taille_en_octets} incluant les sous-dossiers.

    Optimisé pour les volumes Docker (latence I/O élevée par stat()) :
      Phase 1 — Collecte rapide de la structure (topdown=True, prune les exclusions)
      Phase 2 — Calcul parallèle des tailles fichiers (ThreadPoolExecutor)
      Phase 3 — Agrégation bottom-up des tailles (parents = somme enfants)
    """
    # ── Phase 1 : Collecter la structure de l'arborescence ──────────
    # topdown=True permet de couper (prune) les dossiers exclus AVANT
    # de descendre dedans, contrairement à topdown=False qui les parcourt
    # inutilement puis les ignore.
    structure: dict[str, tuple[list[str], list[str]]] = {}

    for dossier, sous_dossiers, fichiers in os.walk(
        chemin_racine, topdown=True, followlinks=False
    ):
        if chemins_exclus and est_chemin_exclu(dossier, chemins_exclus):
            sous_dossiers.clear()  # Empêche os.walk de descendre dans ce dossier
            continue

        # Filtre aussi les sous-dossiers exclus individuellement
        if chemins_exclus:
            sous_dossiers[:] = [
                sd
                for sd in sous_dossiers
                if not est_chemin_exclu(os.path.join(dossier, sd), chemins_exclus)
            ]

        structure[dossier] = (list(fichiers), list(sous_dossiers))

    logger.info(
        "Phase 1 terminée : %d dossiers collectés pour %s",
        len(structure),
        chemin_racine,
    )

    # ── Phase 2 : Calculer les tailles fichiers en parallèle ───────
    # Chaque thread calcule la taille des fichiers d'UN dossier.
    # Les appels stat() à travers les volumes Docker ont une latence élevée,
    # le multithreading permet de les exécuter simultanément.
    tailles_directes: dict[str, int] = {}

    with ThreadPoolExecutor(max_workers=NB_THREADS_SCAN) as executor:
        futures = {
            executor.submit(
                _calculer_taille_fichiers_dossier, dossier, fichiers
            ): dossier
            for dossier, (fichiers, _) in structure.items()
        }
        for future in as_completed(futures):
            dossier, taille = future.result()
            tailles_directes[dossier] = taille

    logger.info("Phase 2 terminée : tailles fichiers calculées en parallèle")

    # ── Phase 3 : Agréger bottom-up (dossiers les plus profonds d'abord) ──
    tailles: dict[str, int] = {}

    for dossier in sorted(
        structure.keys(), key=lambda d: d.count(os.sep), reverse=True
    ):
        _, sous_dossiers = structure[dossier]
        taille_sous_dossiers = sum(
            tailles.get(os.path.join(dossier, sd), 0) for sd in sous_dossiers
        )
        tailles[dossier] = tailles_directes.get(dossier, 0) + taille_sous_dossiers

    logger.info("Phase 3 terminée : agrégation bottom-up complète")

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
