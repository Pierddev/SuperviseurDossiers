"""
Tests pour la fonction principale scanner.
Vérifie l'orchestration complète du processus de scan.
NB: Ces tests ont été réalisés avec l'aide de l'Intelligence Artificielle.
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scanner import scanner


class TestScanner(unittest.TestCase):
    """Tests pour la fonction scanner (orchestration)."""

    @patch.dict(os.environ, {"CHEMINS_RACINES": "C:\\test", "CHEMINS_EXCLUS": ""})
    @patch("scanner.deconnecter_base_de_donnees")
    @patch("scanner.envoyer_notif_teams")
    @patch("scanner.terminer_scan")
    @patch("scanner.traiter_dossiers_en_lot")
    @patch("scanner.scanner_arborescence")
    @patch("scanner.creer_scan")
    @patch("scanner.connecter_base_de_donnees")
    def test_sequence_complete(
        self,
        mock_connect,
        mock_creer,
        mock_scanner_arbo,
        mock_traiter,
        mock_terminer,
        mock_notif,
        mock_deconnect,
    ):
        """Le scanner doit suivre la séquence : connecter → créer scan → scanner_arborescence → traiter_en_lot → terminer → notifier → déconnecter."""
        mock_connect.return_value = MagicMock()
        mock_creer.return_value = 1
        mock_scanner_arbo.return_value = {"C:\\test": 0}
        mock_traiter.return_value = ([], [], 0, 0)

        scanner()

        mock_connect.assert_called_once()
        mock_creer.assert_called_once()
        mock_scanner_arbo.assert_called_once()
        mock_traiter.assert_called_once()
        mock_terminer.assert_called_once()
        mock_notif.assert_called_once()
        mock_deconnect.assert_called_once()

    @patch.dict(os.environ, {"CHEMINS_RACINES": "C:\\test", "CHEMINS_EXCLUS": ""})
    @patch("scanner.deconnecter_base_de_donnees")
    @patch("scanner.envoyer_notif_teams")
    @patch("scanner.terminer_scan")
    @patch("scanner.traiter_dossiers_en_lot")
    @patch("scanner.scanner_arborescence")
    @patch("scanner.creer_scan")
    @patch("scanner.connecter_base_de_donnees")
    def test_scan_termine_avec_statut_termine(
        self,
        mock_connect,
        mock_creer,
        mock_scanner_arbo,
        mock_traiter,
        mock_terminer,
        mock_notif,
        mock_deconnect,
    ):
        """Le scan doit être terminé avec le statut 'completed'."""
        mock_connect.return_value = MagicMock()
        mock_creer.return_value = 1
        mock_scanner_arbo.return_value = {}
        mock_traiter.return_value = ([], [], 0, 0)

        scanner()

        args = mock_terminer.call_args[0]
        self.assertEqual(args[1], 1)  # id_scan
        self.assertEqual(args[2], "completed")  # statut

    @patch.dict(os.environ, {"CHEMINS_RACINES": "C:\\test", "CHEMINS_EXCLUS": ""})
    @patch("scanner.deconnecter_base_de_donnees")
    @patch("scanner.envoyer_notif_teams")
    @patch("scanner.terminer_scan")
    @patch("scanner.traiter_dossiers_en_lot")
    @patch("scanner.scanner_arborescence")
    @patch("scanner.creer_scan")
    @patch("scanner.connecter_base_de_donnees")
    def test_message_contient_nouveaux_dossiers(
        self,
        mock_connect,
        mock_creer,
        mock_scanner_arbo,
        mock_traiter,
        mock_terminer,
        mock_notif,
        mock_deconnect,
    ):
        """Le message Teams doit mentionner les nouveaux dossiers."""
        mock_connect.return_value = MagicMock()
        mock_creer.return_value = 1
        mock_scanner_arbo.return_value = {"C:\\nouveau": 200 * 1024 * 1024}
        mock_traiter.return_value = (
            [{"type": "nouveau", "chemin": "C:\\nouveau", "taille": 200}],
            [],
            200,
            200,
        )

        scanner()

        message = mock_notif.call_args[0][0]
        self.assertIn("Nouveaux dossiers", message)
        self.assertIn("C: > nouveau", message)

    @patch.dict(os.environ, {"CHEMINS_RACINES": "C:\\test", "CHEMINS_EXCLUS": ""})
    @patch("scanner.deconnecter_base_de_donnees")
    @patch("scanner.envoyer_notif_teams")
    @patch("scanner.terminer_scan")
    @patch("scanner.traiter_dossiers_en_lot")
    @patch("scanner.scanner_arborescence")
    @patch("scanner.creer_scan")
    @patch("scanner.connecter_base_de_donnees")
    def test_message_contient_dossiers_modifies(
        self,
        mock_connect,
        mock_creer,
        mock_scanner_arbo,
        mock_traiter,
        mock_terminer,
        mock_notif,
        mock_deconnect,
    ):
        """Le message Teams doit mentionner les dossiers modifiés."""
        mock_connect.return_value = MagicMock()
        mock_creer.return_value = 1
        mock_scanner_arbo.return_value = {"C:\\modifie": 0}
        mock_traiter.return_value = (
            [],
            [{"type": "modification", "chemin": "C:\\modifie", "difference": 150}],
            0,
            150,
        )

        scanner()

        message = mock_notif.call_args[0][0]
        self.assertIn("Dossiers modifiés", message)
        self.assertIn("C: > modifie", message)
        self.assertIn("+    150", message)

    @patch.dict(os.environ, {"CHEMINS_RACINES": "C:\\test", "CHEMINS_EXCLUS": ""})
    @patch("scanner.deconnecter_base_de_donnees")
    @patch("scanner.envoyer_notif_teams")
    @patch("scanner.terminer_scan")
    @patch("scanner.traiter_dossiers_en_lot")
    @patch("scanner.scanner_arborescence")
    @patch("scanner.creer_scan")
    @patch("scanner.connecter_base_de_donnees")
    def test_message_sans_modification(
        self,
        mock_connect,
        mock_creer,
        mock_scanner_arbo,
        mock_traiter,
        mock_terminer,
        mock_notif,
        mock_deconnect,
    ):
        """Le message doit indiquer qu'aucun dossier n'a été modifié."""
        mock_connect.return_value = MagicMock()
        mock_creer.return_value = 1
        mock_scanner_arbo.return_value = {"C:\\stable": 0}
        mock_traiter.return_value = ([], [], 0, 0)

        scanner()

        message = mock_notif.call_args[0][0]
        self.assertIn("Aucun dossier modifié ou nouveau", message)

    @patch.dict(os.environ, {"CHEMINS_RACINES": "C:\\test", "CHEMINS_EXCLUS": ""})
    @patch("scanner.deconnecter_base_de_donnees")
    @patch("scanner.envoyer_notif_teams")
    @patch("scanner.terminer_scan")
    @patch("scanner.traiter_dossiers_en_lot")
    @patch("scanner.scanner_arborescence")
    @patch("scanner.creer_scan")
    @patch("scanner.connecter_base_de_donnees")
    def test_message_contient_la_date(
        self,
        mock_connect,
        mock_creer,
        mock_scanner_arbo,
        mock_traiter,
        mock_terminer,
        mock_notif,
        mock_deconnect,
    ):
        """Le message doit contenir la date et l'heure du scan."""
        mock_connect.return_value = MagicMock()
        mock_creer.return_value = 1
        mock_scanner_arbo.return_value = {}
        mock_traiter.return_value = ([], [], 0, 0)

        scanner()

        message = mock_notif.call_args[0][0]
        self.assertIn("📅", message)

    @patch.dict(os.environ, {"CHEMINS_RACINES": "C:\\test", "CHEMINS_EXCLUS": ""})
    @patch("scanner.deconnecter_base_de_donnees")
    @patch("scanner.envoyer_notif_teams")
    @patch("scanner.terminer_scan")
    @patch("scanner.traiter_dossiers_en_lot")
    @patch("scanner.scanner_arborescence")
    @patch("scanner.creer_scan")
    @patch("scanner.connecter_base_de_donnees")
    def test_signe_negatif_pour_reduction(
        self,
        mock_connect,
        mock_creer,
        mock_scanner_arbo,
        mock_traiter,
        mock_terminer,
        mock_notif,
        mock_deconnect,
    ):
        """Une réduction de taille doit afficher un signe négatif."""
        mock_connect.return_value = MagicMock()
        mock_creer.return_value = 1
        mock_scanner_arbo.return_value = {"C:\\reduit": 0}
        mock_traiter.return_value = (
            [],
            [{"type": "modification", "chemin": "C:\\reduit", "difference": -200}],
            0,
            -200,
        )

        scanner()

        message = mock_notif.call_args[0][0]
        self.assertIn("-    200", message)


if __name__ == "__main__":
    unittest.main()
