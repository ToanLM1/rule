TRUNCATE TABLE occupation_class, region_eligibility, rate_table, product_master;

INSERT INTO product_master (product_code, product_name_kr, min_age, max_age) VALUES
    ('CANCER_BASIC', '암보험 기본형', 18, 65),
    ('SAVINGS_PLUS', '저축보험 플러스', 19, 70);

INSERT INTO rate_table (product_code, age_band, smoker, base_rate, loading_pct) VALUES
    ('CANCER_BASIC', '18-39', FALSE, 100.00, 0),
    ('CANCER_BASIC', '18-39', TRUE, 100.00, 20),
    ('CANCER_BASIC', '40-59', FALSE, 130.00, 0),
    ('CANCER_BASIC', '40-59', TRUE, 130.00, 20),
    ('CANCER_BASIC', '60-65', FALSE, 180.00, 30),
    ('CANCER_BASIC', '60-65', TRUE, 180.00, 50),
    ('SAVINGS_PLUS', '19-70', FALSE, 80.00, 0);

INSERT INTO region_eligibility (region_code, region_name_kr, eligible) VALUES
    ('SEOUL', '서울', TRUE),
    ('BUSAN', '부산', TRUE),
    ('DAEGU', '대구', TRUE),
    ('JEJU', '제주', FALSE),
    ('ULLEUNG', '울릉', FALSE);

INSERT INTO occupation_class (class_code, name_kr, required_doc) VALUES
    (1, '사무직', NULL),
    (2, '판매직', NULL),
    (3, '경공업', NULL),
    (4, '중공업', 'DOC_HEALTH_CHECK'),
    (5, '고위험 직군', 'DOC_HEALTH_CHECK');
