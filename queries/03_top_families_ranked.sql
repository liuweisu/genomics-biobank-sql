-- Question: Which are the three most abundant TE families in each species,
--           and what share of the species' TE copies do they make up?
-- Concepts: window functions (RANK, SUM OVER PARTITION), filtering on a window result
WITH counts AS (
    SELECT species, family, superfamily, COUNT(*) AS copies
    FROM v_te_annotation
    GROUP BY species, family, superfamily
),
ranked AS (
    SELECT
        *,
        RANK() OVER (PARTITION BY species ORDER BY copies DESC)        AS rnk,
        ROUND(100.0 * copies / SUM(copies) OVER (PARTITION BY species), 1) AS pct_of_species
    FROM counts
)
SELECT species, rnk, family, superfamily, copies, pct_of_species
FROM ranked
WHERE rnk <= 3
ORDER BY species, rnk;
