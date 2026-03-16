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

from fichiers import (
    calculer_taille_dossier,
    lister_tous_les_dossier,
    est_chemin_exclu,
    scanner_arborescence,
    filtrer_dossiers_redondants,
)


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


class TestEstCheminExclu(unittest.TestCase):
    """Tests pour la fonction est_chemin_exclu."""

    def test_chemin_exactement_exclu(self):
        """Un chemin identique à un chemin exclu doit retourner True."""
        self.assertTrue(est_chemin_exclu("C:\\Windows", ["C:\\Windows"]))

    def test_sous_chemin_exclu(self):
        """Un sous-chemin d'un chemin exclu doit retourner True."""
        self.assertTrue(est_chemin_exclu("C:\\Windows\\System32", ["C:\\Windows"]))

    def test_chemin_non_exclu(self):
        """Un chemin qui ne correspond à aucune exclusion doit retourner False."""
        self.assertFalse(est_chemin_exclu("C:\\Users", ["C:\\Windows"]))

    def test_liste_exclusions_vide(self):
        """Avec une liste vide, aucun chemin ne doit être exclu."""
        self.assertFalse(est_chemin_exclu("C:\\Windows", []))

    def test_comparaison_insensible_casse(self):
        """La comparaison doit être insensible à la casse (Windows)."""
        self.assertTrue(est_chemin_exclu("C:\\WINDOWS", ["C:\\windows"]))
        self.assertTrue(est_chemin_exclu("c:\\windows", ["C:\\Windows"]))

    def test_chemin_similaire_non_exclu(self):
        """Un chemin qui commence par le même préfixe mais n'est pas un sous-dossier ne doit pas être exclu."""
        # C:\WindowsApps ne doit PAS être exclu si on exclut C:\Windows
        self.assertFalse(est_chemin_exclu("C:\\WindowsApps", ["C:\\Windows"]))

    def test_plusieurs_exclusions(self):
        """Doit fonctionner avec plusieurs chemins exclus."""
        exclusions = ["C:\\Windows", "C:\\Program Files"]
        self.assertTrue(est_chemin_exclu("C:\\Windows\\System32", exclusions))
        self.assertTrue(est_chemin_exclu("C:\\Program Files\\App", exclusions))
        self.assertFalse(est_chemin_exclu("C:\\Users", exclusions))


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

    def test_exclusion_dossier(self):
        """Un dossier exclu ne doit pas apparaître dans la liste."""
        os.makedirs(os.path.join(self.dossier_temp, "inclus"))
        chemin_exclu = os.path.join(self.dossier_temp, "exclu")
        os.makedirs(chemin_exclu)
        resultat = lister_tous_les_dossier(self.dossier_temp, [chemin_exclu])
        self.assertNotIn(chemin_exclu, resultat)
        self.assertIn(os.path.join(self.dossier_temp, "inclus"), resultat)

    def test_exclusion_sous_dossiers(self):
        """Les sous-dossiers d'un dossier exclu ne doivent pas apparaître."""
        chemin_exclu = os.path.join(self.dossier_temp, "exclu")
        os.makedirs(os.path.join(chemin_exclu, "profond", "tres_profond"))
        resultat = lister_tous_les_dossier(self.dossier_temp, [chemin_exclu])
        # Seul le dossier racine doit être dans la liste
        self.assertEqual(len(resultat), 1)
        self.assertEqual(resultat[0], self.dossier_temp)

    def test_exclusion_vide(self):
        """Avec une liste d'exclusion vide, tous les dossiers doivent être listés."""
        os.makedirs(os.path.join(self.dossier_temp, "dossier_a"))
        os.makedirs(os.path.join(self.dossier_temp, "dossier_b"))
        resultat = lister_tous_les_dossier(self.dossier_temp, [])
        self.assertEqual(len(resultat), 3)  # racine + 2 sous-dossiers

    def test_sans_exclusion_retrocompatible(self):
        """Sans paramètre d'exclusion, le comportement doit être identique."""
        os.makedirs(os.path.join(self.dossier_temp, "dossier_a"))
        resultat = lister_tous_les_dossier(self.dossier_temp)
        self.assertEqual(len(resultat), 2)  # racine + 1 sous-dossier


