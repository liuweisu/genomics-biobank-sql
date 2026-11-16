-- Question: What fraction of each chromosome (on the newest assembly) is covered by TEs?
-- Concepts: CTE, JOIN on aggregated subquery, ratio of two aggregates
WITH te_per_chrom AS (
    SELECT chrom_id, COUNT(*) AS copies, SUM(end_bp - start_bp) AS te_bp
    FROM te_insertions
    GROUP BY chrom_id
)
SELECT
    sp.scientific_name             AS species,
    a.name                         AS assembly,
    c.name                         AS chrom,
    c.length_bp,
    t.copies,
    ROUND(100.0 * t.te_bp / c.length_bp, 1) AS pct_te   -- overlapping copies can push this above the true value
FROM te_per_chrom t
JOIN chromosomes c ON c.chrom_id = t.chrom_id
JOIN assemblies a  ON a.assembly_id = c.assembly_id
JOIN species sp    ON sp.species_id = a.species_id
ORDER BY pct_te DESC;
