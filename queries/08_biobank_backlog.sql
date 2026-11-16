-- Question: Which stored samples still need (re-)sequencing: never sequenced, or every
--           run failed QC? Where are they in the freezer?
-- Concepts: LEFT JOIN with aggregate, anti-join, COALESCE, string functions
SELECT
    sp.common_name                                AS species,
    i.external_code,
    s.sample_id,
    s.tissue,
    s.freezer_box,
    COUNT(r.run_id)                               AS runs,
    COALESCE(MAX(r.mean_coverage), 0)             AS best_coverage,
    CASE WHEN COUNT(r.run_id) = 0 THEN 'never sequenced' ELSE 'all runs failed QC' END AS reason
FROM samples s
JOIN individuals i ON i.individual_id = s.individual_id
JOIN species sp    ON sp.species_id = i.species_id
LEFT JOIN sequencing_runs r ON r.sample_id = s.sample_id
GROUP BY s.sample_id
HAVING COALESCE(SUM(r.passed_qc), 0) = 0
ORDER BY species, s.freezer_box;