class TestScannerArborescence(unittest.TestCase):
    """Tests pour la fonction scanner_arborescence."""

    def setUp(self):
        self.dossier_temp = tempfile.mkdtemp()

    def tearDown(self):
        import shutil

        shutil.rmtree(self.dossier_temp, ignore_errors=True)

    def _creer_fichier(self, chemin_relatif, contenu):
        chemin_complet = os.path.join(self.dossier_temp, chemin_relatif)
        os.makedirs(os.path.dirname(chemin_complet), exist_ok=True)
        with open(chemin_complet, "w") as f:
            f.write(contenu)
        return chemin_complet

    def test_dossier_vide(self):
        """Un dossier vide doit avoir une taille de 0."""
        resultat = scanner_arborescence(self.dossier_temp)
        self.assertEqual(resultat[self.dossier_temp], 0)

    def test_fichier_direct(self):
        """La taille doit correspondre au fichier direct."""
        self._creer_fichier("fichier.txt", "Bonjour")
        resultat = scanner_arborescence(self.dossier_temp)
        taille_attendue = os.path.getsize(
            os.path.join(self.dossier_temp, "fichier.txt")
        )
        self.assertEqual(resultat[self.dossier_temp], taille_attendue)

    def test_parent_inclut_enfants(self):
        """La taille du parent doit inclure la taille des sous-dossiers."""
        self._creer_fichier("racine.txt", "racine")
        self._creer_fichier("sous/profond.txt", "profond")
        resultat = scanner_arborescence(self.dossier_temp)
        taille_racine = os.path.getsize(os.path.join(self.dossier_temp, "racine.txt"))
        taille_profond = os.path.getsize(
            os.path.join(self.dossier_temp, "sous", "profond.txt")
        )
        # Le parent doit contenir la somme
        self.assertEqual(resultat[self.dossier_temp], taille_racine + taille_profond)
        # Le sous-dossier doit contenir uniquement son fichier
        self.assertEqual(
            resultat[os.path.join(self.dossier_temp, "sous")], taille_profond
        )

    def test_exclusion(self):
        """Un dossier exclu ne doit pas apparaître dans le résultat."""
        self._creer_fichier("inclus/a.txt", "aaa")
        chemin_exclu = os.path.join(self.dossier_temp, "exclu")
        self._creer_fichier("exclu/b.txt", "bbb")
        resultat = scanner_arborescence(self.dossier_temp, [chemin_exclu])
        self.assertNotIn(chemin_exclu, resultat)
        self.assertIn(os.path.join(self.dossier_temp, "inclus"), resultat)

    def test_coherence_avec_calculer_taille(self):
        """Les tailles doivent être identiques à calculer_taille_dossier."""
        self._creer_fichier("a.txt", "AAA")
        self._creer_fichier("sous/b.txt", "BBBBBB")
        resultat = scanner_arborescence(self.dossier_temp)
        # Vérifie que chaque dossier a la même taille que calculer_taille_dossier
        for chemin, taille in resultat.items():
            self.assertEqual(taille, calculer_taille_dossier(chemin))

    def test_retourne_un_dict(self):
        """La fonction doit retourner un dictionnaire."""
        resultat = scanner_arborescence(self.dossier_temp)
        self.assertIsInstance(resultat, dict)


class TestFiltrerDossiersRedondants(unittest.TestCase):
    """Tests pour la fonction filtrer_dossiers_redondants."""

    def test_filtre_parents_cascade(self):
        """Les parents dont un enfant est dans la liste doivent être filtrés."""
        dossiers = [
            {"type": "modification", "chemin": "C:\\Users", "difference": 500},
            {"type": "modification", "chemin": "C:\\Users\\Pierre", "difference": 500},
            {
                "type": "modification",
                "chemin": "C:\\Users\\Pierre\\Desktop",
                "difference": 500,
            },
        ]
        resultat = filtrer_dossiers_redondants(dossiers)
        self.assertEqual(len(resultat), 1)
        self.assertEqual(resultat[0]["chemin"], "C:\\Users\\Pierre\\Desktop")

    def test_garde_dossiers_independants(self):
        """Des dossiers sans lien parent-enfant doivent tous être conservés."""
        dossiers = [
            {"type": "modification", "chemin": "C:\\Data", "difference": 100},
            {"type": "modification", "chemin": "D:\\Backup", "difference": 200},
        ]
        resultat = filtrer_dossiers_redondants(dossiers)
        self.assertEqual(len(resultat), 2)

    def test_liste_vide(self):
        """Une liste vide doit retourner une liste vide."""
        self.assertEqual(filtrer_dossiers_redondants([]), [])

    def test_un_seul_dossier(self):
        """Un seul dossier doit être conservé."""
        dossiers = [{"type": "nouveau", "chemin": "C:\\Data", "taille": 100}]
        resultat = filtrer_dossiers_redondants(dossiers)
        self.assertEqual(len(resultat), 1)

    def test_branches_multiples(self):
        """Quand un parent a plusieurs enfants dans la liste, le parent est filtré mais les enfants sont gardés."""
        dossiers = [
            {"type": "modification", "chemin": "C:\\Data", "difference": 300},
            {"type": "modification", "chemin": "C:\\Data\\ProjetA", "difference": 200},
            {"type": "modification", "chemin": "C:\\Data\\ProjetB", "difference": 100},
        ]
        resultat = filtrer_dossiers_redondants(dossiers)
        self.assertEqual(len(resultat), 2)
        chemins = [d["chemin"] for d in resultat]
        self.assertIn("C:\\Data\\ProjetA", chemins)
        self.assertIn("C:\\Data\\ProjetB", chemins)


if __name__ == "__main__":
    unittest.main()
