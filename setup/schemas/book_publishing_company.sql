-- Schema definitions for book_publishing_company
-- Auto-extracted from sources/book_publishing_company/postgres.sh

-- Table: roysched
CREATE TABLE IF NOT EXISTS roysched (
    title_id TEXT NOT NULL,
    lorange INTEGER,
    hirange INTEGER,
    royalty INTEGER
);

-- Table: sales
CREATE TABLE IF NOT EXISTS sales (
    stor_id TEXT NOT NULL,
    ord_num TEXT NOT NULL,
    ord_date TIMESTAMP NOT NULL,
    qty INTEGER NOT NULL,
    payterms TEXT NOT NULL,
    title_id TEXT NOT NULL,
    PRIMARY KEY (stor_id, ord_num, title_id)
);

