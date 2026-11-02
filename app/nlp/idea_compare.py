"""App description summary and concise feature extraction.

The fallback summary is extractive and intentionally does not copy the entire
Google Play description. For an AI-generated summary, call summarize_with_gemini
after configuring GEMINI_API_KEY and installing google-genai.
"""
import os
import re
from typing import Dict, List

from .description_matching import classify_apps
from .idea_input import clean_text

def extract_feature_keywords(description: str, max_features: int = 10) -> List[str]:
    """Extract concise feature phrases from app-description sentences."""
    text = clean_text(description)
    if not text:
        return []
    chunks = re.split(r"[\n.!?;•]+|(?<=[.!?])\s+", text)
    feature_cues = (
        "track", "manage", "create", "share", "learn", "discover", "remind",
        "schedule", "monitor", "analy", "chat", "connect", "save", "search",
        "record", "plan", "personaliz", "payment", "book", "scan", "upload",
        "download", "report", "progress", "notification", "offline", "lesson",
        "quiz", "budget", "expense", "goal", "habit", "task", "calendar"
    )
    features = []
    for chunk in chunks:
        sentence = clean_text(chunk)
        if len(sentence) < 12:
            continue
        lower = sentence.lower()
        if not any(cue in lower for cue in feature_cues):
            continue
        words = sentence.split()
        phrase = " ".join(words[:9]).strip(" -,:")
        if phrase and phrase.lower() not in {x.lower() for x in features}:
            features.append(phrase)
        if len(features) >= max_features:
            break
    # Avoid returning nothing for a description that lacks obvious cue verbs.
    if not features:
        for chunk in chunks:
            sentence = clean_text(chunk)
            if 15 <= len(sentence) <= 100 and sentence.lower() not in {x.lower() for x in features}:
                features.append(" ".join(sentence.split()[:9]).strip(" -,:"))
            if len(features) >= min(3, max_features):
                break
    return features[:max_features]

def make_fallback_summary(description: str, max_chars: int = 420) -> str:
    """Summarize purpose/capabilities with selected sentences, not raw truncation."""
    text = clean_text(description)
    if not text:
        return "Summary unavailable because the app description is empty."
    sentences = [clean_text(s) for s in re.split(r"(?<=[.!?])\s+|[\n•]+", text) if clean_text(s)]
    selected = []
    for sentence in sentences:
        if len(sentence) >= 20 and sentence.lower() not in {x.lower() for x in selected}:
            selected.append(sentence)
        if len(" ".join(selected)) >= max_chars:
            break
    summary = " ".join(selected) if selected else text
    if len(summary) > max_chars:
        summary = summary[:max_chars].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"
    return summary

def summarize_with_gemini(description: str, app_title: str = "") -> str:
    """Use Gemini if configured; otherwise safely fall back to sentence selection."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return make_fallback_summary(description)
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        prompt = (
            "Write a concise app analysis summary in 2-3 sentences. Explain the app's "
            "purpose, likely target users, and core capabilities. Do not copy the store "
            "description verbatim. Do not invent features not supported by the description. "
            f"App title: {app_title}\nDescription:\n{description}"
        )
        response = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
        result = clean_text(getattr(response, "text", ""))
        return result or make_fallback_summary(description)
    except Exception:
        return make_fallback_summary(description)

def enrich_app(app: Dict) -> Dict:
    result = dict(app)
    description = clean_text(result.get("description") or result.get("summary") or "")
    result["description_summary"] = summarize_with_gemini(description, result.get("title", ""))
    result["feature_keywords"] = extract_feature_keywords(description)
    return result

def build_comparison_output(idea: str, apps: List[Dict], idea_keywords=None) -> Dict:
    enriched = [enrich_app(app) for app in (apps or [])]
    matches = classify_apps(enriched, idea, idea_keywords)
    categories = {name: [] for name in ("Exact Match", "Strong Match", "Partial Match")}
    for app in matches:
        categories[app["category"]].append(app)
    if not matches:
        status = "no_meaningful_match"
        message = "No relevant apps were found in the available search results."
    else:
        status = "matches_found"
        message = None
    return {
        "status": status,
        "message": message,
        "idea": idea,
        "match_count": len(matches),
        "categories": categories,
        "matches": matches,
    }
