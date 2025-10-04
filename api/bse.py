from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List, Dict
import traceback

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

def _get_fetch():
    """Lazy import so ImportError shows up in the response for easier debugging."""
    try:
        from scraper_core import fetch_announcements
        return fetch_announcements
    except Exception:
        raise RuntimeError("ImportError:\n" + traceback.format_exc())

# Function URL will be: https://<project>.vercel.app/api/bse
# So keep the in-app route at "/"
@app.get("/")
def get_bse(
    from_date: Optional[str] = Query(None, description="YYYY-MM-DD or DD/MM/YYYY"),
    to_date: Optional[str]   = Query(None, description="YYYY-MM-DD or DD/MM/YYYY"),
    segment: str             = Query("C"),
    submission_type: str     = Query("0"),
    category: str            = Query(""),
    subcategory: str         = Query(""),
    search: str              = Query(""),
    max_pages: int           = Query(3, ge=1, le=30),
    probe: bool              = Query(False),
):
    try:
        fetch_announcements = _get_fetch()
        rows: List[Dict] = fetch_announcements(
            from_date=from_date or "",
            to_date=to_date or "",
            segment=segment,
            submission_type=submission_type,
            category=category,
            subcategory=subcategory,
            search=search,
            max_pages=max_pages,
            probe=probe,
            verbose=False,
        )
        # dedup by news_id (if present)
        seen, dedup = set(), []
        for r in rows:
            nid = r.get("news_id")
            if nid and nid not in seen:
                seen.add(nid)
                dedup.append(r)
        return {"count": len(dedup), "rows": dedup[:200]}
    except Exception:
        return {"error": "Server crash", "trace": traceback.format_exc()}
