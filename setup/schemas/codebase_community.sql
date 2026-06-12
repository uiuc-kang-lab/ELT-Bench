-- Schema definitions for codebase_community
-- Auto-extracted from sources/codebase_community/postgres.sh

-- Table: postlinks
CREATE TABLE IF NOT EXISTS postlinks (
    Id            SERIAL PRIMARY KEY,
    CreationDate  TIMESTAMP NULL,
    PostId        INTEGER NULL,
    RelatedPostId INTEGER NULL,
    LinkTypeId    INTEGER NULL
);

