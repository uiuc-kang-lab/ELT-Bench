-- Schema definitions for movie_3
-- Auto-extracted from sources/movie_3/postgres.sh

-- Table: film_actor
CREATE TABLE IF NOT EXISTS film_actor (
    actor_id INTEGER NOT NULL,
  film_id INTEGER NOT NULL,
  last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
  PRIMARY KEY (actor_id, film_id)
);

-- Table: film_category
CREATE TABLE IF NOT EXISTS film_category (
    film_id INTEGER NOT NULL,
  category_id INTEGER NOT NULL,
  last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
  PRIMARY KEY (film_id, category_id)
);

-- Table: inventory
CREATE TABLE IF NOT EXISTS inventory (
    inventory_id SERIAL PRIMARY KEY,
  film_id INTEGER NOT NULL,
  store_id INTEGER NOT NULL,
  last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Table: payment
CREATE TABLE IF NOT EXISTS payment (
    payment_id SERIAL PRIMARY KEY,
  customer_id INTEGER NOT NULL,
  staff_id INTEGER NOT NULL,
  rental_id INTEGER,
  amount REAL NOT NULL,
  payment_date TIMESTAMP NOT NULL,
  last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Table: rental
CREATE TABLE IF NOT EXISTS rental (
    rental_id SERIAL PRIMARY KEY,
  rental_date TIMESTAMP NOT NULL,
  inventory_id INTEGER NOT NULL,
  customer_id INTEGER NOT NULL,
  return_date TIMESTAMP,
  staff_id INTEGER NOT NULL,
  last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
  UNIQUE (rental_date, inventory_id, customer_id)
);

