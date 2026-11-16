"""Fill the schema with a reproducible, synthetic dataset.

Nothing here is real patient or genome data. Species names, TE family names
and gene symbols are real so the queries read naturally, but every
coordinate, assembly statistic, person and genotype is generated. Chromosome
lengths are scaled down so the database stays a few MB.

A few patterns are planted on purpose so the queries have something to find:
* a polymorphic Alu insertion inside NF1, enriched in people with cafe-au-lait spots;
* an L1 insertion inside F8 found in people with abnormal bleeding;
* population-specific allele frequencies for polymorphic TEs;
* some samples that were never sequenced and some runs that failed QC;
* a handful of samples dated before the donor's consent (data-entry errors for query 12 to catch).
"""

from __future__ import annotations

import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

SCHEMA = Path(__file__).resolve().parent.parent / "sql" / "schema.sql"

SPECIES = [
    # name, common, kingdom, genome size (Mb, real order of magnitude), scaled chromosomes (name, Mb)
    ("Homo sapiens", "human", "Animalia", 3100, [("chr1", 6.0), ("chr13", 3.0), ("chr17", 2.5), ("chrX", 4.0)]),
    ("Arabidopsis thaliana", "thale cress", "Plantae", 135, [("Chr1", 3.0), ("Chr2", 2.0), ("Chr3", 2.4)]),
    ("Oryza sativa", "rice", "Plantae", 430, [("chr01", 4.3), ("chr06", 3.1), ("chr11", 2.9)]),
    ("Zea mays", "maize", "Plantae", 2400, [("chr1", 8.0), ("chr5", 6.5), ("chr9", 4.5)]),
    ("Escherichia coli", "E. coli", "Bacteria", 4.6, [("chromosome", 4.6)]),
]

ASSEMBLIES = {
    # species -> list of (name, year, technology, contig N50 kb, BUSCO %)
    "Homo sapiens": [("Hsap_ref_v1", 2013, "Sanger+Illumina", 56_000, 98.9), ("Hsap_t2t_v1", 2022, "PacBio HiFi+ONT", 150_000, 99.2)],
    "Arabidopsis thaliana": [("Atha_ref_v1", 2010, "Sanger", 11_000, 98.6), ("Atha_hifi_v2", 2021, "PacBio HiFi", 22_000, 99.1)],
    "Oryza sativa": [("Osat_ref_v1", 2013, "Sanger+Illumina", 400, 97.3), ("Osat_hifi_v2", 2023, "PacBio HiFi", 17_500, 98.8)],
    "Zea mays": [("Zmay_ref_v4", 2017, "PacBio CLR", 1_200, 95.4), ("Zmay_ref_v5", 2020, "PacBio CLR+BioNano", 2_800, 96.9)],
    "Escherichia coli": [("Ecol_k12_v2", 2013, "Sanger", 4_600, 99.8)],
}

TE_TREE = [
    # (name, parent, rank)
    ("Class I", None, "class"), ("Class II", None, "class"),
    ("LTR", "Class I", "order"), ("LINE", "Class I", "order"), ("SINE", "Class I", "order"),
    ("TIR", "Class II", "order"), ("Helitron", "Class II", "order"), ("IS element", "Class II", "order"),
    ("Copia", "LTR", "superfamily"), ("Gypsy", "LTR", "superfamily"), ("ERV", "LTR", "superfamily"),
    ("L1", "LINE", "superfamily"), ("Alu", "SINE", "superfamily"), ("tRNA-derived", "SINE", "superfamily"),
    ("hAT", "TIR", "superfamily"), ("Mutator", "TIR", "superfamily"), ("Tc1-Mariner", "TIR", "superfamily"),
    ("PIF-Harbinger", "TIR", "superfamily"), ("CACTA", "TIR", "superfamily"),
    ("Helitron-1", "Helitron", "superfamily"), ("IS3", "IS element", "superfamily"), ("IS5", "IS element", "superfamily"),
]

