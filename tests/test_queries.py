import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Ajoute le dossier racine au PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from intranet.queries import (
    get_connexion,
    get_derniers_scans,
    get_scans_history,
    get_scan_details,
    get_stats_dashboard,
)


class TestQueries(unittest.TestCase):
    """Tests pour les fonctions SQL de l'Intranet (intranet/queries.py)."""

    @patch("intranet.queries.mysql.connector.connect")
    def test_get_connexion_reussie(self, mock_connect):
        """Vérifie que la connexion est retournée si réussie."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        self.assertEqual(get_connexion(), mock_conn)

    @patch("intranet.queries.mysql.connector.connect")
    def test_get_connexion_echec(self, mock_connect):
        """Vérifie que None est retourné en cas d'erreur de connexion."""
        import mysql.connector
        mock_connect.side_effect = mysql.connector.Error("Erreur")
        self.assertIsNone(get_connexion())

    @patch("intranet.queries.get_connexion")
    def test_get_derniers_scans(self, mock_get_conn):
        """Vérifie que les derniers scans sont retournés correctement."""
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur
        
        # Données factices
        scans = [{"id_scan": 1, "date_": "2026-04-24", "status": "completed"}]
        mock_cur.fetchall.return_value = scans

        resultat = get_derniers_scans(5)
        
        self.assertEqual(resultat, scans)
        mock_conn.cursor.assert_called_with(dictionary=True)
        mock_conn.close.assert_called_once()

    @patch("intranet.queries.get_connexion")
    def test_get_scans_history_sans_connexion(self, mock_get_conn):
        """Si la connexion échoue, retourne une liste vide."""
        mock_get_conn.return_value = None
        self.assertEqual(get_scans_history(), [])

    @patch("intranet.queries.get_connexion")
    def test_get_scan_details_vide(self, mock_get_conn):
        """Si le scan n'existe pas, retourne un dict vide."""
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur
        
        mock_cur.fetchone.return_value = None  # Aucun scan trouvé
        
        resultat = get_scan_details(99)
        self.assertEqual(resultat, {})

    @patch("intranet.queries.get_connexion")
    def test_get_stats_dashboard(self, mock_get_conn):
        """Vérifie que les stats du dashboard sont bien agrégées."""
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur
        
        # Mock des retours fetchone() et fetchall()
        # 1. dernier_scan
        # 2. total_dossiers
        # 3. total_scans
        mock_cur.fetchone.side_effect = [
            {"id_scan": 2, "date_": "2026-04-24", "status": "completed"},
            {"total": 1500},
            {"total": 10}
        ]
        
        # 4. deux_derniers scans (fetchall)
        # 5. top_changements (fetchall)
        mock_cur.fetchall.side_effect = [
            [{"id_scan": 2}, {"id_scan": 1}],
            [{"id_folder": 1, "path": "C:\\test", "diff_kb": 5000}]
        ]

        resultat = get_stats_dashboard()
        
        self.assertEqual(resultat["total_dossiers"], 1500)
        self.assertEqual(resultat["total_scans"], 10)
        self.assertEqual(resultat["dernier_scan"]["id_scan"], 2)
        self.assertEqual(len(resultat["top_changements"]), 1)
        mock_conn.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
