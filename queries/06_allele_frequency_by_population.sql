-- Question: For polymorphic human TE insertions, what is the allele frequency in each
--           population, and which insertions differ most between populations?
-- Concepts: CTEs, CASE inside SUM, CROSS JOIN for the denominator, HAVING, MAX-MIN spread
WITH genotyped AS (            -- one usable run per person: their best-coverage passing run
    SELECT individual_id, run_id
    FROM (
        SELECT r.run_id, r.individual_id,
               ROW_NUMBER() OVER (PARTITION BY r.individual_id ORDER BY r.mean_coverage DESC) AS rn
        FROM v_good_runs r
    )
    WHERE rn = 1
),
people AS (
    SELECT i.population, g.run_id
    FROM genotyped g
    JOIN individuals i ON i.individual_id = g.individual_id
    JOIN species s     ON s.species_id = i.species_id
    WHERE s.scientific_name = 'Homo sapiens'
),
pop_size AS (
    SELECT population, COUNT(*) AS n FROM people GROUP BY population
),
af AS (
    SELECT
        c.insertion_id,
        p.population,
        SUM(CASE c.genotype WHEN '1/1' THEN 2 ELSE 1 END) * 1.0 / (2 * ps.n) AS allele_freq
    FROM insertion_calls c
    JOIN people p    ON p.run_id = c.run_id
    JOIN pop_size ps ON ps.population = p.population
    GROUP BY c.insertion_id, p.population
)
SELECT
    a.insertion_id,
    v.family,
    v.chrom || ':' || v.start_bp                            AS position,
    ROUND(MAX(CASE WHEN population = 'AFR' THEN allele_freq END), 3) AS af_afr,
    ROUND(MAX(CASE WHEN population = 'EUR' THEN allele_freq END), 3) AS af_eur,
    ROUND(MAX(CASE WHEN population = 'EAS' THEN allele_freq END), 3) AS af_eas,
    ROUND(MAX(CASE WHEN population = 'SAS' THEN allele_freq END), 3) AS af_sas,
    ROUND(MAX(CASE WHEN population = 'AMR' THEN allele_freq END), 3) AS af_amr,
    ROUND(MAX(allele_freq) - MIN(allele_freq), 3)           AS spread
FROM af a
JOIN v_te_annotation v ON v.insertion_id = a.insertion_id
GROUP BY a.insertion_id
HAVING COUNT(*) = 5            -- seen in every population
ORDER BY spread DESC
LIMIT 15;
