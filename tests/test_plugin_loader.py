import os
import sys
import tempfile
import unittest
from unittest.mock import patch

# Ajoute le dossier racine au PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from plugin_loader import charger_plugins


class TestPluginLoader(unittest.TestCase):
    """Tests pour la fonction charger_plugins."""

    def test_dossier_inexistant(self):
        """Si le dossier plugins n'existe pas, il est créé et retourne une liste vide."""
        with tempfile.TemporaryDirectory() as tmpdir:
            faux_dossier = os.path.join(tmpdir, "nexiste_pas")
            resultat = charger_plugins(faux_dossier)
            self.assertEqual(resultat, [])
            # Vérifie que le sous-dossier plugins a bien été créé
            self.assertTrue(os.path.exists(os.path.join(faux_dossier, "plugins")))

    def test_dossier_vide(self):
        """Si le dossier plugins est vide, doit retourner une liste vide."""
        with tempfile.TemporaryDirectory() as tmpdir:
            resultat = charger_plugins(tmpdir)
            self.assertEqual(resultat, [])

    def test_ignore_fichiers_non_py(self):
        """Les fichiers qui ne finissent pas par .py doivent être ignorés."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "plugins"))
            with open(os.path.join(tmpdir, "plugins", "test.txt"), "w") as f:
                f.write("test")
            
            resultat = charger_plugins(tmpdir)
            self.assertEqual(resultat, [])

    def test_plugin_valide(self):
        """Un plugin valide doit être chargé et configuré."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "plugins"))
            # Crée un faux plugin valide
            contenu_plugin = 'def configurer(dossier):\n    pass\ndef planifier(scheduler):\n    pass\ndef afficher_statut():\n    pass'
            fichier_plugin = os.path.join(tmpdir, "plugins", "plugin_test.py")
            with open(fichier_plugin, "w") as f:
                f.write(contenu_plugin)
            
            resultat = charger_plugins(tmpdir)
            self.assertEqual(len(resultat), 1)
            self.assertTrue(hasattr(resultat[0], "configurer"))

    def test_plugin_invalide_methodes_manquantes(self):
        """Un plugin sans les méthodes requises ne doit pas être chargé."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "plugins"))
            # Plugin invalide (manque afficher_statut)
            contenu_plugin = 'def configurer(dossier):\n    pass\ndef planifier(scheduler):\n    pass'
            fichier_plugin = os.path.join(tmpdir, "plugins", "plugin_invalide.py")
            with open(fichier_plugin, "w") as f:
                f.write(contenu_plugin)
            
            resultat = charger_plugins(tmpdir)
            self.assertEqual(len(resultat), 0)

    @patch("plugin_loader.logger.error")
    def test_plugin_erreur_syntaxe(self, mock_logger):
        """Un plugin avec une erreur lors de l'import ne doit pas faire crasher l'app."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "plugins"))
            fichier_plugin = os.path.join(tmpdir, "plugins", "plugin_erreur.py")
            with open(fichier_plugin, "w") as f:
                f.write("ceci n'est pas du python valide !")
            
            resultat = charger_plugins(tmpdir)
            self.assertEqual(len(resultat), 0)
            mock_logger.assert_called()


if __name__ == "__main__":
    unittest.main()
