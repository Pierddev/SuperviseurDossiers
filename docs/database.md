# 🗄️ Base de données

> Ce document décrit le schéma MariaDB utilisé par SuperviseurDossiers depuis la version avec historisation complète.

## Prérequis

- **MariaDB 10.6+** (recommandé)
- Un utilisateur disposant des droits `CREATE`, `INSERT`, `UPDATE`, `SELECT` sur la base

## Tables

| Table     | Rôle                                                                 |
| --------- | -------------------------------------------------------------------- |
| `folders` | Stocke le chemin de chaque dossier scanné et son statut (nouveau ou non) |
| `scans`   | Enregistre chaque exécution de scan (date début, date fin + statut) |
| `sizes`   | Lie un dossier à un scan avec sa taille en Ko — permet l'historisation complète |

### Détail des tables

#### `folders`

| Colonne     | Type          | Description                                         |
| ----------- | ------------- | --------------------------------------------------- |
| `id_folder` | `BIGINT` (PK) | Identifiant unique du dossier                       |
| `path`      | `VARCHAR(512)`| Chemin absolu du dossier (unique)                   |
| `is_new`    | `TINYINT(1)`  | `1` si le dossier est nouveau, `0` sinon            |

#### `scans`

| Colonne    | Type          | Description                                                        |
| ---------- | ------------- | ------------------------------------------------------------------ |
| `id_scan`  | `BIGINT` (PK) | Identifiant unique du scan                                         |
| `date_`    | `TIMESTAMP`   | Date et heure de **début** du scan (UTC)                           |
| `date_end` | `TIMESTAMP`   | Date et heure de **fin** du scan (NULL tant que le scan tourne)    |
| `status`   | `VARCHAR(20)` | Statut : `in_progress`, `completed`, `failed`                      |

#### `sizes`

| Colonne     | Type    | Description                                      |
| ----------- | ------- | ------------------------------------------------ |
| `id_scan`   | `BIGINT`| Référence vers `scans.id_scan` (FK)              |
| `id_folder` | `BIGINT`| Référence vers `folders.id_folder` (FK)          |
| `size_kb`   | `BIGINT`| Taille du dossier en **Ko** au moment du scan    |

> **Convention :** Les tailles sont stockées en Ko. La conversion en Mo, Go, etc. se fait à l'affichage (intranet, notifications Teams).

## Installation

### 1. Index de performance (en plus des clés primaires et uniques)

| Index                 | Table   | Colinne(s)       | Utilité                               |
| --------------------- | ------- | ---------------- | ------------------------------------- |
| `uq_path`             | `folders` | `path`         | Recherche de dossier par chemin (UNIQUE) |
| `idx_scan_status_date` | `scans`   | `status, date_`| Trouver le dernier scan `completed`   |
| `idx_sizes_id_folder`  | `sizes`   | `id_folder`    | Historique complet d'un dossier       |

### 2. Lancer le script de migration

Depuis une invite de commandes, exécuter le fichier fourni dans `sql/migration.sql` :

```cmd
mariadb -u root -p < sql/migration.sql
```

> 💡 Ce script crée la base `superviseur_dossiers` si elle n'existe pas déjà, puis crée les 3 tables avec le bon encodage (`utf8mb4 / utf8mb4_general_ci`).

### 2. Vérifier les tables

```sql
USE superviseur_dossiers;
SHOW TABLES;
```

Résultat attendu :

```
+----------------------------------+
| Tables_in_superviseur_dossiers   |
+----------------------------------+
| folders                          |
| scans                            |
| sizes                            |
+----------------------------------+
```

### 3. Mettre à jour le `.env`

S'assurer que le fichier `.env` pointe vers l'instance MariaDB :

```env
DB_HOST="localhost"
DB_PORT=3306
DB_USER="root"
DB_PASSWORD="votre_mot_de_passe"
DB_NAME="superviseur_dossiers"
```

> ⚠️ Si MySQL et MariaDB cohabitent sur la même machine, MariaDB aura peut-être été installé sur le port `3307`. Adapter `DB_PORT` en conséquence.
