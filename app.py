from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List, Dict
import traceback

app = FastAPI(title="BSE API (root app.py)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

# health check
@app.get("/")
def root():
    return {"ok": True, "usage": "GET /bse?search=...&from_date=YYYY-MM-DD&to_date=YYYY-MM-DD"}

# lazy import so ImportError becomes visible in JSON
def _get_fetch():
    try:
        from scrapper_bse import fetch_announcements  # your file at repo root
        return fetch_announcements
    except Exception:
        raise RuntimeError("ImportError:\n" + traceback.format_exc())

# MAIN ENDPOINT: /bse  (no /api prefix anymore)
@app.get("/bse")
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
        # dedup by news_id
        seen, dedup = set(), []
        for r in rows:
            nid = r.get("news_id")
            if nid and nid not in seen:
                seen.add(nid); dedup.append(r)
        return {"count": len(dedup), "rows": dedup[:200]}
    except Exception:
        return {"error": "Server crash", "trace": traceback.format_exc()}

# DEBUG: echo any unknown path so we can see what Vercel routes to us
@app.get("/{path_name:path}")
def echo_path(path_name: str, request: Request):
    return {
        "debug": "catch-all",
        "received_path": f"/{path_name}",
        "query": dict(request.query_params),
        "hint": "App is mounted at project root. Use / for health and /bse for data."
    }
