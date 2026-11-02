"""Normalize a user's app idea and extract useful search phrases."""
import re
from typing import Any, Dict, List

STOPWORDS = {
    "a","an","the","and","or","for","to","of","in","on","with","by","from",
    "is","are","was","be","that","this","it","app","application","make","made",
    "help","user","users","using","use","can","will","want","need",
    "hai","hain","ka","ki","ke","ko","mein","me","se","aur","ya","ek","karo",
    "karna","kare","chahiye","liye","wala","wali","waale","mera","meri","apna",
    "jo","bhi","ho","hoga","hogi","sakta","sakti","sakte"
}

def clean_text(value: Any) -> str:
    """Return a safe, normalized text string."""
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()

def extract_idea_keywords(idea: str, proposed_features=None, max_keywords: int = 20) -> List[str]:
    """Extract distinct meaningful words and short phrases from idea/features."""
    texts = [clean_text(idea)]
    if proposed_features:
        if isinstance(proposed_features, str):
            texts.append(clean_text(proposed_features))
        else:
            texts.extend(clean_text(x) for x in proposed_features if clean_text(x))

    tokens = []
    for text in texts:
        words = re.findall(r"[a-zA-Z][a-zA-Z0-9'-]*|[\u0900-\u097F]+", text.lower())
        tokens.extend(w for w in words if len(w) > 2 and w not in STOPWORDS)

    # Keep frequent tokens first while preserving their original order.
    result = []
    for token in tokens:
        if token not in result:
            result.append(token)
        if len(result) >= max_keywords:
            break

    # Include meaningful adjacent English word pairs as search phrases.
    phrase_candidates = []
    for text in texts:
        words = re.findall(r"[a-zA-Z][a-zA-Z0-9'-]*|[\u0900-\u097F]+", text.lower())
        for i in range(len(words) - 1):
            a, b = words[i], words[i + 1]
            if a not in STOPWORDS and b not in STOPWORDS and len(a) > 2 and len(b) > 2:
                phrase = f"{a} {b}"
                if phrase not in phrase_candidates:
                    phrase_candidates.append(phrase)
    return (phrase_candidates[:8] + result)[:max_keywords]

def prepare_idea_input(idea: str, proposed_features=None, language: str = "auto") -> Dict[str, Any]:
    """Prepare normalized input for downstream NLP modules."""
    normalized_idea = clean_text(idea)
    features = proposed_features or []
    if isinstance(features, str):
        features = [x.strip() for x in re.split(r"[,;\n]", features) if x.strip()]
    else:
        features = [clean_text(x) for x in features if clean_text(x)]
    if not normalized_idea:
        return {"status": "error", "error": "Please enter an app idea.", "idea": "", "keywords": [], "proposed_features": features}
    return {
        "status": "ok",
        "idea": normalized_idea,
        "language": language or "auto",
        "proposed_features": features,
        "keywords": extract_idea_keywords(normalized_idea, features),
    }
