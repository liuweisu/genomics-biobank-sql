-- Question: How much of each annotated genome is made of transposable elements,
--           split by TE order (LTR, LINE, SINE, TIR, ...)?
-- Concepts: multi-table JOIN through a view, GROUP BY, conditional aggregation, ROUND
SELECT
    species,
    COUNT(*)                                                          AS te_copies,
    ROUND(SUM(length_bp) / 1e6, 2)                                    AS te_mb,
    ROUND(100.0 * SUM(CASE WHEN te_order = 'LTR'  THEN length_bp END) / SUM(length_bp), 1) AS pct_ltr,
    ROUND(100.0 * SUM(CASE WHEN te_order = 'LINE' THEN length_bp END) / SUM(length_bp), 1) AS pct_line,
    ROUND(100.0 * SUM(CASE WHEN te_order = 'SINE' THEN length_bp END) / SUM(length_bp), 1) AS pct_sine,
    ROUND(100.0 * SUM(CASE WHEN te_class = 'Class II' THEN length_bp END) / SUM(length_bp), 1) AS pct_dna_te
FROM v_te_annotation
GROUP BY species
ORDER BY te_mb DESC;
