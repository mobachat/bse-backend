# api/bse.py
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List, Dict
from datetime import datetime, timedelta
try:
    from zoneinfo import ZoneInfo
    IST = ZoneInfo("Asia/Kolkata")
except Exception:
    IST = None

from scrapper_bse import fetch_announcements, probe_connectivity  # <- added

def today_ddmmyyyy_ist() -> str:
    if IST:
        d = datetime.now(IST).date()
    else:
        d = (datetime.utcnow() + timedelta(hours=5, minutes=30)).date()
    return d.strftime("%d/%m/%Y")

app = FastAPI(title="BSE Announcements API (Today Only)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

@app.get("/")
def today_only(
    search: str = Query(""),
    segment: str = Query("C"),
    submission_type: str = Query("0"),
    category: str = Query(""),
    subcategory: str = Query(""),
    max_pages: int = Query(5, ge=1, le=50),
    diag: bool = Query(False, description="Return upstream diagnostics"),
):
    fd = td = today_ddmmyyyy_ist()

    rows: List[Dict] = []
    err: Optional[str] = None
    try:
        rows = fetch_announcements(
            from_date=fd,
            to_date=td,
            segment=segment,
            submission_type=submission_type,
            category=category,
            subcategory=subcategory,
            search=search,
            max_pages=max_pages,
            probe=False,
            verbose=False,
        )
    except Exception as e:
        err = str(e)

    # dedup
    seen, dedup = set(), []
    for r in rows:
        nid = r.get("news_id")
        if nid and nid not in seen:
            seen.add(nid); dedup.append(r)

    resp = {"date": fd, "count": len(dedup), "rows": dedup[:200]}
    if err:
        resp["error"] = err
    if diag:
        resp["diag"] = probe_connectivity()
        resp["sample"] = (dedup[0] if dedup else None)
    return resp

@app.get("/healthz")
def health(): return {"ok": True, "today_ist": today_ddmmyyyy_ist()}
