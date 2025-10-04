from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List, Dict
from scraper_core import fetch_announcements  # re-exported wrapper around your original

app = FastAPI(title="BSE Announcements API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

@app.get("/api/bse")
def get_bse(
    from_date: Optional[str] = Query(None, description="YYYY-MM-DD or DD/MM/YYYY"),
    to_date: Optional[str] = Query(None, description="YYYY-MM-DD or DD/MM/YYYY"),
    segment: str = Query("C"),
    submission_type: str = Query("0"),
    category: str = Query(""),
    subcategory: str = Query(""),
    search: str = Query(""),
    max_pages: int = Query(3, ge=1, le=30),
    probe: bool = Query(False),
):
    """
    HTTP endpoint that calls your scraper's core function and returns JSON.
    """
    try:
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
        # Deduplicate by 'news_id' if present
        seen = set()
        dedup = []
        for r in rows:
            nid = r.get("news_id")
            if nid and nid not in seen:
                seen.add(nid)
                dedup.append(r)
        return {"count": len(dedup), "rows": dedup[:200]}
    except Exception as e:
        return {"error": str(e)}
