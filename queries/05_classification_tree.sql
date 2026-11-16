-- Question: Show the full TE classification tree with the number of copies under every node,
--           e.g. how many copies fall under "Class I" in total.
-- Concepts: recursive CTE (walking an adjacency list), aggregating up a hierarchy
WITH RECURSIVE
tree (class_id, name, rank, depth, path) AS (
    SELECT class_id, name, rank, 0, name
    FROM te_classes
    WHERE parent_id IS NULL
    UNION ALL
    SELECT c.class_id, c.name, c.rank, t.depth + 1, t.path || ' > ' || c.name
    FROM te_classes c
    JOIN tree t ON c.parent_id = t.class_id
),
-- every (ancestor, superfamily) pair, so copies can be rolled up to each level
ancestors (ancestor_id, class_id) AS (
    SELECT class_id, class_id FROM te_classes
    UNION ALL
    SELECT a.ancestor_id, c.class_id
    FROM te_classes c
    JOIN ancestors a ON c.parent_id = a.class_id
),
copies AS (
    SELECT f.class_id, COUNT(*) AS n
    FROM te_insertions t
    JOIN te_families f ON f.family_id = t.family_id
    GROUP BY f.class_id
)
SELECT
    substr('                ', 1, 4 * tree.depth) || tree.name AS te_class,
    tree.rank,
    COALESCE(SUM(copies.n), 0)                                AS copies
FROM tree
JOIN ancestors a    ON a.ancestor_id = tree.class_id
LEFT JOIN copies    ON copies.class_id = a.class_id
GROUP BY tree.class_id
ORDER BY tree.path;
