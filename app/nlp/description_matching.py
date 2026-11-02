"""Description-based relevance and category classification."""
import re
from typing import Dict, List, Tuple

BASIC_STOPWORDS = {
    "the","and","for","with","that","this","from","your","you","are","can","will",
    "app","application","users","user","using","use","into","their","have","has",
    "hai","hain","ka","ki","ke","ko","mein","aur","se","liye"
}

def tokens(text: str) -> set:
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9'-]*|[\u0900-\u097F]+", (text or "").lower())
    return {w for w in words if len(w) > 2 and w not in BASIC_STOPWORDS}

def relevance_score(idea: str, app_description: str, idea_keywords=None) -> float:
    idea_terms = set(idea_keywords or []) | tokens(idea)
    app_terms = tokens(app_description)
    if not idea_terms or not app_terms:
        return 0.0
    # Phrase terms count when the phrase appears in the app description.
    phrase_hits = sum(1 for x in (idea_keywords or []) if " " in x and x.lower() in (app_description or "").lower())
    word_terms = {x for x in idea_terms if " " not in x}
    word_score = len(word_terms & app_terms) / max(1, len(word_terms))
    phrase_score = phrase_hits / max(1, len([x for x in (idea_keywords or []) if " " in x]))
    return round(min(1.0, 0.8 * word_score + 0.2 * phrase_score), 4)

def classify_match(score: float) -> str:
    """Map score to the three required categories."""
    if score >= 0.65:
        return "Exact Match"
    if score >= 0.35:
        return "Strong Match"
    if score >= 0.15:
        return "Partial Match"
    return "No Meaningful Match Found"

def classify_apps(apps: List[Dict], idea: str, idea_keywords=None) -> List[Dict]:
    results = []
    for app in apps or []:
        description = app.get("description") or app.get("summary") or ""
        score = relevance_score(idea, description, idea_keywords)
        category = classify_match(score)
        if category == "No Meaningful Match Found":
            continue
        item = dict(app)
        item["description_relevance"] = score
        item["category"] = category
        results.append(item)
    return sorted(results, key=lambda x: x["description_relevance"], reverse=True)
