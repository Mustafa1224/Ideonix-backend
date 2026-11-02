"""Glue between Divyanshi's NLP stage 1 (app/nlp, used unchanged) and the pipeline.
It builds Google Play search queries from the idea, then uses her functions to summarise each
app, extract its features, score its relevance and classify it as Exact, Strong or Partial Match.
(Her summarize_with_gemini is not used here: the extractive summary is fast, free and never
fails, and avoids one extra AI call per app.)"""
from typing import Optional

from .nlp.description_matching import classify_apps
from .nlp.idea_compare import extract_feature_keywords, make_fallback_summary
from .nlp.idea_input import extract_idea_keywords
from .schemas import Competitor, IdeaUnderstanding

RELEVANCE = {"Exact Match": "high", "Strong Match": "medium", "Partial Match": "low"}


def search_queries(idea_text: str, idea: IdeaUnderstanding) -> list[str]:
    kws = [k.strip().lower() for k in idea.keywords if k.strip()]
    phrases = [k for k in extract_idea_keywords(idea_text, idea.core_features) if " " in k]
    candidates = [" ".join(kws[:2]), " ".join(kws[:4]), *phrases[:2], *(kws[:1])]
    out = []
    for q in candidates:
        if q and q not in out:
            out.append(q)
    return out[:4]


def match_apps(idea_text: str, idea: IdeaUnderstanding, apps: list[dict], top: int = 5) -> tuple[list[Competitor], str, Optional[str]]:
    match_text = " ".join(idea.keywords + idea.core_features)
    keywords = extract_idea_keywords(match_text, idea.core_features) + [k.lower() for k in idea.keywords]
    enriched = []
    for a in apps:
        desc = a.get("description") or ""
        enriched.append({**a, "description_summary": make_fallback_summary(desc), "feature_keywords": extract_feature_keywords(desc)})
    matches = classify_apps(enriched, match_text, keywords)[:top]
    if not matches:
        return [], "no_meaningful_match", "No relevant apps were found in the Google Play search results."
    competitors = [
        Competitor(
            app_id=a["appId"], name=a["title"], rating=round(float(a.get("score") or 0), 1), installs=int(a.get("installs") or 0),
            relevance=RELEVANCE[a["category"]], match_category=a["category"], match_score=a["description_relevance"], # type: ignore
            summary=a["description_summary"], feature_keywords=a["feature_keywords"], store_url=a.get("url") or None,
            icon=a.get("icon") or None, developer=a.get("developer") or None, genre=a.get("genre") or None,
        )
        for a in matches
    ]
    return competitors, "matches_found", None