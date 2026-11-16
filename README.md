# Enterprise Knowledge Graph Studio (prototype)

PostgreSQL tables **or several uploaded CSV files** → hybrid ontology (manual / rule-drafted + Groq AI,
human-approved, versioned) → NetworkX `MultiDiGraph` → validation gate → versioned graph store
(JSON + GraphML, optional Neo4j).
Every stage has its own module **and** its own screen that shows what it does, why, its input,
its output and what actually happened.

## Run

```powershell
python -m venv .venv ; .venv\Scripts\activate
pip install -r requirements.txt

# UI (run from the project root so .streamlit/config.toml is picked up)
streamlit run ui/app.py

# Headless, same code as the UI
python scripts/run_pipeline.py              # built-in sample data + offline AI response
python scripts/run_pipeline.py --postgres   # PG* variables from .env (read-only user)
python scripts/run_pipeline.py --use-groq   # live Groq call (GROQ_API_KEY)
python scripts/run_pipeline.py --csv-dir data/samples/customer360   # every .csv in a folder, ontology drafted by rules

# Tests (200): CSV source, ontology drafting, all 16 stages on files, the Streamlit screens, the CLI
pip install -r requirements-dev.txt
python -m pytest tests
```

To try a real database: `psql -d retail -f sql/01_source_schema.sql`, copy `.env.example` to
`.env`, fill the `PG*` values, then choose **PostgreSQL** in Stage 2.

