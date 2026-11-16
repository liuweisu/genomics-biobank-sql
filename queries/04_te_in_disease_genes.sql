-- Question: Which TE copies sit inside a human disease gene, and is the gene disrupted
--           by a young (high identity) element from a family that is still active?
-- Concepts: interval overlap join (a.start < b.end AND b.start < a.end), LEFT JOIN-free filtering
SELECT
    g.symbol,
    g.disease,
    f.name                         AS family,
    t.start_bp - g.start_bp        AS offset_in_gene,
    t.end_bp - t.start_bp          AS te_length,
    t.identity,
    f.is_active,
    t.is_polymorphic
FROM genes g
JOIN te_insertions t ON t.chrom_id = g.chrom_id
                    AND t.start_bp < g.end_bp
                    AND g.start_bp < t.end_bp
JOIN te_families f   ON f.family_id = t.family_id
WHERE g.disease IS NOT NULL
  AND f.is_active = 1
  AND t.identity >= 0.97
ORDER BY t.is_polymorphic DESC, t.identity DESC;
