-- Question: For each species, how much did the newest assembly improve on the previous one?
-- Concepts: LAG window function, ordering within a partition, percentage change
SELECT
    sp.scientific_name AS species,
    a.name             AS assembly,
    a.release_year,
    a.technology,
    a.contig_n50_kb,
    LAG(a.contig_n50_kb) OVER w                                   AS previous_n50_kb,
    ROUND(a.contig_n50_kb / LAG(a.contig_n50_kb) OVER w, 1)        AS n50_fold_change,
    ROUND(a.busco_complete - LAG(a.busco_complete) OVER w, 1)      AS busco_gain
FROM assemblies a
JOIN species sp ON sp.species_id = a.species_id
WINDOW w AS (PARTITION BY a.species_id ORDER BY a.release_year)
ORDER BY species, a.release_year;
