import os
import sys
import tempfile
import unittest
from unittest.mock import patch
from unittest.mock import MagicMock

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
            contenu_plugin = "def configurer(dossier):\n    pass\ndef planifier(scheduler):\n    pass\ndef afficher_statut():\n    pass"
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
            contenu_plugin = "def configurer(dossier):\n    pass\ndef planifier(scheduler):\n    pass"
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


class TestRegistrePlugins(unittest.TestCase):
    """Tests pour la gestion du registre des plugins."""

    def setUp(self):
        import plugin_loader

        plugin_loader._REGISTRE.clear()
        plugin_loader._DOSSIER_APP = ""

    def test_get_registre_vide(self):
        from plugin_loader import get_registre

        self.assertEqual(get_registre(), {})

    def test_get_registre_avec_plugins(self):
        import plugin_loader
        from plugin_loader import get_registre

        plugin_loader._REGISTRE["mon_plugin"] = {
            "actif": True,
            "erreur": None,
            "chemin": "/chemin/plugin.py",
            "module": MagicMock(),
        }
        registre = get_registre()
        self.assertIn("mon_plugin", registre)
        self.assertTrue(registre["mon_plugin"]["actif"])
        self.assertTrue(registre["mon_plugin"]["valide"])

    def test_desactiver_plugin_existant(self):
        import plugin_loader
        from plugin_loader import desactiver_plugin

        plugin_loader._REGISTRE["mon_plugin"] = {
            "actif": True,
            "module": object(),
            "erreur": None,
        }
        res = desactiver_plugin("mon_plugin")
        self.assertTrue(res["ok"])
        self.assertFalse(plugin_loader._REGISTRE["mon_plugin"]["actif"])

    def test_desactiver_plugin_inexistant(self):
        from plugin_loader import desactiver_plugin

        res = desactiver_plugin("nexiste_pas")
        self.assertFalse(res["ok"])
        self.assertIn("non trouvé", res["erreur"])

    def test_reinitialiser_plugins_en_erreur(self):
        import plugin_loader
        from plugin_loader import reinitialiser_plugins_en_erreur

        plugin_loader._REGISTRE["p1"] = {"actif": True, "erreur": None}
        plugin_loader._REGISTRE["p2"] = {"actif": False, "erreur": "Crash!"}
        reinitialiser_plugins_en_erreur()
        self.assertIn("p1", plugin_loader._REGISTRE)
        self.assertNotIn("p2", plugin_loader._REGISTRE)

    @patch("os.path.exists")
    def test_activer_plugin_inexistant(self, mock_exists):
        from plugin_loader import activer_plugin

        mock_exists.return_value = False
        res = activer_plugin("nexiste_pas")
        self.assertFalse(res["ok"])
        self.assertIn("introuvable", res["erreur"])

    @patch("plugin_loader._charger_module")
    @patch("os.path.exists")
    def test_activer_plugin_valide(self, mock_exists, mock_charger):
        import plugin_loader
        from plugin_loader import activer_plugin

        mock_exists.return_value = True
        mock_charger.return_value = {
            "actif": True,
            "module": object(),
            "erreur": None,
            "chemin": "/test.py",
        }

        res = activer_plugin("mon_plugin")
        self.assertTrue(res["ok"])
        self.assertIn("mon_plugin", plugin_loader._REGISTRE)
        self.assertTrue(plugin_loader._REGISTRE["mon_plugin"]["actif"])

    @patch("plugin_loader._scan_fichiers_plugins")
    @patch("os.path.exists")
    def test_recharger_plugins(self, mock_exists, mock_scan):
        import plugin_loader
        from plugin_loader import recharger_plugins

        plugin_loader._DOSSIER_APP = "/app"
        mock_exists.return_value = True
        # On simule un plugin trouvé sur le disque
        mock_scan.return_value = [("nouveau_plugin", "/chemin/nouveau_plugin.py")]

        # On mock _charger_module
        with patch("plugin_loader._charger_module") as mock_charger:
            mock_charger.return_value = {
                "actif": True,
                "module": object(),
                "erreur": None,
                "chemin": "/chemin/nouveau_plugin.py",
            }
            recharger_plugins()

            self.assertIn("nouveau_plugin", plugin_loader._REGISTRE)
            self.assertTrue(plugin_loader._REGISTRE["nouveau_plugin"]["actif"])


if __name__ == "__main__":
    unittest.main()
