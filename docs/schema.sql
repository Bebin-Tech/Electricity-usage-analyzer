-- MySQL 8.0.16+ / 8.4. Use an empty electricity_analyzer database.
-- Application ORM definitions are the canonical schema. Existing databases need
-- reviewed migrations; this file intentionally does not drop or overwrite data.
CREATE TABLE users (
  id INTEGER NOT NULL AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  email VARCHAR(254) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  is_admin BOOLEAN NOT NULL,
  active BOOLEAN NOT NULL,
  created_at DATETIME NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE readings (
  id INTEGER NOT NULL AUTO_INCREMENT PRIMARY KEY,
  user_id INTEGER NOT NULL,
  date DATE NOT NULL,
  kwh FLOAT NOT NULL,
  source VARCHAR(20) NOT NULL,
  CONSTRAINT uq_daily_reading UNIQUE (user_id, date),
  CONSTRAINT chk_reading_kwh CHECK (kwh >= 0),
  FOREIGN KEY (user_id) REFERENCES users(id),
  INDEX ix_readings_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE appliances (
  id INTEGER NOT NULL AUTO_INCREMENT PRIMARY KEY,
  user_id INTEGER NOT NULL,
  name VARCHAR(100) NOT NULL,
  watts FLOAT NOT NULL,
  hours_per_day FLOAT NOT NULL,
  quantity INTEGER NOT NULL,
  CHECK (watts > 0),
  CHECK (hours_per_day >= 0 AND hours_per_day <= 24),
  CHECK (quantity >= 1),
  FOREIGN KEY (user_id) REFERENCES users(id),
  INDEX ix_appliances_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE tariff_settings (
  id INTEGER NOT NULL AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  rate_per_kwh FLOAT NOT NULL,
  fixed_charge FLOAT NOT NULL,
  currency VARCHAR(3) NOT NULL,
  CHECK (rate_per_kwh >= 0),
  CHECK (fixed_charge >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE prediction_history (
  id INTEGER NOT NULL AUTO_INCREMENT PRIMARY KEY,
  user_id INTEGER NOT NULL,
  created_at DATETIME NOT NULL,
  result_json LONGTEXT NOT NULL,
  FOREIGN KEY (user_id) REFERENCES users(id),
  INDEX ix_prediction_history_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE uploaded_datasets (
  id INTEGER NOT NULL AUTO_INCREMENT PRIMARY KEY,
  user_id INTEGER NOT NULL,
  filename VARCHAR(255) NOT NULL,
  row_count INTEGER NOT NULL,
  uploaded_at DATETIME NOT NULL,
  FOREIGN KEY (user_id) REFERENCES users(id),
  INDEX ix_uploaded_datasets_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Illustrative estimate configuration, not an official electricity tariff.
INSERT INTO tariff_settings (id, name, rate_per_kwh, fixed_charge, currency)
VALUES (1, 'Standard estimate', 6, 0, 'INR');
