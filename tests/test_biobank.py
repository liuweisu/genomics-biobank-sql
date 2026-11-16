import sqlite3

import pytest

from biobank import db, generate


@pytest.fixture(scope="session")
def database(tmp_path_factory):
    return generate.build(tmp_path_factory.mktemp("db") / "biobank.db")


@pytest.fixture
def con(database):
    with db.connect(database) as c:
        yield c


@pytest.fixture
def rw(database, tmp_path):
    copy = tmp_path / "rw.db"
    copy.write_bytes(database.read_bytes())
    with db.connect(copy, readonly=False) as c:
        yield c


def test_build_is_reproducible(tmp_path):
    a = generate.build(tmp_path / "a.db", seed=1)
    b = generate.build(tmp_path / "b.db", seed=1)
    q = "SELECT COUNT(*), SUM(start_bp) FROM te_insertions"
    assert sqlite3.connect(a).execute(q).fetchone() == sqlite3.connect(b).execute(q).fetchone()


@pytest.mark.parametrize("name", list(db.list_queries()))
def test_every_query_runs_and_returns_rows(con, name):
    columns, rows = db.run_named(con, name)
    assert columns and rows


def test_foreign_keys_enforced(rw):
    with pytest.raises(sqlite3.IntegrityError):
        rw.execute("INSERT INTO samples (individual_id, tissue, collected_on) VALUES (999999, 'blood', '2024-01-01')")


def test_check_constraint(rw):
    with pytest.raises(sqlite3.IntegrityError):
        rw.execute("INSERT INTO te_insertions (family_id, chrom_id, start_bp, end_bp, strand, identity)"
                   " VALUES (1, 1, 500, 100, '+', 0.9)")


def test_trigger_rejects_insertion_beyond_chromosome(rw):
    length = rw.execute("SELECT length_bp FROM chromosomes WHERE chrom_id = 1").fetchone()[0]
    with pytest.raises(sqlite3.IntegrityError, match="beyond the end"):
        rw.execute("INSERT INTO te_insertions (family_id, chrom_id, start_bp, end_bp, strand, identity)"
                   " VALUES (1, 1, ?, ?, '+', 0.9)", (length - 10, length + 10))


def test_trigger_rejects_cross_species_call(rw):
    human_run = rw.execute("""SELECT r.run_id FROM sequencing_runs r JOIN samples s USING (sample_id)
                              JOIN individuals i USING (individual_id) JOIN species sp USING (species_id)
                              WHERE sp.common_name = 'human' LIMIT 1""").fetchone()[0]
    maize_ins = rw.execute("""SELECT t.insertion_id FROM te_insertions t JOIN te_families f USING (family_id)
                              JOIN species sp USING (species_id) WHERE sp.common_name = 'maize' LIMIT 1""").fetchone()[0]
    with pytest.raises(sqlite3.IntegrityError, match="different species"):
        rw.execute("INSERT INTO insertion_calls VALUES (?, ?, '0/1', 10)", (human_run, maize_ins))


def test_readonly_connection_cannot_write(con):
    with pytest.raises(sqlite3.OperationalError):
        con.execute("DELETE FROM species")


def test_planted_association_is_found(con):
    cols, rows = db.run_named(con, "07")
    top = dict(zip(cols, rows[0]))
    assert top["symbol"] in {"NF1", "F8"} and top["odds_ratio"] > 50


def test_classification_rollup_is_consistent(con):
    cols, rows = db.run_named(con, "05")
    counts = {r[0].strip(): r[2] for r in rows}
    total = con.execute("SELECT COUNT(*) FROM te_insertions").fetchone()[0]
    assert counts["Class I"] + counts["Class II"] == total
    assert counts["LTR"] == counts["Copia"] + counts["Gypsy"] + counts["ERV"]


def test_quality_checks_find_only_the_planted_problem(con):
    _, rows = db.run_named(con, "12")
    problems = {name: n for name, n in rows if n}
    assert set(problems) == {"samples collected before the donor gave consent"}


def test_parameterised_query_is_injection_safe(con):
    assert db.individuals_with_insertion_in_gene(con, "NF1")
    assert db.individuals_with_insertion_in_gene(con, "NF1' OR '1'='1") == []


def test_interval_index_is_used(con):
    plan = " ".join(db.explain(con, "SELECT * FROM te_insertions WHERE chrom_id = 3 AND start_bp < 1000"))
    assert "idx_te_insertions_chrom_pos" in plan
