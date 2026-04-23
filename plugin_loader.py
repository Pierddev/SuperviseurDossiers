"""
Module de chargement dynamique des plugins.
"""

import importlib.util
import logging
import os
import sys
import traceback

logger = logging.getLogger(__name__)

# Registre global des plugins : nom -> dict(module, actif, erreur, chemin)
_REGISTRE: dict[str, dict] = {}

# Dossier de l'application (initialisé au premier chargement)
_DOSSIER_APP: str = ""


def _dossier_plugins() -> str:
    """Retourne le chemin absolu du dossier plugins."""
    return os.path.join(_DOSSIER_APP, "plugins")


def _scan_fichiers_plugins() -> list[tuple[str, str]]:
    """
    Scanne le dossier plugins/ et retourne une liste de (nom_module, chemin_fichier)
    pour chaque fichier .py valide (non préfixé par '__').
    """
    dossier = _dossier_plugins()
    resultats: list[tuple[str, str]] = []
    if not os.path.exists(dossier):
        return resultats
    for nom_fichier in sorted(os.listdir(dossier)):
        if nom_fichier.endswith(".py") and not nom_fichier.startswith("__"):
            nom_module = nom_fichier[:-3]
            chemin = os.path.join(dossier, nom_fichier)
            resultats.append((nom_module, chemin))
    return resultats


def _charger_module(nom_module: str, chemin_fichier: str) -> dict:
    """
    Tente de charger un module plugin depuis son chemin.
    Retourne un dict décrivant son état :
        { module, actif, erreur, chemin }
    """
    try:
        spec = importlib.util.spec_from_file_location(nom_module, chemin_fichier)
        if not spec or not spec.loader:
            return {
                "module": None,
                "actif": False,
                "erreur": "Impossible de créer le spec du module.",
                "chemin": chemin_fichier,
            }

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Vérifie les fonctions requises
        fonctions_requises = ["configurer", "planifier", "afficher_statut"]
        manquantes = [f for f in fonctions_requises if not hasattr(module, f)]
        if manquantes:
            return {
                "module": None,
                "actif": False,
                "erreur": f"Fonctions manquantes : {', '.join(manquantes)}",
                "chemin": chemin_fichier,
            }

        # Initialise le plugin
        module.configurer(_DOSSIER_APP)
        logger.info(f"Plugin '{nom_module}' chargé avec succès.")
        return {
            "module": module,
            "actif": True,
            "erreur": None,
            "chemin": chemin_fichier,
        }

    except Exception:
        msg = traceback.format_exc()
        logger.error(f"Erreur lors du chargement du plugin '{nom_module}': {msg}")
        return {
            "module": None,
            "actif": False,
            "erreur": msg.strip(),
            "chemin": chemin_fichier,
        }


def reinitialiser_plugins_en_erreur() -> None:
    """
    Retire du registre les plugins en état d'erreur pour permettre un nouveau
    chargement lors du prochain appel de charger_plugins().
    Ne touche pas aux plugins actifs ni à ceux désactivés manuellement (sans erreur).
    """
    global _REGISTRE
    for nom in list(_REGISTRE.keys()):
        info = _REGISTRE[nom]
        if not info["actif"] and info.get("erreur"):
            del _REGISTRE[nom]
            logger.info(f"Plugin '{nom}' retiré du registre (en erreur) pour retry.")