FAMILIES = {
    # species -> (family, superfamily, consensus length, active, relative abundance)
    "Homo sapiens": [
        ("AluY", "Alu", 311, 1, 30), ("AluSx", "Alu", 312, 0, 40), ("L1HS", "L1", 6_064, 1, 4),
        ("L1PA2", "L1", 6_150, 0, 10), ("HERVK", "ERV", 9_472, 0, 2), ("MER5A", "hAT", 189, 0, 8),
        ("MIR", "tRNA-derived", 262, 0, 25),
    ],
    "Arabidopsis thaliana": [
        ("ATCOPIA78", "Copia", 5_100, 0, 6), ("ATHILA", "Gypsy", 10_500, 0, 20), ("ATENSPM3", "CACTA", 8_300, 0, 5),
        ("HELITRONY3", "Helitron-1", 1_500, 0, 25), ("VANDAL21", "Mutator", 6_800, 1, 4), ("SIMPLEHAT2", "hAT", 3_000, 0, 6),
    ],
    "Oryza sativa": [
        ("RIRE2", "Gypsy", 11_400, 0, 25), ("Tos17", "Copia", 4_114, 1, 3), ("mPing", "PIF-Harbinger", 430, 1, 12),
        ("Stowaway1", "Tc1-Mariner", 250, 0, 30), ("Dasheng", "Gypsy", 5_600, 0, 8), ("MULE-1", "Mutator", 3_900, 0, 6),
    ],
    "Zea mays": [
        ("Huck", "Gypsy", 13_000, 0, 30), ("Ji", "Copia", 9_800, 0, 25), ("Opie", "Copia", 9_200, 0, 25),
        ("Ac", "hAT", 4_565, 1, 2), ("MuDR", "Mutator", 4_942, 1, 3), ("Helitron-Zm1", "Helitron-1", 6_000, 0, 10),
    ],
    "Escherichia coli": [("IS1", "IS3", 768, 1, 4), ("IS3", "IS3", 1_258, 1, 3), ("IS5", "IS5", 1_195, 1, 5)],
}

# copies chosen so TE content is roughly realistic: maize ~75%, human ~45%, rice ~35%, Arabidopsis ~20%
N_INSERTIONS = {"Homo sapiens": 6_000, "Arabidopsis thaliana": 400, "Oryza sativa": 1_100, "Zea mays": 2_000, "Escherichia coli": 18}

HUMAN_GENES = [
    # symbol, chrom, start, length, disease
    ("NF1", "chr17", 1_200_000, 280_000, "Neurofibromatosis type 1"),
    ("BRCA2", "chr13", 900_000, 84_000, "Hereditary breast and ovarian cancer"),
    ("F8", "chrX", 2_100_000, 187_000, "Haemophilia A"),
    ("DMD", "chrX", 300_000, 1_100_000, "Duchenne muscular dystrophy"),
    ("APC", "chr1", 4_200_000, 139_000, "Familial adenomatous polyposis"),
    ("CFTR", "chr1", 2_000_000, 189_000, "Cystic fibrosis"),
]

PHENOTYPES = [
    ("HP:0000957", "Cafe-au-lait spot", "skin"),
    ("HP:0001892", "Abnormal bleeding", "blood"),
    ("HP:0003002", "Breast carcinoma", "neoplasm"),
    ("HP:0003560", "Muscular dystrophy", "musculoskeletal"),
    ("HP:0001250", "Seizure", "nervous system"),
    ("HP:0000819", "Diabetes mellitus", "metabolism"),
    ("TO:0000207", "Plant height", "growth"),
    ("TO:0002616", "Flowering time", "development"),
]

POPULATIONS = {
    "Homo sapiens": ["AFR", "EUR", "EAS", "SAS", "AMR"],
    "Arabidopsis thaliana": ["Iberia", "Central Europe", "Scandinavia", "Asia"],
    "Oryza sativa": ["japonica", "indica", "aus"],
    "Zea mays": ["temperate", "tropical", "landrace"],
    "Escherichia coli": ["clinical", "environmental"],
}
N_INDIVIDUALS = {"Homo sapiens": 500, "Arabidopsis thaliana": 160, "Oryza sativa": 120, "Zea mays": 120, "Escherichia coli": 40}


def _date(rng: random.Random, start: date, span_days: int) -> str:
    return (start + timedelta(days=rng.randrange(span_days))).isoformat()


