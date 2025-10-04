#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
scrapper_bse.py — BSE Corporate Announcements via API (browser-like requests)

Usage:
  python scrapper_bse.py --from 2025-09-28 --to 2025-10-04 --verbose --probe
  python scrapper_bse.py --search tata

Notes:
- Mimics a browser, warms cookies, and tries multiple parameter variants / endpoints.
- If the site is blocking, use --probe to print upstream statuses to stderr.
"""

from __future__ import annotations
import datetime as dt
import json
import sys
import time
import random
from typing import Dict, List, Optional
import requests

# ---------- Constants ----------
ANN_HTML = "https://www.bseindia.com/corporates/ann.html"

# Common JSON endpoints BSE uses (deployment may flip between them)
ENDPOINTS = [
    "https://api.bseindia.com/BseIndiaAPI/api/Ann/w",
    "https://api.bseindia.com/BseIndiaAPI/api/AnnGetData/w",
]

# Static assets to touch once so the WAF/anti-bot sets cookies for our session
WARM_ASSETS = [
    "https://www.bseindia.com/include/css/bootstrap.min.css",
    "https://www.bseindia.com/include/js/jquery-1.11.3.min.js",
]

BROWSER_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/120.0.0.0 Safari/537.36"),
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Referer": ANN_HTML,
    "Origin": "https://www.bseindia.com",
    "X-Requested-With": "XMLHttpRequest",
    "Connection": "keep-alive",
}

DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d")


# ---------- Utilities ----------
def to_site_date(s: Optional[str]) -> str:
    """Accept YYYY-MM-DD, DD/MM/YYYY, DD-MM-YYYY, YYYY/MM/DD → return DD/MM/YYYY. If empty, use today."""
    if not s:
        return dt.date.today().strftime("%d/%m/%Y")
    s = s.strip()
    for fmt in DATE_FORMATS:
        try:
            d = dt.datetime.strptime(s, fmt)
            return d.strftime("%d/%m/%Y")
        except ValueError:
            pass
    raise ValueError(f"Invalid date: {s}")


def _safe_get(d: Dict, *keys, default=None):
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return default


def _make_pdf_url(row: Dict) -> Optional[str]:
    att = _safe_get(row, "ATTACHMENTNAME", "ATTACHMENT", "FILE")
    if not att:
        return None
    if isinstance(att, str) and att.lower().startswith("http"):
        return att
    pdfflag = _safe_get(row, "PDFFLAG", "pdfflag", default=0)
    if str(pdfflag) == "1":
        return f"https://www.bseindia.com/xml-data/corpfiling/AttachHis/{att}"
    return f"https://www.bseindia.com/xml-data/corpfiling/AttachLive/{att}"


def _make_detail_url(row: Dict) -> Optional[str]:
    newsid = _safe_get(row, "NEWSID", "newsid")
    scrip = str(_safe_get(row, "SCRIP_CD", "Scripcode", "scripcode", default="")).strip()
    if newsid and scrip:
        return f"https://m.bseindia.com/MAnnDet.aspx?Form=STR&newsid={newsid}&scrpcd={scrip}"
    return None


def normalize_row(r: Dict) -> Dict:
    return {
        "datetime":   _safe_get(r, "DT_TM", "DtTm", "NEWS_DT"),
        "scrip_code": _safe_get(r, "SCRIP_CD", "Scripcode", "scripcode"),
        "scrip_name": _safe_get(r, "S_LONGNAME", "SLONGNAME", "SCRIPNAME", "Scripname"),
        "headline":   _safe_get(r, "NEWSSUB", "HEADLINE", "NEWS_SUB"),
        "category":   _safe_get(r, "CATEGORYNAME", "CATEGORY"),
        "subcategory": _safe_get(r, "SUBCATEGORYNAME", "SUBCAT"),
        "news_id":    _safe_get(r, "NEWSID", "newsid"),
        "pdf_url":    _make_pdf_url(r),
        "detail_url": _make_detail_url(r),
    }


def _extract_rows(payload: Dict) -> List[Dict]:
    """Handle common shapes: {Table:[...]}, {data:[...]}, {"d":{"Table":[...]}}."""
    if not isinstance(payload, dict):
        return []
    for key in ("Table", "table", "data", "Data"):
        val = payload.get(key)
        if isinstance(val, list):
            return val
    if "d" in payload and isinstance(payload["d"], dict):
        if isinstance(payload["d"].get("Table"), list):
            return payload["d"]["Table"]
    return []


def _session(verbose: bool = False) -> requests.Session:
    s = requests.Session()
    s.headers.update(BROWSER_HEADERS)
    # Warm base page (sets cookies like ASP.NET_SessionId, WAF tokens)
    try:
        r = s.get(ANN_HTML, timeout=15)
        if verbose:
            print(f"[probe] GET ann.html → {r.status_code}", file=sys.stderr)
    except requests.RequestException as e:
        if verbose:
            print(f"[probe] ann.html error: {e}", file=sys.stderr)
    # Touch a couple of static assets (some WAFs set/refresh cookies here)
    for url in WARM_ASSETS:
        try:
            r = s.get(url, timeout=10)
            if verbose:
                print(f"[probe] warm {url} → {r.status_code}", file=sys.stderr)
        except requests.RequestException:
            pass
    return s


def _param_variants(segment, subm, f_ddmmyyyy, t_ddmmyyyy, page, search, category, subcategory):
    base = {
        "strCat": category or "-1",
        "strSubCat": subcategory or "",
        "strType": segment or "C",
        "strFromDate": f_ddmmyyyy,
        "strToDate": t_ddmmyyyy,
        "strSearch": search or "",
        "strScrip": "",
        "pageno": str(page),
    }
    v1 = dict(base, **{"strIsXBRL": subm})
    v2 = dict(base, **{"strAnnSubmitType": subm})
    # Some deployments honor strPrevDate; harmless if empty.
    v3 = dict(base, **{"strIsXBRL": subm, "strPrevDate": ""})
    return [v1, v2, v3]


def _try_request(sess: requests.Session, url: str, params: Dict, probe=False, verbose=False):
    # Add a cache-buster & small backoff jitter
    params = dict(params)
    params["_"] = str(int(time.time() * 1000)) + str(random.randint(100, 999))

    # GET first
    try:
        r = sess.get(url, params=params, timeout=25)
        if probe:
            print(f"[probe] GET {url} → {r.status_code}", file=sys.stderr)
        if r.ok:
            try:
                return r.json()
            except Exception:
                if probe:
                    print(f"[probe] GET non-JSON: {r.text[:300]!r}", file=sys.stderr)
    except Exception as e:
        if probe:
            print(f"[probe] GET error: {e}", file=sys.stderr)

    # POST fallback (form-encoded)
    try:
        r = sess.post(
            url,
            data=params,
            timeout=25,
            headers={"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
        )
        if probe:
            print(f"[probe] POST {url} → {r.status_code}", file=sys.stderr)
        if r.ok:
            try:
                return r.json()
            except Exception:
                if probe:
                    print(f"[probe] POST non-JSON: {r.text[:300]!r}", file=sys.stderr)
    except Exception as e:
        if probe:
            print(f"[probe] POST error: {e}", file=sys.stderr)

    return None


def fetch_announcements(
    from_date: str,
    to_date: str,
    *,
    segment: str = "C",
    submission_type: str = "0",
    category: str = "",
    subcategory: str = "",
    search: str = "",
    max_pages: int = 30,
    delay_sec: float = 0.25,
    verbose: bool = False,
    probe: bool = False,
) -> List[Dict]:
    """
    Core fetcher. Returns a list of normalized dicts.
    """
    f = to_site_date(from_date)
    t = to_site_date(to_date)
    sess = _session(verbose=probe)

    all_rows: List[Dict] = []
    page = 1

    while page <= max_pages:
        got_any = False
        for url in ENDPOINTS:
            for params in _param_variants(
                segment, submission_type, f, t, page, search, category, subcategory
            ):
                if verbose:
                    print(f"[debug] try page={page} url={url} params={params}", file=sys.stderr)
                payload = _try_request(sess, url, params, probe=probe, verbose=verbose)
                if not payload:
                    continue
                rows_raw = _extract_rows(payload)
                if verbose:
                    print(f"[debug] rows={len(rows_raw)}", file=sys.stderr)
                if rows_raw:
                    all_rows.extend(normalize_row(r) for r in rows_raw)
                    got_any = True
                    # Heuristic: typical page size ~20 — smaller => last page
                    if len(rows_raw) < 20:
                        return all_rows
        if not got_any:
            break
        page += 1
        if delay_sec:
            time.sleep(delay_sec)

    return all_rows


# ---------- CLI ----------
def _arg(flag: str, default: Optional[str] = None) -> Optional[str]:
    if flag in sys.argv:
        i = sys.argv.index(flag)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default


def _bool(flag: str) -> bool:
    return flag in sys.argv


if __name__ == "__main__":
    today = dt.date.today()
    from_default = (today - dt.timedelta(days=6)).strftime("%Y-%m-%d")
    to_default = today.strftime("%Y-%m-%d")

    from_d = _arg("--from", from_default)
    to_d   = _arg("--to", to_default)
    segment = _arg("--segment", "C")
    subm    = _arg("--subm", "0")
    cat     = _arg("--cat", "")
    subcat  = _arg("--subcat", "")
    search  = _arg("--search", "")
    verbose = _bool("--verbose")
    probe   = _bool("--probe")

    data = fetch_announcements(
        from_date=from_d,
        to_date=to_d,
        segment=segment,
        submission_type=subm,
        category=cat,
        subcategory=subcat,
        search=search,
        verbose=verbose,
        probe=probe,
    )

    # De-dup by news_id
    seen, dedup = set(), []
    for r in data:
        nid = r.get("news_id")
        if not nid or nid in seen:
            continue
        seen.add(nid)
        dedup.append(r)

    print(json.dumps({"count": len(dedup), "rows": dedup[:50]}, ensure_ascii=False, indent=2))
