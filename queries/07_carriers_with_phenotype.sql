-- Question: For every polymorphic TE insertion inside NF1 or F8, are carriers more often
--           affected by the phenotype that gene is known for? (a small association scan)
-- Concepts: EXISTS subqueries, CROSS JOIN, a 2x2 contingency table, odds ratio computed in SQL
WITH gene_insertions AS (
    SELECT g.symbol, t.insertion_id, f.name AS family,
           CASE g.symbol WHEN 'NF1' THEN 'Cafe-au-lait spot'
                         WHEN 'F8'  THEN 'Abnormal bleeding' END AS expected_phenotype
    FROM genes g
    JOIN te_insertions t ON t.chrom_id = g.chrom_id AND t.start_bp < g.end_bp AND g.start_bp < t.end_bp
    JOIN te_families f   ON f.family_id = t.family_id
    WHERE g.symbol IN ('NF1', 'F8') AND t.is_polymorphic = 1
),
humans AS (                    -- people with at least one usable sequencing run
    SELECT DISTINCT r.individual_id
    FROM v_good_runs r
    JOIN individuals i ON i.individual_id = r.individual_id
    JOIN species s     ON s.species_id = i.species_id AND s.scientific_name = 'Homo sapiens'
),
status AS (
    SELECT
        gi.symbol, gi.insertion_id, gi.family, gi.expected_phenotype,
        EXISTS (SELECT 1 FROM insertion_calls c JOIN v_good_runs r ON r.run_id = c.run_id
                WHERE c.insertion_id = gi.insertion_id AND r.individual_id = h.individual_id) AS carrier,
        EXISTS (SELECT 1 FROM individual_phenotypes ip JOIN phenotypes p ON p.phenotype_id = ip.phenotype_id
                WHERE ip.individual_id = h.individual_id AND p.name = gi.expected_phenotype)  AS affected
    FROM gene_insertions gi
    CROSS JOIN humans h
)
SELECT
    symbol,
    insertion_id,
    family,
    expected_phenotype,
    SUM(carrier AND affected)         AS carrier_affected,
    SUM(carrier AND NOT affected)     AS carrier_unaffected,
    SUM(NOT carrier AND affected)     AS noncarrier_affected,
    SUM(NOT carrier AND NOT affected) AS noncarrier_unaffected,
    -- Haldane-corrected odds ratio (+0.5 in every cell avoids division by zero)
    ROUND(  (SUM(carrier AND affected) + 0.5) * (SUM(NOT carrier AND NOT affected) + 0.5)
          / ((SUM(carrier AND NOT affected) + 0.5) * (SUM(NOT carrier AND affected) + 0.5)), 1) AS odds_ratio
FROM status
GROUP BY symbol, insertion_id
HAVING SUM(carrier) > 0          -- an odds ratio needs carriers
ORDER BY odds_ratio DESC;
