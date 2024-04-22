CREATE TABLE galaxies
(
    id              SERIAL PRIMARY KEY NOT NULL,
    source_id       VARCHAR            NOT NULL UNIQUE,
    ra              DECIMAL(25, 20)    NOT NULL,
    dec             DECIMAL(25, 20)    NOT NULL,
    gal_prob        DECIMAL(25, 20)    NOT NULL,
    bin_id          SMALLINT           NOT NULL,
    status          VARCHAR            NOT NULL DEFAULT 'Pending',
    failed_attempts SMALLINT           NOT NULL DEFAULT 0
);

CREATE TABLE bands
(
    source_id   VARCHAR NOT NULL,
    band        CHAR    NOT NULL,
    error_count INT     NOT NULL DEFAULT 0,
    PRIMARY KEY (source_id, band),
    FOREIGN KEY (source_id) REFERENCES galaxies (source_id) ON DELETE CASCADE,
    CHECK (band IN ('g', 'r', 'i', 'z'))
);

CREATE TABLE rotations
(
    source_id     VARCHAR NOT NULL,
    band          CHAR    NOT NULL,
    degree        INT     NOT NULL,
    total_error   FLOAT DEFAULT 0,
    running_count INT   DEFAULT 0,
    PRIMARY KEY (source_id, band),
    FOREIGN KEY (source_id, band) REFERENCES bands (source_id, band) ON DELETE CASCADE
);

-- Galaxy Details View: combined data from galaxies, bands and rotations
CREATE VIEW galaxy_details AS
SELECT g.id            AS galaxy_id,
       g.source_id     AS galaxy_source_id,
       g.ra            AS galaxy_ra,
       g.dec           AS galaxy_dec,
       g.bin_id        AS galaxy_bin_id,
       g.status        AS galaxy_status,
       b.band          AS band_band,
       b.error_count   AS band_error_count,
       r.degree        AS rotations_degree,
       r.total_error   AS rotations_total_error,
       r.running_count AS rotations_running_count
FROM galaxies g
         JOIN bands b ON g.source_id = b.source_id
         LEFT JOIN rotations r ON b.source_id = r.source_id AND b.band = r.band;

-- Unused
CREATE TABLE ellipticity
(
    source_id VARCHAR NOT NULL,
    band      CHAR    NOT NULL,
    PRIMARY KEY (source_id, band),
    FOREIGN KEY (source_id, band) REFERENCES bands (source_id, band) ON DELETE CASCADE
);
