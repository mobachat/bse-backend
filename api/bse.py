# api/bse.py
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Optional
from datetime import datetime, timedelta
try:
    from zoneinfo import ZoneInfo
    IST = ZoneInfo("Asia/Kolkata")
except Exception:
    IST = None

from scrapper_bse import fetch_announcements  # your working function

def today_ddmmyyyy_ist() -> str:
    if IST:
        d = datetime.now(IST).date()
    else:
        d = (datetime.utcnow() + timedelta(hours=5, minutes=30)).date()
    return d.strftime("%d/%m/%Y")

app = FastAPI(title="BSE Announcements API — Today (IST)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

@app.get("/")  # Final URL: /api/bse
def today_only(
    search: str = Query(""),
    segment: str = Query("C"),
    submission_type: str = Query("0"),
    category: str = Query(""),
    subcategory: str = Query(""),
    max_pages: int = Query(6, ge=1, le=50),
    diag: bool = Query(False, description="Return minimal diagnostics"),
):
    fd = td = today_ddmmyyyy_ist()

    def _call(fd_in: str, td_in: str, pages: int) -> List[Dict]:
        return fetch_announcements(
            from_date=fd_in,
            to_date=td_in,
            segment=segment,
            submission_type=submission_type,
            category=category,
            subcategory=subcategory,
            search=search,
            max_pages=pages,
            probe=False,
            verbose=False,
        )

    # First try: strict "today"
    rows = _call(fd, td, max_pages)

    # Fallback: if nothing, retry with (today-1 .. today) and a bit more pages
    if not rows:
        y = (datetime.strptime(fd, "%d/%m/%Y") - timedelta(days=1)).strftime("%d/%m/%Y")
        rows = _call(y, td, max_pages + 2)

    # Dedup by news_id
    seen, out = set(), []
    for r in rows:
        nid = r.get("news_id")
        if nid and nid not in seen:
            seen.add(nid)
            out.append(r)

    resp = {"date": fd, "count": len(out), "rows": out[:200]}
    if diag:
        resp["diag"] = {
            "segment": segment, "submission_type": submission_type,
            "category": category, "subcategory": subcategory,
            "search": search, "max_pages": max_pages,
            "first_row": (out[0] if out else None)
        }
    return resp

@app.get("/healthz")
def health():
    return {"ok": True, "today_ist": today_ddmmyyyy_ist()}
