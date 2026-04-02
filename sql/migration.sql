-- ============================================================
-- Migration vers MariaDB avec historisation complète
-- SuperviseurDossiers — feature/intranet-historisation
-- ============================================================

CREATE DATABASE IF NOT EXISTS superviseur_dossiers
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_general_ci;
USE superviseur_dossiers;

-- ------------------------------------------------------------
-- 1. Suppression des anciennes tables (ordre important pour les FK)
-- ------------------------------------------------------------
DROP TABLE IF EXISTS sudo_tailles;
DROP TABLE IF EXISTS sudo_dossiers;
DROP TABLE IF EXISTS sudo_scans;


-- ------------------------------------------------------------
-- 2. Création des nouvelles tables
-- ------------------------------------------------------------

CREATE TABLE folders (
    id_folder  BIGINT       NOT NULL AUTO_INCREMENT,
    path       VARCHAR(512) NOT NULL,
    is_new     TINYINT(1)   NOT NULL DEFAULT 1,
    PRIMARY KEY (id_folder),
    UNIQUE KEY uq_path (path)
);

CREATE TABLE scans (
    id_scan    BIGINT       NOT NULL AUTO_INCREMENT,
    date_      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status     VARCHAR(20)  NOT NULL DEFAULT 'in_progress',
    PRIMARY KEY (id_scan)
);

CREATE TABLE sizes (
    id_scan    BIGINT  NOT NULL,
    id_folder  BIGINT  NOT NULL,
    size_kb    BIGINT  NOT NULL,   -- taille en Ko
    PRIMARY KEY (id_scan, id_folder),
    FOREIGN KEY (id_scan)   REFERENCES scans(id_scan),
    FOREIGN KEY (id_folder) REFERENCES folders(id_folder)
);
