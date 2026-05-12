-- ============================================================
-- Script d'installation unique — SuperviseurDossiers
-- ============================================================
-- Exécuter une seule fois pour créer la base et les tables.
-- Usage : mysql -u root -p < sql/setup.sql
-- ============================================================

CREATE DATABASE IF NOT EXISTS superviseur_dossiers
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_general_ci;
USE superviseur_dossiers;

-- ------------------------------------------------------------
-- 1. Création des nouvelles tables
-- ------------------------------------------------------------
CREATE TABLE folders (
    id_folder  BIGINT       NOT NULL AUTO_INCREMENT,
    path       VARCHAR(512) NOT NULL,
    is_new     TINYINT(1)   NOT NULL DEFAULT 1,
    is_root    TINYINT(1)   NOT NULL DEFAULT 0,
    is_deleted TINYINT(1)   NOT NULL DEFAULT 0,
    PRIMARY KEY (id_folder),
    UNIQUE KEY uq_path (path)
);

CREATE TABLE scans (
    id_scan       BIGINT       NOT NULL AUTO_INCREMENT,
    date_         TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    date_end      TIMESTAMP    NULL     DEFAULT NULL,
    status        VARCHAR(20)  NOT NULL DEFAULT 'in_progress',
    total_folders INT          NULL     DEFAULT NULL,
    total_size_kb BIGINT       NULL     DEFAULT NULL,
    PRIMARY KEY (id_scan)
);

CREATE TABLE sizes (
    id_scan    BIGINT  NOT NULL,
    id_folder  BIGINT  NOT NULL,
    size_kb    BIGINT  NOT NULL,
    PRIMARY KEY (id_scan, id_folder),
    FOREIGN KEY (id_scan)   REFERENCES scans(id_scan),
    FOREIGN KEY (id_folder) REFERENCES folders(id_folder)
);

-- ------------------------------------------------------------
-- 2. Index de performance
-- ------------------------------------------------------------
CREATE INDEX idx_scan_status_date     ON scans(status, date_);
CREATE INDEX idx_sizes_id_folder      ON sizes(id_folder);
CREATE INDEX idx_folders_is_deleted   ON folders(is_deleted);
CREATE INDEX idx_folders_is_new       ON folders(is_new);
CREATE INDEX idx_folders_deleted_path ON folders(is_deleted, path(100));
CREATE INDEX idx_folders_new_path     ON folders(is_new, path(100));
