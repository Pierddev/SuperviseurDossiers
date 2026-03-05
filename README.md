# 📁 Superviseur de Dossiers

Script Python déployé sur **Windows Server** qui analyse automatiquement la taille de tous les dossiers d'un chemin racine, stocke les résultats dans une base de données **MySQL** et envoie des notifications **Microsoft Teams** en cas de changements importants.

## 📑 Sommaire

- [Fonctionnalités](#-fonctionnalités)
- [Prérequis](#-prérequis)
- [Base de données](#-base-de-données)
    - [Schéma SQL](#schéma-sql)
- [Configuration](#-configuration)
- [Installation](#-installation)
- [Déploiement sur Windows Server](#-déploiement-sur-windows-server)
- [Structure du projet](#-structure-du-projet)
- [Technologies](#-technologies)

## 🎯 Fonctionnalités

- **Scan récursif** — Parcourt tous les dossiers et sous-dossiers à partir d'un chemin racine configurable
- **Exclusion de chemins** — Permet d'exclure des dossiers du scan (ex: `C:\Windows`)
- **Stockage en BDD** — Enregistre la taille de chaque dossier en Mo avec historique léger (taille actuelle + taille du dernier scan)
- **Détection des changements** — Identifie les nouveaux dossiers et les variations de taille significatives (seuil configurable)
- **Notifications Teams** — Envoie un résumé après chaque scan via webhook Microsoft Teams
- **Logging** — Enregistre les erreurs dans un fichier `superviseur.log`
- **Planification** — Scan quotidien automatique à une heure configurable
- **Scan manuel** — Possibilité de lancer un scan immédiat via `.\SuperviseurDossiers.exe --scan-now`

## 📋 Prérequis

- Python 3.10+
- MySQL 8.0+
- Un webhook Microsoft Teams

## 🗄️ Base de données

Le script utilise 3 tables :

| Table           | Rôle                                                                      |
| --------------- | ------------------------------------------------------------------------- |
| `sudo_dossiers` | Stocke les chemins des dossiers et leur statut (nouveau ou non)           |
| `sudo_tailles`  | Stocke la taille actuelle et la taille du dernier scan de chaque dossier  |
| `sudo_scans`    | Historique des scans avec leur date et statut (en_cours, termine, erreur) |

### Schéma SQL

```sql
CREATE DATABASE IF NOT EXISTS superviseur_dossiers;
USE superviseur_dossiers;

CREATE TABLE IF NOT EXISTS sudo_dossiers (
  id_dossier INT NOT NULL AUTO_INCREMENT,
  dossier_chemin VARCHAR(300) NOT NULL,
  dossier_est_nouveau TINYINT NULL,
  PRIMARY KEY (id_dossier)
) ENGINE = InnoDB;

CREATE TABLE IF NOT EXISTS sudo_tailles (
  id_dossier INT NOT NULL,
  taille_actuel_scan INT NULL,
  taille_dernier_scan INT NULL,
  PRIMARY KEY (id_dossier),
  CONSTRAINT fk_id_dossier
    FOREIGN KEY (id_dossier)
    REFERENCES sudo_dossiers (id_dossier)
) ENGINE = InnoDB;

CREATE TABLE IF NOT EXISTS sudo_scans (
  id_scan INT NOT NULL AUTO_INCREMENT,
  scan_date TIMESTAMP NULL,
  scan_statut ENUM('en_cours', 'termine', 'erreur') NULL,
  PRIMARY KEY (id_scan)
) ENGINE = InnoDB;

-- Index pour optimiser les recherches par chemin de dossier
CREATE INDEX idx_dossier_chemin ON sudo_dossiers(dossier_chemin);
```

### Mise en place

1. **Installer MySQL** sur le serveur si ce n'est pas déjà fait :
    - Télécharger MySQL Installer depuis [dev.mysql.com/downloads/installer/](https://dev.mysql.com/downloads/installer/)
    - Installer **MySQL Server** et définir un mot de passe root lors de l'installation

2. Ouvrir une **invite de commandes** (cmd) sur le serveur :

```cmd
mysql -u root -p
```

> 💡 Si `mysql` n'est pas reconnu, utilisez le chemin complet :

```cmd
"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe" -u root -p
```

3. Copier-coller le **schéma SQL ci-dessus** dans le terminal MySQL

4. Vérifier que les tables sont créées :

```sql
SHOW TABLES;
```

Résultat attendu :

```
+------------------------------------+
| Tables_in_superviseur_dossiers     |
+------------------------------------+
| sudo_dossiers                      |
| sudo_scans                         |
| sudo_tailles                       |
+------------------------------------+
```

5. Quitter MySQL :

```sql
EXIT;
```

## ⚙️ Configuration

Créer un fichier `.env` à la racine du projet :

```env
# Base de données
DB_HOST="localhost"
DB_PORT=3306
DB_USER="root"
DB_PASSWORD="votre_mot_de_passe"
DB_NAME="superviseur_dossiers"

# Webhook Microsoft Teams
TEAMS_WEBHOOK_URL="https://votre-webhook-teams.com/..."

# Chemins racines à scanner (séparés par des virgules)
# Supporte les chemins locaux et réseau (UNC)
CHEMINS_RACINES=C:\,D:\Data,\\ServeurNAS\Partage

# Chemins à exclure du scan (séparés par des virgules)
# Les sous-dossiers des chemins exclus ne seront pas scannés
CHEMINS_EXCLUS=C:\Windows,C:\Program Files,C:\Program Files (x86)

# Heure du scan quotidien (format HH:MM)
HEURE_SCAN="17:30"

# Seuil de notification (en Mo)
# Seuls les nouveaux dossiers et les variations de taille dépassant ce seuil
# seront inclus dans la notification Teams
MODIFICATION_TAILLE_IMPORTANTE=100

# Délai entre chaque vérification de l'heure (en secondes, par défaut 5 minutes)
DELAI_VERIFICATION=300
```

## 🚀 Installation

```bash
# Cloner le dépôt
git clone https://github.com/Pierddev/SuperviseurDossiers.git
cd SuperviseurDossiers

# Créer l'environnement virtuel
python -m venv .venv

# Activer l'environnement virtuel
.venv\Scripts\activate

# Installer les dépendances
pip install -r requirements.txt

# Configurer le fichier .env
cp .env.example .env
# Éditer .env avec vos paramètres

# Créer les tables dans MySQL
# Exécuter le schéma SQL ci-dessus dans votre base de données

# Lancer le script (mode planifié)
python main.py

# Lancer un scan immédiat (puis quitte)
python main.py --scan-now
```

## 📦 Déploiement sur Windows Server

### 1. Générer l'exécutable

```bash
pip install pyinstaller
pyinstaller --onefile --name SuperviseurDossiers --icon=icone.ico main.py
```

Le fichier `dist/SuperviseurDossiers.exe` est créé.

### 2. Copier les fichiers sur le serveur

Placer ces 2 fichiers dans un dossier sur le serveur (ex: `C:\SuperviseurDossiers\`) :

```
C:\SuperviseurDossiers\
├── SuperviseurDossiers.exe    # L'exécutable
└── .env                       # Configuration adaptée au serveur
```

> ⚠️ Le fichier `.env` doit être adapté avec les paramètres du serveur (BDD, webhook, chemin racine à analyser).

### 3. Démarrage automatique au boot

Créer une tâche planifiée (en **administrateur**) :

```cmd
schtasks /create /tn "SuperviseurDossiers" /tr "C:\votre_chemin\SuperviseurDossiers\SuperviseurDossiers.exe" /sc onstart /ru SYSTEM /rl HIGHEST
```

| Paramètre     | Signification                    |
| ------------- | -------------------------------- |
| `/tn`         | Nom de la tâche                  |
| `/tr`         | Chemin vers le .exe              |
| `/sc onstart` | Se lance au démarrage du serveur |
| `/ru SYSTEM`  | Tourne sous le compte SYSTEM     |
| `/rl HIGHEST` | Privilèges élevés                |

## 📬 Exemple de notification Teams

```
Scan du 18/02/2026 à 17:30

Nouveaux dossiers :
- C:\Projets\NouveauProjet (+250.45 Mo)

Dossiers modifiés :
- C:\Users\Documents (+150.30 Mo)
- C:\Backup\Archives (-200.00 Mo)

Variation totale : +200.75 Mo

Scan terminé avec succès
⏱️ Durée du scan : 10s
```

## 📂 Structure du projet

```
SuperviseurDossiers/
├── main.py              # Script principal
├── requirements.txt     # Dépendances Python
├── .env                 # Configuration (non versionné)
├── .gitignore
├── superviseur.log      # Fichier de logs (généré automatiquement)
└── tests/               # Tests
```

## 🛠️ Technologies

- **Python** — Langage principal
- **MySQL** — Base de données
- **Microsoft Teams** — Notifications via webhook
- **os.walk()** — Parcours récursif des dossiers
- **python-dotenv** — Gestion des variables d'environnement
- **schedule** — Planification des tâches
