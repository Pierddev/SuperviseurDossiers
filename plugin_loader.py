"""
Module de chargement dynamique des plugins.
"""

import importlib.util
import logging
import os
import sys

logger = logging.getLogger(__name__)


def charger_plugins(dossier_app: str) -> list:
    """
    Scanne le dossier 'plugins/' et charge les modules Python qui y sont présents.
    Un plugin valide doit exposer les fonctions 'configurer', 'planifier' et 'afficher_statut'.
    Retourne la liste des plugins chargés avec succès.
    """
    dossier_plugins = os.path.join(dossier_app, "plugins")
    plugins_charges = []

    # Crée le dossier plugins s'il n'existe pas
    if not os.path.exists(dossier_plugins):
        os.makedirs(dossier_plugins)
        return plugins_charges

    # Ajoute le dossier plugins au sys.path pour permettre les imports relatifs dans les plugins
    if dossier_plugins not in sys.path:
        sys.path.insert(0, dossier_plugins)

    for nom_fichier in os.listdir(dossier_plugins):
        if nom_fichier.endswith(".py") and not nom_fichier.startswith("__"):
            nom_module = nom_fichier[:-3]
            chemin_fichier = os.path.join(dossier_plugins, nom_fichier)

            try:
                # Chargement dynamique du module
                spec = importlib.util.spec_from_file_location(nom_module, chemin_fichier)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                    # Vérifie que le plugin expose les fonctions requises
                    if (
                        hasattr(module, "configurer")
                        and hasattr(module, "planifier")
                        and hasattr(module, "afficher_statut")
                    ):
                        try:
                            # Initialise le plugin
                            module.configurer(dossier_app)
                            plugins_charges.append(module)
                            logger.info(f"Plugin '{nom_module}' chargé avec succès.")
                        except Exception as e:
                            logger.error(
                                f"Erreur lors de la configuration du plugin '{nom_module}': {e}"
                            )
                            print(
                                f"⚠️ Erreur lors de la configuration du plugin '{nom_module}': {e}"
                            )
                    else:
                        logger.warning(
                            f"Le fichier '{nom_fichier}' dans 'plugins/' n'est pas un plugin valide (fonctions manquantes)."
                        )
            except Exception as e:
                logger.error(f"Erreur lors du chargement du fichier '{nom_fichier}': {e}")
                print(f"⚠️ Erreur lors du chargement du plugin '{nom_fichier}': {e}")

    return plugins_charges