def charger_plugins(dossier_app: str) -> list:
    """
    Scanne le dossier 'plugins/' et charge les modules Python qui y sont présents.
    Met à jour le registre global (_REGISTRE) avec l'état de chaque plugin.
    Retourne la liste des modules chargés avec succès (actifs).
    """
    global _DOSSIER_APP
    _DOSSIER_APP = dossier_app

    dossier = _dossier_plugins()

    # Crée le dossier plugins s'il n'existe pas
    if not os.path.exists(dossier):
        os.makedirs(dossier)
        return []

    # Ajoute le dossier plugins au sys.path
    if dossier not in sys.path:
        sys.path.insert(0, dossier)

    for nom_module, chemin in _scan_fichiers_plugins():
        deja_present = nom_module in _REGISTRE
        en_erreur = (
            deja_present
            and not _REGISTRE[nom_module]["actif"]
            and _REGISTRE[nom_module].get("erreur")
        )

        if not deja_present or en_erreur:
            if en_erreur and nom_module in sys.modules:
                del sys.modules[nom_module]
            etat = _charger_module(nom_module, chemin)
            _REGISTRE[nom_module] = etat

    return [
        info["module"]
        for info in _REGISTRE.values()
        if info["actif"] and info["module"]
    ]


def recharger_plugins() -> None:
    """
    Force le rechargement complet de tous les plugins depuis le disque.
    Découvre de nouveaux plugins et met à jour les existants.
    Préserve l'état actif/inactif choisi par l'utilisateur pour les plugins déjà connus.
    """
    global _REGISTRE

    if not _DOSSIER_APP:
        return

    dossier = _dossier_plugins()
    if not os.path.exists(dossier):
        return

    # Supprime les modules du sys.modules pour forcer la relecture
    for nom in list(sys.modules.keys()):
        if nom in _REGISTRE:
            del sys.modules[nom]

    nouveaux = {}
    for nom_module, chemin in _scan_fichiers_plugins():
        ancien = _REGISTRE.get(nom_module)
        etat = _charger_module(nom_module, chemin)

        # Si l'utilisateur avait explicitement désactivé ce plugin, on respecte son choix
        if (
            ancien
            and not ancien.get("actif")
            and ancien.get("module") is None
            and not ancien.get("erreur")
        ):
            # Désactivé manuellement (pas en erreur)
            etat["actif"] = False

        nouveaux[nom_module] = etat

    _REGISTRE = nouveaux


def get_registre() -> dict[str, dict]:
    """
    Retourne une copie du registre global sous une forme sérialisable (sans les modules Python).
    Format : { nom: { actif, erreur, chemin } }
    """
    resultat = {}
    for nom, info in _REGISTRE.items():
        resultat[nom] = {
            "actif": info.get("actif", False),
            "erreur": info.get("erreur"),
            "chemin": info.get("chemin", ""),
            "valide": info.get("module") is not None
            or (not info.get("actif") and info.get("erreur") is None),
        }
    return resultat


def activer_plugin(nom: str) -> dict:
    """
    Tente d'activer un plugin par son nom.
    Recharge le module depuis le disque si nécessaire.
    Retourne { ok: bool, erreur: str|None }.
    """
    chemin = os.path.join(_dossier_plugins(), f"{nom}.py")
    if not os.path.exists(chemin):
        return {
            "ok": False,
            "erreur": f"Fichier '{nom}.py' introuvable dans le dossier plugins.",
        }

    # Supprime l'ancienne version du module si présente
    if nom in sys.modules:
        del sys.modules[nom]

    etat = _charger_module(nom, chemin)
    _REGISTRE[nom] = etat

    if etat["actif"]:
        return {"ok": True, "erreur": None}
    else:
        return {"ok": False, "erreur": etat.get("erreur", "Erreur inconnue.")}


def desactiver_plugin(nom: str) -> dict:
    """
    Désactive un plugin par son nom (le retire du registre actif sans supprimer le fichier).
    Retourne { ok: bool, erreur: str|None }.
    """
    if nom not in _REGISTRE:
        return {"ok": False, "erreur": f"Plugin '{nom}' non trouvé dans le registre."}

    # Marque comme inactif sans erreur (désactivation volontaire)
    _REGISTRE[nom]["actif"] = False
    _REGISTRE[nom]["module"] = None
    _REGISTRE[nom]["erreur"] = None  # pas d'erreur, c'est voulu

    # Retire du sys.modules
    if nom in sys.modules:
        del sys.modules[nom]

    return {"ok": True, "erreur": None}
