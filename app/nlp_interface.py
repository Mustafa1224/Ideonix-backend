"""Review analysis. Works on REAL reviews now. Gap detection is a theme-keyword heuristic over
low-rated reviews and sentiment comes from star ratings, until the team's sentiment module
replaces analyze_reviews (keep the signature)."""
import re
from collections import defaultdict

from .schemas import Competitor, Gap, Review, ReviewAnalysis, SampleReview

_THEMES = {
    "ads": (r"\b(ads?|adverts?|advertisements?)\b", "Too many ads", "Ad-free or low-ad experience"),
    "crash": (r"\b(crash\w*|force close|freez\w*|hangs?|hanging|not opening)\b", "Crashes and freezing", "Stable, crash-free core flow"),
    "bugs": (r"\b(bugs?|glitch\w*|not working|doesn.?t work|errors?)\b", "Bugs and errors", "Reliable core features"),
    "slow": (r"\b(slow|lag\w*|loading)\b", "Slow performance", "Fast, lightweight performance"),
    "login": (r"\b(login|log in|otp|sign in|password|verification)\b", "Login and OTP trouble", "Simple, dependable sign-in"),
    "payment": (r"\b(payments?|refunds?|charged|transactions?|deducted)\b", "Payment and money issues", "Transparent, reliable payments"),
    "price": (r"\b(subscriptions?|premium|expensive|price|paid)\b", "Paywalls and pricing complaints", "Fair pricing with a useful free tier"),
    "support": (r"\b(customer care|customer support|support|no response)\b", "Poor customer support", "Responsive support"),
    "ui": (r"\b(confusing|complicated|interface|hard to use|difficult)\b", "Confusing interface", "Simple, clear interface"),
    "notif": (r"\b(notifications?|reminders?|alerts?)\b", "Unreliable notifications", "Dependable reminders and notifications"),
    "sync": (r"\b(sync\w*|backup|lost data|data loss|restore)\b", "Data loss and sync problems", "Reliable backup and sync"),
    "language": (r"\b(hindi|language|regional)\b", "Missing language support", "Hindi and regional language support"),
    "offline": (r"\b(offline|no internet|internet)\b", "Weak offline support", "Works well offline"),
}


def sentiment_label(rating: int) -> str:
    return "Positive" if rating >= 4 else "Neutral" if rating == 3 else "Negative"


def analyze_reviews(reviews: list[Review], competitors: list[Competitor]) -> ReviewAnalysis:
    names = {c.app_id: c.name for c in competitors}
    hits: dict[str, list[Review]] = defaultdict(list)
    for r in reviews:
        if r.rating > 3:
            continue
        for key, (pattern, _, _) in _THEMES.items():
            if re.search(pattern, r.text.lower()):
                hits[key].append(r)
    gaps = [
        Gap(
            title=_THEMES[k][1], missing_feature=_THEMES[k][2], mentions=len(rs),
            competitors=sorted({names.get(r.app_id, r.app_id) for r in rs}),
            quotes=[r.text[:200] for r in sorted(rs, key=lambda x: -len(x.text))[:3]],
        )
        for k, rs in hits.items()
    ]
    gaps.sort(key=lambda g: g.mentions, reverse=True)
    split = {"Positive": 0, "Neutral": 0, "Negative": 0}
    for r in reviews:
        split[sentiment_label(r.rating)] += 1
    avg = sum((r.rating - 3) / 2 for r in reviews) / len(reviews) if reviews else 0.0
    return ReviewAnalysis(review_count=len(reviews), avg_sentiment=round(avg, 3), gaps=gaps[:8], sentiment_split=split)


def sample_reviews(reviews: list[Review], competitors: list[Competitor], per_app: int = 3, total: int = 12) -> list[SampleReview]:
    out = []
    for c in competitors:
        mine = sorted((r for r in reviews if r.app_id == c.app_id and len(r.text) >= 25), key=lambda r: -len(r.text))
        for r in mine[:per_app]:
            out.append(SampleReview(app_name=c.name, text=r.text[:220], rating=r.rating, sentiment=sentiment_label(r.rating)))
    return out[:total]