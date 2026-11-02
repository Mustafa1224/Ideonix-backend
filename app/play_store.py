"""Real Google Play data (apps, details, reviews) through the google-play-scraper package.
Results are cached on disk for 24 hours, so repeat searches are fast and do not depend on
Google being reachable. There is no sample-data mode."""
import hashlib
import json
import logging
import time
from pathlib import Path

from .schemas import Review

log = logging.getLogger("ideonix.playstore")
CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache"
CACHE_TTL = 24 * 3600
COUNTRY, LANG = "in", "en"


class PlayStoreError(RuntimeError):
    pass


def _cached(key, fn):
    CACHE_DIR.mkdir(exist_ok=True)
    f = CACHE_DIR / (hashlib.md5(key.encode()).hexdigest() + ".json")
    if f.exists() and time.time() - f.stat().st_mtime < CACHE_TTL:
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            pass
    data = fn()
    try:
        f.write_text(json.dumps(data, default=str), encoding="utf-8")
    except Exception as exc:
        log.warning("Could not write cache: %s", exc)
    return data


def _normalize(basic: dict, detail: dict | None) -> dict:
    d = detail or {}
    app_id = basic.get("appId") or d.get("appId") or ""
    installs = d.get("realInstalls") or d.get("minInstalls") or 0
    return {
        "appId": app_id,
        "title": d.get("title") or basic.get("title") or app_id,
        "description": d.get("description") or basic.get("description") or d.get("summary") or basic.get("summary") or "",
        "score": d.get("score") or basic.get("score") or 0,
        "installs": int(installs or 0),
        "genre": d.get("genre") or basic.get("genre") or "",
        "icon": d.get("icon") or basic.get("icon") or "",
        "developer": d.get("developer") or basic.get("developer") or "",
        "url": f"https://play.google.com/store/apps/details?id={app_id}",
    }


def search_apps(queries: list[str], limit: int = 8) -> list[dict]:
    """Search Google Play (India) for each query and return up to `limit` unique apps with details."""
    from google_play_scraper import app as gp_app
    from google_play_scraper import search as gp_search

    seen, hits, failures = set(), [], 0
    for q in queries:
        try:
            results = _cached("search:" + q, lambda q=q: gp_search(q, n_hits=10, lang=LANG, country=COUNTRY))
        except Exception as exc:
            failures += 1
            log.warning("Play search failed for %r: %s", q, exc)
            continue
        for r in results:
            if r.get("appId") and r["appId"] not in seen:
                seen.add(r["appId"])
                hits.append(r)
    if queries and failures == len(queries):
        raise PlayStoreError("Could not reach Google Play. Check the internet connection and try again.")

    apps = []
    for r in hits[:limit]:
        try:
            detail = _cached("app:" + r["appId"], lambda r=r: gp_app(r["appId"], lang=LANG, country=COUNTRY))
        except Exception as exc:
            log.warning("Details failed for %s: %s", r["appId"], exc)
            detail = None
        apps.append(_normalize(r, detail))
    return apps


def fetch_reviews(app_id: str, count: int = 80) -> list[Review]:
    from google_play_scraper import Sort
    from google_play_scraper import reviews as gp_reviews

    try:
        rows = _cached(
            f"reviews:{app_id}:{count}",
            lambda: gp_reviews(app_id, lang=LANG, country=COUNTRY, sort=Sort.NEWEST, count=count)[0],
        )
    except Exception as exc:
        log.warning("Reviews failed for %s: %s", app_id, exc)
        return []
    out = []
    for r in rows:
        text, score = (r.get("content") or "").strip(), r.get("score")
        if text and isinstance(score, int) and 1 <= score <= 5:
            out.append(Review(app_id=app_id, text=text, rating=score))
    return out