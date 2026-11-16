-- Genomics biobank: species, genome assemblies, genes, transposable elements,
-- and the people/plants whose DNA was sequenced.
--
-- Written for SQLite (the browser demo uses SQLite compiled to WebAssembly).
-- Everything except the trigger syntax is standard SQL and runs on PostgreSQL
-- with INTEGER PRIMARY KEY replaced by GENERATED ALWAYS AS IDENTITY.

PRAGMA foreign_keys = ON;

------------------------------------------------------------------------------
-- Reference data: what genomes exist and what is annotated on them
------------------------------------------------------------------------------

CREATE TABLE species (
    species_id      INTEGER PRIMARY KEY,
    scientific_name TEXT    NOT NULL UNIQUE,
    common_name     TEXT,
    kingdom         TEXT    NOT NULL CHECK (kingdom IN ('Animalia', 'Plantae', 'Bacteria')),
    genome_size_mb  REAL    NOT NULL CHECK (genome_size_mb > 0)
);

CREATE TABLE assemblies (
    assembly_id     INTEGER PRIMARY KEY,
    species_id      INTEGER NOT NULL REFERENCES species (species_id),
    name            TEXT    NOT NULL UNIQUE,
    release_year    INTEGER NOT NULL CHECK (release_year BETWEEN 1990 AND 2100),
    technology      TEXT    NOT NULL,             -- e.g. 'Illumina', 'PacBio HiFi', 'ONT'
    contig_n50_kb   REAL    NOT NULL CHECK (contig_n50_kb > 0),
    busco_complete  REAL    NOT NULL CHECK (busco_complete BETWEEN 0 AND 100)  -- % complete BUSCOs
);

CREATE TABLE chromosomes (
    chrom_id        INTEGER PRIMARY KEY,
    assembly_id     INTEGER NOT NULL REFERENCES assemblies (assembly_id),
    name            TEXT    NOT NULL,
    length_bp       INTEGER NOT NULL CHECK (length_bp > 0),
    UNIQUE (assembly_id, name)
);

CREATE TABLE genes (
    gene_id         INTEGER PRIMARY KEY,
    chrom_id        INTEGER NOT NULL REFERENCES chromosomes (chrom_id),
    symbol          TEXT    NOT NULL,
    start_bp        INTEGER NOT NULL CHECK (start_bp >= 0),
    end_bp          INTEGER NOT NULL,
    strand          TEXT    NOT NULL CHECK (strand IN ('+', '-')),
    biotype         TEXT    NOT NULL DEFAULT 'protein_coding',
    disease         TEXT,                          -- associated disease, if any
    CHECK (end_bp > start_bp)
);

-- TE classification is a tree (Wicker et al. 2007):
-- Class I (retrotransposons) > LTR > Copia, Class II (DNA transposons) > TIR > hAT, ...
-- Stored as an adjacency list and walked with a recursive CTE (queries/05).
CREATE TABLE te_classes (
    class_id        INTEGER PRIMARY KEY,
    name            TEXT    NOT NULL UNIQUE,
    parent_id       INTEGER REFERENCES te_classes (class_id),
    rank            TEXT    NOT NULL CHECK (rank IN ('class', 'order', 'superfamily'))
);

CREATE TABLE te_families (
    family_id        INTEGER PRIMARY KEY,
    name             TEXT    NOT NULL,
    class_id         INTEGER NOT NULL REFERENCES te_classes (class_id),  -- a superfamily
    species_id       INTEGER NOT NULL REFERENCES species (species_id),
    consensus_length INTEGER NOT NULL CHECK (consensus_length > 0),
    is_active        INTEGER NOT NULL DEFAULT 0 CHECK (is_active IN (0, 1)),  -- still mobile today
    UNIQUE (species_id, name)
);

-- TE copies annotated on a reference assembly
CREATE TABLE te_insertions (
    insertion_id    INTEGER PRIMARY KEY,
    family_id       INTEGER NOT NULL REFERENCES te_families (family_id),
    chrom_id        INTEGER NOT NULL REFERENCES chromosomes (chrom_id),
    start_bp        INTEGER NOT NULL CHECK (start_bp >= 0),
    end_bp          INTEGER NOT NULL,
    strand          TEXT    NOT NULL CHECK (strand IN ('+', '-')),
    identity        REAL    NOT NULL CHECK (identity BETWEEN 0 AND 1),  -- to the family consensus
    is_polymorphic  INTEGER NOT NULL DEFAULT 0 CHECK (is_polymorphic IN (0, 1)),
    CHECK (end_bp > start_bp)
);

------------------------------------------------------------------------------
-- Biobank: individuals, their samples, sequencing, and genotype calls
------------------------------------------------------------------------------

CREATE TABLE individuals (
    individual_id   INTEGER PRIMARY KEY,
    species_id      INTEGER NOT NULL REFERENCES species (species_id),
    external_code   TEXT    NOT NULL UNIQUE,       -- pseudonymised ID, never a name
    population      TEXT    NOT NULL,              -- ancestry group or plant accession origin
    sex             TEXT    CHECK (sex IN ('F', 'M') OR sex IS NULL),
    birth_year      INTEGER,
    consent_date    TEXT                           -- ISO date; NULL for plants
);

CREATE TABLE phenotypes (
    phenotype_id    INTEGER PRIMARY KEY,
    term_id         TEXT    NOT NULL UNIQUE,       -- HPO term for humans, TO term for plants
    name            TEXT    NOT NULL,
    category        TEXT    NOT NULL
);

