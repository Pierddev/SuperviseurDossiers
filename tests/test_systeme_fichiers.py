"""
Tests pour les fonctions liées au système de fichiers.
Vérifie calculer_taille_dossier et lister_tous_les_dossier.
NB: Ces tests ont été réalisés avec l'aide de l'Intelligence Artificielle.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from main import calculer_taille_dossier, lister_tous_les_dossier


class TestCalculerTailleDossier(unittest.TestCase):
    """Tests pour la fonction calculer_taille_dossier."""

    def setUp(self):
        """Crée une arborescence temporaire pour les tests."""
        self.dossier_temp = tempfile.mkdtemp()

    def tearDown(self):
        """Supprime l'arborescence temporaire après chaque test."""
        import shutil

        shutil.rmtree(self.dossier_temp, ignore_errors=True)

    def _creer_fichier(self, chemin_relatif, contenu):
        """Crée un fichier avec un contenu donné dans le dossier temporaire."""
        chemin_complet = os.path.join(self.dossier_temp, chemin_relatif)
        os.makedirs(os.path.dirname(chemin_complet), exist_ok=True)
        with open(chemin_complet, "w") as f:
            f.write(contenu)
        return chemin_complet

    def test_dossier_vide(self):
        """Un dossier vide doit avoir une taille de 0."""
        taille = calculer_taille_dossier(self.dossier_temp)
        self.assertEqual(taille, 0)

    def test_un_seul_fichier(self):
        """La taille doit correspondre à la taille du fichier."""
        self._creer_fichier("fichier.txt", "Bonjour")
        taille = calculer_taille_dossier(self.dossier_temp)
        taille_attendue = os.path.getsize(
            os.path.join(self.dossier_temp, "fichier.txt")
        )
        self.assertEqual(taille, taille_attendue)

    def test_plusieurs_fichiers(self):
        """La taille doit être la somme de tous les fichiers."""
        self._creer_fichier("a.txt", "AAA")
        self._creer_fichier("b.txt", "BBBBBB")
        taille = calculer_taille_dossier(self.dossier_temp)
        taille_a = os.path.getsize(os.path.join(self.dossier_temp, "a.txt"))
        taille_b = os.path.getsize(os.path.join(self.dossier_temp, "b.txt"))
        self.assertEqual(taille, taille_a + taille_b)

    def test_sous_dossiers(self):
        """La taille doit inclure les fichiers dans les sous-dossiers."""
        self._creer_fichier("racine.txt", "racine")
        self._creer_fichier("sous/profond.txt", "profond")
        taille = calculer_taille_dossier(self.dossier_temp)
        taille_racine = os.path.getsize(os.path.join(self.dossier_temp, "racine.txt"))
        taille_profond = os.path.getsize(
            os.path.join(self.dossier_temp, "sous", "profond.txt")
        )
        self.assertEqual(taille, taille_racine + taille_profond)

    def test_dossier_inexistant(self):
        """Un dossier inexistant doit retourner 0 (os.walk ne lève pas d'erreur)."""
        taille = calculer_taille_dossier(os.path.join(self.dossier_temp, "inexistant"))
        self.assertEqual(taille, 0)

    def test_retourne_un_entier(self):
        """La fonction doit toujours retourner un entier."""
        self._creer_fichier("test.txt", "contenu")
        taille = calculer_taille_dossier(self.dossier_temp)
        self.assertIsInstance(taille, int)


class TestListerTousLesDossier(unittest.TestCase):
    """Tests pour la fonction lister_tous_les_dossier."""

    def setUp(self):
        """Crée une arborescence temporaire pour les tests."""
        self.dossier_temp = tempfile.mkdtemp()

    def tearDown(self):
        """Supprime l'arborescence temporaire après chaque test."""
        import shutil

        shutil.rmtree(self.dossier_temp, ignore_errors=True)

    def test_dossier_vide(self):
        """Un dossier vide doit retourner uniquement le chemin racine."""
        resultat = lister_tous_les_dossier(self.dossier_temp)
        self.assertEqual(resultat, [self.dossier_temp])

    def test_contient_la_racine(self):
        """Le premier élément doit toujours être le chemin racine."""
        os.makedirs(os.path.join(self.dossier_temp, "sous_dossier"))
        resultat = lister_tous_les_dossier(self.dossier_temp)
        self.assertEqual(resultat[0], self.dossier_temp)

    def test_sous_dossiers_directs(self):
        """Doit lister les sous-dossiers directs."""
        os.makedirs(os.path.join(self.dossier_temp, "dossier_a"))
        os.makedirs(os.path.join(self.dossier_temp, "dossier_b"))
        resultat = lister_tous_les_dossier(self.dossier_temp)
        self.assertEqual(len(resultat), 3)  # racine + 2 sous-dossiers

    def test_sous_dossiers_imbriques(self):
        """Doit lister les sous-dossiers imbriqués récursivement."""
        os.makedirs(os.path.join(self.dossier_temp, "a", "b", "c"))
        resultat = lister_tous_les_dossier(self.dossier_temp)
        # racine + a + a/b + a/b/c = 4
        self.assertEqual(len(resultat), 4)

    def test_fichiers_non_inclus(self):
        """Les fichiers ne doivent pas apparaître dans la liste."""
        with open(os.path.join(self.dossier_temp, "fichier.txt"), "w") as f:
            f.write("test")
        resultat = lister_tous_les_dossier(self.dossier_temp)
        self.assertEqual(len(resultat), 1)  # uniquement la racine

    def test_retourne_une_liste(self):
        """La fonction doit retourner une liste."""
        resultat = lister_tous_les_dossier(self.dossier_temp)
        self.assertIsInstance(resultat, list)

    def test_chemins_complets(self):
        """Chaque élément doit être un chemin complet (absolu)."""
        os.makedirs(os.path.join(self.dossier_temp, "sous_dossier"))
        resultat = lister_tous_les_dossier(self.dossier_temp)
        for chemin in resultat:
            self.assertTrue(os.path.isabs(chemin))


if __name__ == "__main__":
    unittest.main()
