"""Opportunity score. The weights and thresholds are heuristics: tune them on real ideas and be
ready to show this formula to judges."""
import math

from .schemas import Competitor, OpportunityScore, ReviewAnalysis

WEIGHTS = {"demand": 0.30, "user_pain": 0.25, "gap_size": 0.30, "weak_competition": 0.15}
BUILD_AT, PIVOT_AT = 70, 40  # Build >= 70, Pivot 40-69, Avoid < 40


def _clamp(x: float) -> int:
    return max(0, min(100, round(x)))


def compute_score(competitors: list[Competitor], analysis: ReviewAnalysis) -> OpportunityScore:
    total_installs = sum(c.installs for c in competitors)
    # log scale: 10k installs ~ 0, 100M installs ~ 100
    demand = _clamp((math.log10(max(total_installs, 1)) - 4) / 4 * 100)

    user_pain = _clamp((1 - analysis.avg_sentiment) / 2 * 100)

    gap_mentions = sum(g.mentions for g in analysis.gaps[:5])
    gap_size = _clamp(gap_mentions / max(analysis.review_count, 1) * 250)

    if competitors:
        avg_rating = sum(c.rating for c in competitors) / len(competitors)
        competition_strength = _clamp((avg_rating - 3) / 2 * 100)
    else:
        competition_strength = 0

    total = _clamp(
        WEIGHTS["demand"] * demand
        + WEIGHTS["user_pain"] * user_pain
        + WEIGHTS["gap_size"] * gap_size
        + WEIGHTS["weak_competition"] * (100 - competition_strength)
    )
    verdict = "Build" if total >= BUILD_AT else "Pivot" if total >= PIVOT_AT else "Avoid"
    n = analysis.review_count
    confidence = "low" if n < 50 or len(competitors) < 2 else "medium" if n < 300 else "high"

    return OpportunityScore(
        total=total,
        verdict=verdict,
        demand=demand,
        user_pain=user_pain,
        gap_size=gap_size,
        competition_strength=competition_strength,
        confidence=confidence,
    )