def build(path: str | Path, seed: int = 42) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    rng = random.Random(seed)
    con = sqlite3.connect(path)
    con.executescript(SCHEMA.read_text())
    cur = con.cursor()

    # --- TE classification tree -------------------------------------------
    class_ids: dict[str, int] = {}
    for name, parent, rank in TE_TREE:
        cur.execute("INSERT INTO te_classes (name, parent_id, rank) VALUES (?, ?, ?)",
                    (name, class_ids.get(parent), rank))
        class_ids[name] = cur.lastrowid

    for term, name, category in PHENOTYPES:
        cur.execute("INSERT INTO phenotypes (term_id, name, category) VALUES (?, ?, ?)", (term, name, category))
    pheno_ids = {name: pid for pid, name in cur.execute("SELECT phenotype_id, name FROM phenotypes").fetchall()}

    planted: dict[str, int] = {}
    for sci, common, kingdom, size, chroms in SPECIES:
        cur.execute("INSERT INTO species (scientific_name, common_name, kingdom, genome_size_mb) VALUES (?, ?, ?, ?)",
                    (sci, common, kingdom, size))
        sp_id = cur.lastrowid

        latest_chroms: dict[str, tuple[int, int]] = {}
        for name, year, tech, n50, busco in ASSEMBLIES[sci]:
            cur.execute(
                "INSERT INTO assemblies (species_id, name, release_year, technology, contig_n50_kb, busco_complete)"
                " VALUES (?, ?, ?, ?, ?, ?)", (sp_id, name, year, tech, n50, busco))
            asm_id = cur.lastrowid
            for cname, mb in chroms:
                length = int(mb * 1_000_000)
                cur.execute("INSERT INTO chromosomes (assembly_id, name, length_bp) VALUES (?, ?, ?)",
                            (asm_id, cname, length))
                latest_chroms[cname] = (cur.lastrowid, length)  # annotations go on the newest assembly

        # genes
        if sci == "Homo sapiens":
            for sym, cname, start, length, disease in HUMAN_GENES:
                cid, _ = latest_chroms[cname]
                cur.execute("INSERT INTO genes (chrom_id, symbol, start_bp, end_bp, strand, disease) VALUES (?, ?, ?, ?, ?, ?)",
                            (cid, sym, start, start + length, rng.choice("+-"), disease))
        n_genes = {"Homo sapiens": 120, "Escherichia coli": 300}.get(sci, 150)
        for i in range(n_genes):
            cname = rng.choice(list(latest_chroms))
            cid, clen = latest_chroms[cname]
            length = rng.randint(800, 1_500) if kingdom == "Bacteria" else rng.randint(1_500, 60_000)
            start = rng.randrange(0, clen - length)
            prefix = {"Homo sapiens": "GENE", "Arabidopsis thaliana": "AT", "Oryza sativa": "Os",
                      "Zea mays": "Zm", "Escherichia coli": "b"}[sci]
            cur.execute("INSERT INTO genes (chrom_id, symbol, start_bp, end_bp, strand, biotype) VALUES (?, ?, ?, ?, ?, ?)",
                        (cid, f"{prefix}{i + 1:04d}", start, start + length, rng.choice("+-"),
                         rng.choices(["protein_coding", "lncRNA", "pseudogene"], [85, 10, 5])[0]))

        # TE families and copies
        fams = []
        for fname, superfam, clen_, active, weight in FAMILIES[sci]:
            cur.execute("INSERT INTO te_families (name, class_id, species_id, consensus_length, is_active) VALUES (?, ?, ?, ?, ?)",
                        (fname, class_ids[superfam], sp_id, clen_, active))
            fams.append((cur.lastrowid, fname, clen_, active, weight))
        weights = [f[4] for f in fams]
        for _ in range(N_INSERTIONS[sci]):
            fid, fname, clen_, active, _w = rng.choices(fams, weights)[0]
            cname = rng.choices(list(latest_chroms), [v[1] for v in latest_chroms.values()])[0]
            cid, chrom_len = latest_chroms[cname]
            length = int(clen_ * rng.uniform(0.2, 1.0)) if rng.random() < 0.6 else clen_  # many copies are truncated
            start = rng.randrange(0, chrom_len - length)
            identity = rng.uniform(0.93, 0.999) if active else rng.uniform(0.70, 0.95)
            polymorphic = int(active and rng.random() < 0.5) or int(rng.random() < 0.03)
            cur.execute("INSERT INTO te_insertions (family_id, chrom_id, start_bp, end_bp, strand, identity, is_polymorphic)"
                        " VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (fid, cid, start, start + length, rng.choice("+-"), round(identity, 4), polymorphic))

        if sci == "Homo sapiens":
            fam = {f[1]: f[0] for f in fams}
            for gene, family, offset, length in (("NF1", "AluY", 150_000, 311), ("F8", "L1HS", 90_000, 6_064)):
                _, cname, gene_start, _, _ = next(g for g in HUMAN_GENES if g[0] == gene)
                cid, _ = latest_chroms[cname]
                cur.execute("INSERT INTO te_insertions (family_id, chrom_id, start_bp, end_bp, strand, identity, is_polymorphic)"
                            " VALUES (?, ?, ?, ?, '+', 0.995, 1)",
                            (fam[family], cid, gene_start + offset, gene_start + offset + length))
                planted[gene] = cur.lastrowid

        # individuals, samples, runs
        polymorphic_ids = [r[0] for r in cur.execute(
            "SELECT t.insertion_id FROM te_insertions t JOIN chromosomes c USING (chrom_id) "
            "JOIN assemblies a USING (assembly_id) WHERE a.species_id = ? AND t.is_polymorphic = 1", (sp_id,))]
        pops = POPULATIONS[sci]
        # each insertion gets a base allele frequency, shifted per population
        base_af = {ins: rng.betavariate(0.6, 3) for ins in polymorphic_ids}
        pop_shift = {(ins, p): rng.uniform(0.3, 1.7) for ins in polymorphic_ids for p in pops}

        for n in range(N_INDIVIDUALS[sci]):
            pop = rng.choice(pops)
            is_human = sci == "Homo sapiens"
            code = f"{common[:2].upper().replace('.', '')}-{n + 1:05d}"
            cur.execute("INSERT INTO individuals (species_id, external_code, population, sex, birth_year, consent_date)"
                        " VALUES (?, ?, ?, ?, ?, ?)",
                        (sp_id, code, pop, rng.choice("FM") if is_human else None,
                         rng.randint(1940, 2015) if is_human else None,
                         _date(rng, date(2018, 1, 1), 1500) if is_human else None))
            ind_id = cur.lastrowid

            carries_nf1 = is_human and rng.random() < 0.05
            carries_f8 = is_human and rng.random() < 0.03
            if is_human:
                if carries_nf1 and rng.random() < 0.85:
                    cur.execute("INSERT INTO individual_phenotypes VALUES (?, ?, ?)",
                                (ind_id, pheno_ids["Cafe-au-lait spot"], _date(rng, date(2019, 1, 1), 1200)))
                if carries_f8 and rng.random() < 0.9:
                    cur.execute("INSERT INTO individual_phenotypes VALUES (?, ?, ?)",
                                (ind_id, pheno_ids["Abnormal bleeding"], _date(rng, date(2019, 1, 1), 1200)))
                for ph, p in (("Seizure", 0.04), ("Diabetes mellitus", 0.08), ("Breast carcinoma", 0.03),
                              ("Cafe-au-lait spot", 0.01)):
                    if rng.random() < p:
                        cur.execute("INSERT OR IGNORE INTO individual_phenotypes VALUES (?, ?, ?)",
                                    (ind_id, pheno_ids[ph], _date(rng, date(2019, 1, 1), 1200)))
            elif kingdom == "Plantae":
                for ph in ("Plant height", "Flowering time"):
                    if rng.random() < 0.5:
                        cur.execute("INSERT INTO individual_phenotypes VALUES (?, ?, ?)",
                                    (ind_id, pheno_ids[ph], _date(rng, date(2020, 4, 1), 200)))

            tissues = {"Animalia": ["blood", "saliva", "skin biopsy"], "Plantae": ["leaf", "root", "seedling"],
                       "Bacteria": ["culture"]}[kingdom]
            consent = cur.execute("SELECT consent_date FROM individuals WHERE individual_id = ?", (ind_id,)).fetchone()[0]
            for _s in range(rng.choices([1, 2], [75, 25])[0]):
                if consent:
                    # samples are taken after consent, except a few planted data-entry errors
                    offset = rng.randrange(1, 400) * (-1 if rng.random() < 0.01 else 1)
                    collected = (date.fromisoformat(consent) + timedelta(days=offset)).isoformat()
                else:
                    collected = _date(rng, date(2019, 1, 1), 1500)
                cur.execute("INSERT INTO samples (individual_id, tissue, collected_on, freezer_box) VALUES (?, ?, ?, ?)",
                            (ind_id, rng.choice(tissues), collected,
                             f"F{rng.randint(1, 6)}-R{rng.randint(1, 20):02d}-B{rng.randint(1, 50):02d}"))
                sample_id = cur.lastrowid
                n_runs = rng.choices([0, 1, 2], [8, 80, 12])[0]  # some samples are still waiting
                for _r in range(n_runs):
                    platform = rng.choices(["Illumina NovaSeq", "PacBio Revio", "ONT PromethION"], [70, 15, 15])[0]
                    cov = round(rng.uniform(8, 60), 1)
                    passed = int(cov >= 12 and rng.random() > 0.07)
                    cur.execute("INSERT INTO sequencing_runs (sample_id, platform, mean_coverage, run_date, passed_qc)"
                                " VALUES (?, ?, ?, ?, ?)", (sample_id, platform, cov, _date(rng, date(2020, 1, 1), 1500), passed))
                    run_id = cur.lastrowid
                    if not passed:
                        continue
                    calls = []
                    for ins in polymorphic_ids:
                        af = min(0.95, base_af[ins] * pop_shift[(ins, pop)])
                        if planted.get("NF1") == ins:
                            af = 0.9 if carries_nf1 else 0.0
                        if planted.get("F8") == ins:
                            af = 0.9 if carries_f8 else 0.0
                        if rng.random() < af:
                            gt = "1/1" if rng.random() < af else "0/1"
                            calls.append((run_id, ins, gt, max(2, int(rng.gauss(cov / (1 if gt == "1/1" else 2), 3)))))
                    cur.executemany("INSERT INTO insertion_calls VALUES (?, ?, ?, ?)", calls)
    con.commit()
    con.execute("ANALYZE")
    con.execute("VACUUM")
    con.close()
    return path


if __name__ == "__main__":
    import sys

    out = build(sys.argv[1] if len(sys.argv) > 1 else "build/biobank.db")
    print(f"wrote {out} ({out.stat().st_size / 1e6:.1f} MB)")
