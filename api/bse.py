# api/bse.py
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List, Dict

# import your scraper's function from scrapper_bse.py
from scrapper_bse import fetch_announcements  # make sure this exists

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

@app.get("/")  # final URL will be /api/bse
def get_bse(
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    segment: str = Query("C"),
    submission_type: str = Query("0"),
    category: str = Query(""),
    subcategory: str = Query(""),
    search: str = Query(""),
    max_pages: int = Query(3, ge=1, le=30),
    probe: bool = Query(False),
):
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
    # dedup by news_id
    seen, dedup = set(), []
    for r in rows:
        nid = r.get("news_id")
        if nid and nid not in seen:
            seen.add(nid); dedup.append(r)
    return {"count": len(dedup), "rows": dedup[:200]}

@app.get("/healthz")
def health():
    return {"ok": True}
