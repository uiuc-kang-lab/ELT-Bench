-- Schema definitions for shakespeare
-- Auto-extracted from sources/shakespeare/postgres.sh

-- Table: paragraphs
CREATE TABLE IF NOT EXISTS paragraphs (
    id SERIAL PRIMARY KEY,
    ParagraphNum INTEGER NOT NULL,
    PlainText TEXT NOT NULL,
    character_id INTEGER NOT NULL,
    chapter_id INTEGER DEFAULT 0 NOT NULL
);

