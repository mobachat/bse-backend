# api/bse.py
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List, Dict
from datetime import datetime, timedelta
try:
    from zoneinfo import ZoneInfo  # Python 3.9+
    IST_TZ = ZoneInfo("Asia/Kolkata")
except Exception:
    IST_TZ = None  # fallback handled below

from scrapper_bse import fetch_announcements  # your working scraper

def today_ddmmyyyy_ist() -> str:
    if IST_TZ is not None:
        d = datetime.now(IST_TZ).date()
    else:
        # Fallback: UTC + 5:30 -> not perfect for DST (IST has none), but safe
        d = (datetime.utcnow() + timedelta(hours=5, minutes=30)).date()
    return d.strftime("%d/%m/%Y")  # what BSE typically expects

app = FastAPI(title="BSE Announcements API (Today Only)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

@app.get("/")  # Framework mode -> served at root "/". Serverless -> "/api/bse".
def get_today(
    # dates are intentionally ignored to always fetch “today”
    segment: str = Query("C"),
    submission_type: str = Query("0"),
    category: str = Query(""),
    subcategory: str = Query(""),
    search: str = Query(""),
    max_pages: int = Query(5, ge=1, le=50),
    probe: bool = Query(False),
):
    today = today_ddmmyyyy_ist()
    rows: List[Dict] = fetch_announcements(
        from_date=today,
        to_date=today,
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
    return {"date": today, "count": len(dedup), "rows": dedup[:200]}

@app.get("/healthz")
def health():
    return {"ok": True, "today_ist": today_ddmmyyyy_ist()}
