-- Question: Does the data violate any rule the schema cannot express on its own?
--           Each row is one check; every count should be 0.
-- Concepts: UNION ALL of checks, correlated subqueries, self-join for overlaps
SELECT 'insertion calls from runs that failed QC' AS check_name,
       COUNT(*) AS violations
FROM insertion_calls c JOIN sequencing_runs r ON r.run_id = c.run_id
WHERE r.passed_qc = 0
UNION ALL
SELECT 'calls for TE copies not marked polymorphic',
       COUNT(*)
FROM insertion_calls c JOIN te_insertions t ON t.insertion_id = c.insertion_id
WHERE t.is_polymorphic = 0
UNION ALL
SELECT 'samples collected before the donor gave consent',
       COUNT(*)
FROM samples s JOIN individuals i ON i.individual_id = s.individual_id
WHERE i.consent_date IS NOT NULL AND s.collected_on < i.consent_date
UNION ALL
SELECT 'human individuals without consent date',
       COUNT(*)
FROM individuals i JOIN species sp ON sp.species_id = i.species_id
WHERE sp.kingdom = 'Animalia' AND i.consent_date IS NULL
UNION ALL
SELECT 'genes with duplicate symbols on one assembly',
       COUNT(*)
FROM (SELECT c.assembly_id, g.symbol FROM genes g JOIN chromosomes c ON c.chrom_id = g.chrom_id
      GROUP BY c.assembly_id, g.symbol HAVING COUNT(*) > 1);
