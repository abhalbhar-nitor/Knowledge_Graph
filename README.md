# Enterprise Knowledge Graph Studio (prototype)

PostgreSQL tables → hybrid ontology (manual + Groq AI, human-approved, versioned) → NetworkX
`MultiDiGraph` → validation gate → versioned graph store (JSON + GraphML, optional Neo4j).
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
```

To try a real database: `psql -d retail -f sql/01_source_schema.sql`, copy `.env.example` to
`.env`, fill the `PG*` values, then choose **PostgreSQL** in Stage 2.

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
│   └── fixtures/groq_offline_fixture.json    recorded AI answer incl. hallucinations (Stage 6)
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
│   │   ├── schema_models.py     SchemaCatalog + PostgreSQL type compatibility
│   │   ├── transform.py         normalise, coerce, canonical keys, node ids
│   │   └── context.py           PipelineContext (stage hand-off + activity log) and stage list
│   ├── sources/
│   │   ├── base.py              read-only DataSource interface
│   │   ├── postgres_source.py   psycopg 3 pool, pg_catalog introspection, keyset batches
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
└── ui/
    ├── app.py                   Streamlit entry (navigation grouped by part)
    ├── components/              bootstrap (session context), layout (stage header, guard, log), graph_view
    └── pages/                   home.py, s01_scope.py … s16_store.py, explorer.py (one screen per stage)
```

## The stages

| # | Stage | Output |
|---|---|---|
| 1 | Goal & scope | scope sheet (questions, tables, sensitive columns) |
| 2 | Connect safely | read-only session (statement timeout, pool) |
| 3 | Schema extraction | SchemaCatalog from `pg_catalog` |
| 4 | Schema analysis | table types, relationship candidates, undeclared FKs |
| 5 | Manual ontology | draft: classes, attributes, relationships, mapping |
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