CREATE TABLE individual_phenotypes (
    individual_id   INTEGER NOT NULL REFERENCES individuals (individual_id),
    phenotype_id    INTEGER NOT NULL REFERENCES phenotypes (phenotype_id),
    observed_on     TEXT    NOT NULL,
    PRIMARY KEY (individual_id, phenotype_id)
);

CREATE TABLE samples (
    sample_id       INTEGER PRIMARY KEY,
    individual_id   INTEGER NOT NULL REFERENCES individuals (individual_id),
    tissue          TEXT    NOT NULL,
    collected_on    TEXT    NOT NULL,
    freezer_box     TEXT                            -- physical location in the biobank
);

CREATE TABLE sequencing_runs (
    run_id          INTEGER PRIMARY KEY,
    sample_id       INTEGER NOT NULL REFERENCES samples (sample_id),
    platform        TEXT    NOT NULL CHECK (platform IN ('Illumina NovaSeq', 'PacBio Revio', 'ONT PromethION')),
    mean_coverage   REAL    NOT NULL CHECK (mean_coverage > 0),
    run_date        TEXT    NOT NULL,
    passed_qc       INTEGER NOT NULL CHECK (passed_qc IN (0, 1))
);

-- Genotype of a polymorphic TE insertion in one sequencing run
CREATE TABLE insertion_calls (
    run_id           INTEGER NOT NULL REFERENCES sequencing_runs (run_id),
    insertion_id     INTEGER NOT NULL REFERENCES te_insertions (insertion_id),
    genotype         TEXT    NOT NULL CHECK (genotype IN ('0/1', '1/1')),
    supporting_reads INTEGER NOT NULL CHECK (supporting_reads >= 0),
    PRIMARY KEY (run_id, insertion_id)
);

------------------------------------------------------------------------------
-- Integrity: coordinates must lie on the chromosome
------------------------------------------------------------------------------

CREATE TRIGGER te_insertions_within_chromosome
BEFORE INSERT ON te_insertions
WHEN NEW.end_bp > (SELECT length_bp FROM chromosomes WHERE chrom_id = NEW.chrom_id)
BEGIN
    SELECT RAISE(ABORT, 'TE insertion extends beyond the end of its chromosome');
END;

CREATE TRIGGER genes_within_chromosome
BEFORE INSERT ON genes
WHEN NEW.end_bp > (SELECT length_bp FROM chromosomes WHERE chrom_id = NEW.chrom_id)
BEGIN
    SELECT RAISE(ABORT, 'Gene extends beyond the end of its chromosome');
END;

-- A call can only be made for an insertion in the same species as the individual
CREATE TRIGGER insertion_calls_same_species
BEFORE INSERT ON insertion_calls
WHEN (
    SELECT i.species_id
    FROM sequencing_runs r
    JOIN samples s ON s.sample_id = r.sample_id
    JOIN individuals i ON i.individual_id = s.individual_id
    WHERE r.run_id = NEW.run_id
) IS NOT (
    SELECT a.species_id
    FROM te_insertions t
    JOIN chromosomes c ON c.chrom_id = t.chrom_id
    JOIN assemblies a ON a.assembly_id = c.assembly_id
    WHERE t.insertion_id = NEW.insertion_id
)
BEGIN
    SELECT RAISE(ABORT, 'Individual and TE insertion belong to different species');
END;

------------------------------------------------------------------------------
-- Indexes for the joins and range lookups used most
------------------------------------------------------------------------------

CREATE INDEX idx_te_insertions_chrom_pos ON te_insertions (chrom_id, start_bp, end_bp);
CREATE INDEX idx_te_insertions_family    ON te_insertions (family_id);
CREATE INDEX idx_genes_chrom_pos         ON genes (chrom_id, start_bp, end_bp);
CREATE INDEX idx_insertion_calls_ins     ON insertion_calls (insertion_id);
CREATE INDEX idx_samples_individual      ON samples (individual_id);
CREATE INDEX idx_runs_sample             ON sequencing_runs (sample_id);

------------------------------------------------------------------------------
-- Views
------------------------------------------------------------------------------

-- One row per TE copy with its family, class path and location
CREATE VIEW v_te_annotation AS
SELECT
    t.insertion_id,
    sp.scientific_name           AS species,
    a.name                       AS assembly,
    c.name                       AS chrom,
    t.start_bp,
    t.end_bp,
    t.end_bp - t.start_bp        AS length_bp,
    t.strand,
    f.name                       AS family,
    sf.name                      AS superfamily,
    ord.name                     AS te_order,
    cls.name                     AS te_class,
    t.identity,
    t.is_polymorphic
FROM te_insertions t
JOIN te_families f  ON f.family_id = t.family_id
JOIN te_classes sf  ON sf.class_id = f.class_id
JOIN te_classes ord ON ord.class_id = sf.parent_id
JOIN te_classes cls ON cls.class_id = ord.parent_id
JOIN chromosomes c  ON c.chrom_id = t.chrom_id
JOIN assemblies a   ON a.assembly_id = c.assembly_id
JOIN species sp     ON sp.species_id = a.species_id;

-- Sequencing runs that can be used for analysis
CREATE VIEW v_good_runs AS
SELECT r.*, s.individual_id
FROM sequencing_runs r
JOIN samples s ON s.sample_id = r.sample_id
WHERE r.passed_qc = 1 AND r.mean_coverage >= 20;
