CREATE TABLE IF NOT EXISTS product_master (
    product_code VARCHAR(64) PRIMARY KEY,
    product_name_kr VARCHAR(200) NOT NULL,
    min_age INTEGER NOT NULL,
    max_age INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS rate_table (
    product_code VARCHAR(64) NOT NULL,
    age_band VARCHAR(32) NOT NULL,
    smoker BOOLEAN NOT NULL,
    base_rate NUMERIC(12, 2) NOT NULL,
    loading_pct INTEGER NOT NULL,
    PRIMARY KEY (product_code, age_band, smoker)
);

CREATE TABLE IF NOT EXISTS region_eligibility (
    region_code VARCHAR(32) PRIMARY KEY,
    region_name_kr VARCHAR(100) NOT NULL,
    eligible BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS occupation_class (
    class_code INTEGER PRIMARY KEY,
    name_kr VARCHAR(100) NOT NULL,
    required_doc VARCHAR(100)
);
