-- Question: Which TE families are likely still mobile? Rank families by the share of
--           near-identical copies (>= 98% identity to the consensus), a sign of recent activity.
-- Concepts: aggregate FILTER-style CASE, NTILE, comparing a computed signal with a stored flag
SELECT
    sp.common_name                                                   AS species,
    f.name                                                           AS family,
    COUNT(*)                                                         AS copies,
    ROUND(100.0 * SUM(t.identity >= 0.98) / COUNT(*), 1)             AS pct_young_copies,
    ROUND(AVG(t.identity), 3)                                        AS mean_identity,
    NTILE(4) OVER (ORDER BY 1.0 * SUM(t.identity >= 0.98) / COUNT(*) DESC) AS activity_quartile,
    f.is_active                                                      AS annotated_active
FROM te_insertions t
JOIN te_families f ON f.family_id = t.family_id
JOIN species sp    ON sp.species_id = f.species_id
GROUP BY f.family_id
HAVING COUNT(*) >= 10
ORDER BY pct_young_copies DESC;
