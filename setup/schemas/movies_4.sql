-- Schema definitions for movies_4
-- Auto-extracted from sources/movies_4/postgres.sh

-- Table: movie_cast
CREATE TABLE IF NOT EXISTS movie_cast (
    movie_id       INTEGER DEFAULT NULL,
    person_id      INTEGER DEFAULT NULL,
    character_name TEXT DEFAULT NULL,
    gender_id      INTEGER DEFAULT NULL,
    cast_order     INTEGER DEFAULT NULL
);

-- Table: movie_company
CREATE TABLE IF NOT EXISTS movie_company (
    movie_id   INTEGER DEFAULT NULL,
    company_id INTEGER DEFAULT NULL
);

-- Table: movie_crew
CREATE TABLE IF NOT EXISTS movie_crew (
    movie_id      INTEGER DEFAULT NULL,
    person_id     INTEGER DEFAULT NULL,
    department_id INTEGER DEFAULT NULL,
    job           TEXT DEFAULT NULL
);

-- Table: production_country
CREATE TABLE IF NOT EXISTS production_country (
    movie_id   INTEGER DEFAULT NULL,
    country_id INTEGER DEFAULT NULL
);

