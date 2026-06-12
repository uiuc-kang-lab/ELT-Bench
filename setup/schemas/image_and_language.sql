-- Schema definitions for image_and_language
-- Auto-extracted from sources/image_and_language/postgres.sh

-- Table: img_obj
CREATE TABLE IF NOT EXISTS img_obj (
    IMG_ID        INTEGER DEFAULT 0 NOT NULL,
    OBJ_SAMPLE_ID INTEGER DEFAULT 0 NOT NULL,
    OBJ_CLASS_ID  INTEGER,
    X             INTEGER,
    Y             INTEGER,
    W             INTEGER,
    H             INTEGER,
    PRIMARY KEY (IMG_ID, OBJ_SAMPLE_ID)
);

-- Table: img_rel
CREATE TABLE IF NOT EXISTS img_rel (
    IMG_ID         INTEGER DEFAULT 0 NOT NULL,
    PRED_CLASS_ID  INTEGER DEFAULT 0 NOT NULL,
    OBJ1_SAMPLE_ID INTEGER DEFAULT 0 NOT NULL,
    OBJ2_SAMPLE_ID INTEGER DEFAULT 0 NOT NULL,
    PRIMARY KEY (IMG_ID, PRED_CLASS_ID, OBJ1_SAMPLE_ID, OBJ2_SAMPLE_ID)
);

