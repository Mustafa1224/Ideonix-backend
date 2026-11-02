"""Stage 1 feature-comparison helpers. Review sentiment is deliberately excluded."""
from typing import Dict, List

def compare_feature_keywords(idea_features: List[str], app_features: List[str]) -> Dict:
    """Compare normalized feature phrases and report direct overlap/unmatched items."""
    normalize = lambda values: {str(x).strip().lower(): str(x).strip() for x in (values or []) if str(x).strip()}
    idea_map = normalize(idea_features)
    app_map = normalize(app_features)
    common = sorted(set(idea_map) & set(app_map))
    return {
        "matched_features": [idea_map[x] for x in common],
        "idea_features_not_found_in_app": [idea_map[x] for x in sorted(set(idea_map) - set(app_map))],
        "app_features": list(app_map.values()),
        "note": "Phrase overlap is a baseline comparison, not proof that features are fully equivalent."
    }
