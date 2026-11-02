"""idea text -> full analysis. Each stage is a small function with a typed input and output, and
progress is written to the DB after every stage so the frontend can poll /analyses/{id}/status."""
import logging

from . import feature_evaluation, gemini_client, nlp_interface, nlp_matching, play_store, prompts, roadmap, scoring
from .db import Analysis, SessionLocal
from .schemas import AnalysisResult, IdeaUnderstanding

log = logging.getLogger("ideonix.pipeline")

STAGES = [
    "understand_idea",
    "find_competitors",
    "collect_reviews",
    "analyze_reviews",
    "score_opportunity",
    "evaluate_features",
    "build_roadmap",
]


def run_pipeline(analysis_id: str) -> None:
    """Runs in a background task with its own DB session."""
    db = SessionLocal()
    row = db.get(Analysis, analysis_id)
    if row is None:
        db.close()
        return

    partial: dict = {}

    def checkpoint(stage: str) -> None:
        row.status, row.stage, row.result = "running", stage, dict(partial) # type: ignore
        db.commit()

    try:
        checkpoint("understand_idea")
        idea = gemini_client.generate_structured(prompts.idea_prompt(row.idea_text), IdeaUnderstanding)
        partial["idea"] = idea.model_dump(mode="json")

        checkpoint("find_competitors")
        apps = play_store.search_apps(nlp_matching.search_queries(row.idea_text, idea))
        competitors, m_status, m_message = nlp_matching.match_apps(row.idea_text, idea, apps)
        partial["competitors"] = [c.model_dump(mode="json") for c in competitors]
        partial["matches_status"], partial["matches_message"] = m_status, m_message

        checkpoint("collect_reviews")
        reviews = [r for c in competitors for r in play_store.fetch_reviews(c.app_id)]
        partial["sample_reviews"] = [x.model_dump(mode="json") for x in nlp_interface.sample_reviews(reviews, competitors)]

        checkpoint("analyze_reviews")
        analysis = nlp_interface.analyze_reviews(reviews, competitors)
        partial["review_analysis"] = analysis.model_dump(mode="json")

        checkpoint("score_opportunity")
        score = scoring.compute_score(competitors, analysis)
        partial["score"] = score.model_dump(mode="json")

        checkpoint("evaluate_features")
        evaluations = feature_evaluation.evaluate_features(idea, analysis.gaps)
        partial["feature_evaluations"] = [e.model_dump(mode="json") for e in evaluations]

        checkpoint("build_roadmap")
        plan = roadmap.build_roadmap(idea, evaluations)
        partial["roadmap"] = plan.model_dump(mode="json")

        # validate the assembled result against the contract before marking complete
        final = AnalysisResult.model_validate(partial)
        row.result = final.model_dump(mode="json")
        row.status, row.stage, row.error = "completed", None, None
        db.commit()
    except Exception as exc:
        log.exception("Pipeline failed for %s", analysis_id)
        db.rollback()
        row = db.get(Analysis, analysis_id)
        row.status, row.error = "failed", f"{type(exc).__name__}: {exc}"[:500] # type: ignore
        db.commit()
    finally:
        db.close()