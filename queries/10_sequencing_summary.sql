-- Question: Per platform and year, how many runs were done, what fraction passed QC,
--           and what is the running total of sequenced individuals?
-- Concepts: date functions (strftime), COUNT DISTINCT, running total with SUM() OVER (ORDER BY ...)
WITH yearly AS (
    SELECT
        strftime('%Y', r.run_date)        AS year,
        r.platform,
        COUNT(*)                          AS runs,
        ROUND(AVG(r.passed_qc) * 100, 1)  AS pct_passed,
        ROUND(AVG(r.mean_coverage), 1)    AS mean_cov,
        COUNT(DISTINCT s.individual_id)   AS individuals
    FROM sequencing_runs r
    JOIN samples s ON s.sample_id = r.sample_id
    GROUP BY year, r.platform
)
SELECT
    *,
    SUM(runs) OVER (PARTITION BY platform ORDER BY year) AS cumulative_runs
FROM yearly
ORDER BY platform, year;
