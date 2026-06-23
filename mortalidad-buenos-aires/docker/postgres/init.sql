-- =====================================================================
-- Schema inicial: mortalidad-buenos-aires
-- Se ejecuta automáticamente la primera vez que el contenedor postgres
-- arranca (docker-entrypoint-initdb.d).
-- =====================================================================

-- =========================================
-- Dimensión: catálogo CIE-10 (capítulos)
-- =========================================
CREATE TABLE IF NOT EXISTS dim_cie10 (
    letra        CHAR(1) PRIMARY KEY,
    capitulo     TEXT    NOT NULL,
    descripcion  TEXT
);

INSERT INTO dim_cie10 (letra, capitulo, descripcion) VALUES
    ('A', 'Infecciosas y parasitarias', 'Enfermedades infecciosas y parasitarias (A00-B99)'),
    ('B', 'Infecciosas y parasitarias', 'Enfermedades infecciosas y parasitarias (A00-B99)'),
    ('C', 'Neoplasias',                  'Tumores malignos y benignos (C00-D48)'),
    ('D', 'Neoplasias / Sangre',         'Tumores y enfermedades de la sangre'),
    ('E', 'Endocrinas y metabólicas',    'Trastornos endocrinos, nutricionales y metabólicos (E00-E90)'),
    ('F', 'Trastornos mentales',         'Trastornos mentales y del comportamiento (F00-F99)'),
    ('G', 'Sistema nervioso',            'Enfermedades del sistema nervioso (G00-G99)'),
    ('H', 'Ojo / Oído',                  'Enfermedades del ojo y del oído (H00-H95)'),
    ('I', 'Aparato circulatorio',        'Enfermedades del sistema circulatorio (I00-I99)'),
    ('J', 'Aparato respiratorio',        'Enfermedades del sistema respiratorio (J00-J99)'),
    ('K', 'Aparato digestivo',           'Enfermedades del sistema digestivo (K00-K93)'),
    ('L', 'Piel y tejido subcutáneo',    'Enfermedades de la piel (L00-L99)'),
    ('M', 'Osteomuscular',               'Enfermedades del sistema osteomuscular (M00-M99)'),
    ('N', 'Aparato genitourinario',      'Enfermedades del sistema genitourinario (N00-N99)'),
    ('O', 'Embarazo y parto',            'Embarazo, parto y puerperio (O00-O99)'),
    ('P', 'Afecciones perinatales',      'Ciertas afecciones originadas en el período perinatal (P00-P96)'),
    ('Q', 'Malformaciones congénitas',   'Malformaciones congénitas (Q00-Q99)'),
    ('R', 'Síntomas y signos inespecíficos', 'Síntomas, signos y hallazgos anormales (R00-R99)'),
    ('S', 'Traumatismos y envenenamientos', 'Traumatismos, envenenamientos (S00-T98)'),
    ('T', 'Traumatismos y envenenamientos', 'Traumatismos, envenenamientos (S00-T98)'),
    ('V', 'Causas externas',             'Causas externas de morbilidad y mortalidad (V01-Y98)'),
    ('W', 'Causas externas',             'Causas externas de morbilidad y mortalidad'),
    ('X', 'Causas externas',             'Causas externas de morbilidad y mortalidad'),
    ('Y', 'Causas externas',             'Causas externas de morbilidad y mortalidad'),
    ('Z', 'Factores de salud',           'Factores que influyen en el estado de salud (Z00-Z99)'),
    ('U', 'Códigos especiales',          'Códigos para propósitos especiales (U00-U99)')
ON CONFLICT (letra) DO NOTHING;

-- =========================================
-- Dimensión: jurisdicción
-- =========================================
CREATE TABLE IF NOT EXISTS dim_jurisdiccion (
    nombre TEXT PRIMARY KEY,
    region TEXT
);

INSERT INTO dim_jurisdiccion (nombre, region) VALUES
    ('Buenos Aires',          'Pampeana'),
    ('Ciudad Autónoma de Buenos Aires', 'Pampeana'),
    ('Córdoba',               'Pampeana'),
    ('Santa Fe',              'Pampeana'),
    ('Mendoza',               'Cuyo')
ON CONFLICT (nombre) DO NOTHING;

-- =========================================
-- Tabla de hechos: fact_defunciones
-- =========================================
CREATE TABLE IF NOT EXISTS fact_defunciones (
    id                    BIGSERIAL PRIMARY KEY,
    anio                  INTEGER  NOT NULL,
    sexo                  TEXT     NOT NULL,
    grupo_edad            TEXT     NOT NULL,
    jurisdiccion          TEXT     NOT NULL,
    cie10_causa_id        TEXT,
    cie10_clasificacion   TEXT     NOT NULL,
    supracategoria        TEXT     NOT NULL,
    cantidad              INTEGER  NOT NULL,
    poblacion             BIGINT,
    tasa_por_100k         NUMERIC(10, 4)
);

CREATE INDEX IF NOT EXISTS idx_fact_anio        ON fact_defunciones (anio);
CREATE INDEX IF NOT EXISTS idx_fact_sexo        ON fact_defunciones (sexo);
CREATE INDEX IF NOT EXISTS idx_fact_grupo_edad  ON fact_defunciones (grupo_edad);
CREATE INDEX IF NOT EXISTS idx_fact_supracat    ON fact_defunciones (supracategoria);
CREATE INDEX IF NOT EXISTS idx_fact_anio_supra  ON fact_defunciones (anio, supracategoria);

-- =========================================
-- Vistas materializadas (consultas frecuentes del dashboard)
-- =========================================
CREATE OR REPLACE VIEW vw_tendencia_anual AS
SELECT
    anio,
    SUM(cantidad)            AS total_defunciones,
    AVG(tasa_por_100k)::NUMERIC(10, 4) AS tasa_promedio
FROM fact_defunciones
GROUP BY anio
ORDER BY anio;

CREATE OR REPLACE VIEW vw_top_causas AS
SELECT
    supracategoria,
    SUM(cantidad) AS total
FROM fact_defunciones
GROUP BY supracategoria
ORDER BY total DESC;

CREATE OR REPLACE VIEW vw_por_grupo_edad AS
SELECT
    grupo_edad,
    sexo,
    SUM(cantidad) AS total
FROM fact_defunciones
GROUP BY grupo_edad, sexo
ORDER BY grupo_edad, sexo;

-- =========================================
-- Artefactos ML (modelos persistidos como bytea)
-- Permite que el servicio ETL escriba modelos y el servicio API los lea
-- sin necesidad de volumen compartido (clave en Fly.io multi-app).
-- =========================================
CREATE TABLE IF NOT EXISTS ml_artifacts (
    name        TEXT PRIMARY KEY,
    payload     BYTEA NOT NULL,
    metadata    JSONB NOT NULL DEFAULT '{}'::jsonb,
    size_bytes  INTEGER GENERATED ALWAYS AS (octet_length(payload)) STORED,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ml_artifacts_updated ON ml_artifacts (updated_at DESC);
