"""Runs all 16 stages in order with default decisions (used by the CLI and the UI 'quick run')."""
from __future__ import annotations

from kg.core.context import PipelineContext
from kg.stages import (s01_scope, s02_connect, s03_schema_extraction, s04_schema_analysis, s05_manual_ontology,
                       s06_ai_suggestions, s07_review_approval, s08_ontology_validation, s09_ontology_repository,
                       s10_build_plan, s11_extraction, s12_data_quality, s13_cleaning_er, s14_graph_builder,
                       s15_graph_validation, s16_graph_persistence)


def run_all(ctx: PipelineContext, postgres: dict | None = None, use_groq: bool = False,
            author: str = "data.modeller", reviewer: str = "reviewer.lead") -> PipelineContext:
    s01_scope.run(ctx, s01_scope.default_scope())
    if postgres:
        s02_connect.connect_postgres(ctx, **postgres)
    else:
        s02_connect.connect_sample(ctx)
    s03_schema_extraction.run(ctx)
    s04_schema_analysis.run(ctx)
    s05_manual_ontology.run(ctx, s05_manual_ontology.load_template())
    items = s06_ai_suggestions.run(ctx, actor=author, use_groq=use_groq, include_samples=True)
    # demo policy: accept valid + needs_review, reject invalid (a human does this in the UI)
    decisions = {i.item_id: {"action": "approve" if i.status in ("valid", "needs_review") else "reject"}
                 for i in items if i.kind != "duplicate"}
    s07_review_approval.run(ctx, decisions, actor=author, acyclic_relationships=["Customer-[REFERRED]->Customer"])
    if not s08_ontology_validation.run(ctx).ok:
        return ctx
    s09_ontology_repository.run(ctx, author=author, reviewer=reviewer)
    s10_build_plan.run(ctx)
    s11_extraction.run(ctx)
    s12_data_quality.run(ctx)
    if not ctx.is_done(12):
        return ctx
    s13_cleaning_er.run(ctx)
    s14_graph_builder.run(ctx)
    s15_graph_validation.run(ctx)
    s16_graph_persistence.run(ctx)
    return ctx
