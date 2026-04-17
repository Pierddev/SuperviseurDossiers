-- ============================================================
-- Index de performance pour améliorer la vitesse des scans
-- SuperviseurDossiers — fix/optimize-scan-performance
-- ============================================================

USE superviseur_dossiers;

-- Index sur is_deleted pour accélérer les requêtes de détection de suppressions
CREATE INDEX idx_folders_is_deleted ON folders(is_deleted);

-- Index sur is_new pour accélérer la réinitialisation des tags
CREATE INDEX idx_folders_is_new ON folders(is_new);

-- Index composite pour les requêtes filtrant sur is_deleted + path
CREATE INDEX idx_folders_deleted_path ON folders(is_deleted, path(100));

-- Index composite pour les requêtes filtrant sur is_new + path
CREATE INDEX idx_folders_new_path ON folders(is_new, path(100));
