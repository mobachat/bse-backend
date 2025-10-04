# api/bse.py
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List, Dict

# Import your working scraper function from the root file
from scrapper_bse import fetch_announcements  # <- uses your prototype

app = FastAPI(title="BSE Announcements API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten later if needed
    allow_methods=["GET"],
    allow_headers=["*"],
)

@app.get("/")  # final URL becomes /api/bse
def get_bse(
    from_date: Optional[str] = Query(None, description="YYYY-MM-DD or DD/MM/YYYY"),
    to_date: Optional[str]   = Query(None, description="YYYY-MM-DD or DD/MM/YYYY"),
    segment: str = Query("C"),
    submission_type: str = Query("0"),
    category: str = Query(""),
    subcategory: str = Query(""),
    search: str = Query(""),
    max_pages: int = Query(5, ge=1, le=50),
    probe: bool = Query(False),
):
    """
    Proxies the working scraper. If either date is omitted, your scraper
    defaults to today's date. To prevent empty results, pass both dates or none.
    """
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

    # de-dup by news_id
    seen, dedup = set(), []
    for r in rows:
        nid = r.get("news_id")
        if nid and nid not in seen:
            seen.add(nid)
            dedup.append(r)

    return {"count": len(dedup), "rows": dedup[:200]}

@app.get("/healthz")
def health():
    return {"ok": True}