To try files: Stage 2 → **Upload CSV files** → select several files at once (or use the bundled Customer 360
examples), then Stage 5 → **🪄 Draft from the schema**. See [Uploading CSV files](#uploading-csv-files-stage-2).

## Folder structure

```
Enterprices_KG/
├── .env.example                 settings template (secrets come from env / vault, never code)
├── .streamlit/config.toml       UI theme
├── requirements.txt
├── sql/
│   ├── 01_source_schema.sql     sample retail source + indexes + read-only role
│   └── 02_kg_meta_schema.sql    production DDL for the ontology repository / build metadata
├── data/
│   ├── ontologies/retail_manual_draft.json   example manual draft (Stage 5)
│   ├── fixtures/groq_offline_fixture.json    recorded AI answer incl. hallucinations (Stage 6)
│   └── samples/                              CSV examples: customer360 (7 files), customer360_messy (refused on purpose)
├── storage/                     runtime output (git-ignored)
│   ├── catalog/                 schema catalog (Stage 3)
│   ├── ontology_repo/<id>/      ontology versions vNNNN.json + audit.jsonl (Stage 9)
│   ├── graphs/<id>/<build_id>/  graph snapshots + CURRENT pointer (Stage 16)
│   └── logs/ai_requests.jsonl   every AI request (Stage 6)
├── scripts/run_pipeline.py      CLI runner
├── src/kg/
│   ├── config.py                settings from environment
│   ├── pipeline.py              run_all(): stages 1-16 in order
│   ├── viz.py                   PyVis renderers (graph, ontology, schema)
│   ├── core/
│   │   ├── ontology_models.py   Pydantic ontology model (classes, attributes, relationships, mapping)
│   │   ├── ontology_draft.py    rule-based ontology draft from a SchemaCatalog (Stage 5 "Draft from the schema")
│   │   ├── naming.py            file / column / table names -> valid class, attribute, relationship names
│   │   ├── schema_models.py     SchemaCatalog + PostgreSQL type compatibility
│   │   ├── transform.py         normalise, coerce, canonical keys, node ids
│   │   └── context.py           PipelineContext (stage hand-off + activity log) and stage list
│   ├── sources/
│   │   ├── base.py              read-only DataSource interface
│   │   ├── postgres_source.py   psycopg 3 pool, pg_catalog introspection, keyset batches
│   │   ├── csv_source.py        several uploaded CSV files -> one schema (types, keys, links) behind DataSource
│   │   ├── sample_source.py     in-memory source (same interface)
│   │   └── sample_data.py       sample tables with deliberate data problems
│   └── stages/                  ONE FILE PER STAGE, each exposes run(ctx, ...)
│       ├── s01_scope.py                Part A · Prepare
│       ├── s02_connect.py
│       ├── s03_schema_extraction.py
│       ├── s04_schema_analysis.py
│       ├── s05_manual_ontology.py      Part B · Ontology
│       ├── s06_ai_suggestions.py
│       ├── s07_review_approval.py
│       ├── s08_ontology_validation.py
│       ├── s09_ontology_repository.py
│       ├── s10_build_plan.py
│       ├── s11_extraction.py           Part C · Build
│       ├── s12_data_quality.py
│       ├── s13_cleaning_er.py
│       ├── s14_graph_builder.py
│       ├── s15_graph_validation.py
│       └── s16_graph_persistence.py
├── ui/
│   ├── app.py                   Streamlit entry (navigation grouped by part)
│   ├── components/              bootstrap (session context), layout (stage header, guard, log), graph_view
│   └── pages/                   home.py, s01_scope.py … s16_store.py, explorer.py (one screen per stage)
└── tests/                       pytest: csv_source, ontology_draft, pipeline on files, UI click-through, CLI
```

## The stages

| # | Stage | Output |
|---|---|---|
| 1 | Goal & scope | scope sheet (questions, tables, sensitive columns) |
| 2 | Connect safely | read-only session (statement timeout, pool) **or** several uploaded CSV files as in-memory tables |
| 3 | Schema extraction | SchemaCatalog from `pg_catalog` |
| 4 | Schema analysis | table types, relationship candidates, undeclared FKs |
| 5 | Manual ontology | draft: classes, attributes, relationships, mapping (hand-made, or **🪄 drafted from the schema by rules**) |
| 6 | Groq AI suggestions | labelled suggestions (valid / needs review / invalid) |
| 7 | Review & approve | hybrid draft (origin manual / ai / hybrid) |
| 8 | Ontology validation | structural + semantic report |
| 9 | Ontology versioning | approved immutable version (four-eyes), audit, rollback |
| 10 | Build plan | table/column → node/edge mapping |
| 11 | Data extraction | keyset batches, checkpoints, watermarks |
| 12 | Data quality | block / quarantine / warn findings, referential integrity |
| 13 | Clean & entity resolution | canonical records, merges, quarantine |
| 14 | Build NetworkX graph | `MultiDiGraph` (nodes pass, edges pass) |
| 15 | Graph validation | reconciliation + ontology conformance |
| 16 | Store graph | versioned snapshot, CURRENT pointer, optional Neo4j |

On the sample data the result is 33 nodes and 52 edges: customer 11 is merged into customer 2,
product 206 (negative price) and the PLACED edge of order 1012 (customer 99 does not exist) are
quarantined with reasons, and Customer:7 is reported as isolated.

## Uploading CSV files (Stage 2)

Stage 2 → **Upload CSV files** takes several files at once. Each file becomes a table `csv.<file_name>`; everything
after Stage 2 runs unchanged because the files sit behind the same read-only `DataSource` interface as PostgreSQL.
On the 7 bundled Customer 360 files the whole pipeline gives **54 nodes and 64 edges**, in any file order.

What is worked out from the files (rules only, no AI), and shown in Stage 2 with every doubt listed as a warning:

| Step | Rule |
|---|---|
| Parse | UTF-8 (BOM) or Windows-1252; delimiter `, ; tab \|` read from the header; blank lines skipped; `""`, `null`, `none`, `nan`, `n/a` are NULL |
| Names | `Cust ID` → column `cust_id` (the original header is kept and shown in Stage 3); file name → table / class name |
| Types | bigint, double precision (also `4,500,000`), boolean `true/false`, date `YYYY-MM-DD`, timestamp; everything else text. Phone / account numbers, codes and numbers with leading zeros stay text |
| Key | an identifier column (`id`, `code`, `no`…) whose values are unique; else a composite such as `cust_id + score_date`; else a unique text column. A failing identifier (repeats, empty cells) is **reported, never replaced** by another column |
| Links | a column named like another file's key whose values match it becomes a foreign key (same name + overlap, or "mentions the file name" + ≥80 % overlap, flagged *values only*). Orphan values are reported and later set aside by Stage 12 |

Stage 5 → **🪄 Draft from the schema** then builds the ontology: a class per table that has a key, `Owner -[HAS_HOLDER]-> Holder`
per link (via the holder's rows), `A -[BRIDGE]-> B` per bridge table, and notes for everything it had to skip. The draft goes
through the same validation (Stage 8), four-eyes approval (Stage 9) and build (Stages 10-16) as a hand-made ontology.
The same button works for PostgreSQL schemas.

Safety: files live in memory only (never written to disk); limits `KG_MAX_UPLOAD_FILES` (25), `KG_MAX_UPLOAD_MB` (25 per file) and
`KG_MAX_UPLOAD_ROWS` (200 000 per file); only `.csv/.tsv/.txt`, binary files refused, file names reduced to a safe table name,
cells that start with `= + - @` are reported and kept as text. **All files are checked before anything is loaded** — if one is bad
the upload is rejected with every reason and the previous connection stays as it was.

Things to know: the AI step (Stage 6) is optional for files — the recorded offline answer only fits the built-in sample, so with files it
needs a live Groq key or is skipped. Cleaning in Stage 13 handles spacing, case and merging of records; messy number or date formats
(`₹ 45,00,000`, `12/03/1985`, `8.5%`) must be fixed in the file — they are reported as warnings and kept as text.
`data/samples/customer360_messy` shows this: it is refused because its identifiers repeat.

## Design rules

* The builder never hard-codes a table or class; everything comes from the approved ontology.
* The AI only suggests: it sees structure (and optional masked samples, never PII), every
  suggestion is checked against the real schema, and a person decides. Builds never call the AI.
* Only an approved ontology version can be built; approval needs a passing validation and a
  reviewer different from the author.
* A graph becomes CURRENT only if Stage 15 passes. Bad rows are quarantined with a reason, never dropped.
* Table and column names reach SQL only after a catalog whitelist check and `psycopg.sql.Identifier` quoting.

## Not in this prototype yet

Incremental (watermark) graph updates and CDC, DuckDB "Silver" staging for very large tables,
moving the ontology repository from files into `kg_meta` in PostgreSQL, analytics / GraphRAG /
NL queries, authentication and role-based PII hiding.
