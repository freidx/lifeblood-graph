import os
import re
import csv
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone

BASE = "https://www.lifeblood.com.au/donors/blood-plasma-platelets/blood-supply-levels"
OUT = "docs/history.csv"

session = requests.Session()
session.headers["User-Agent"] = "Mozilla/5.0 (X11; Linux x86_64; rv:155.0) Gecko/20100101 Firefox/155.0"
session.get(BASE, timeout=30).raise_for_status() # get la cookie

def fetch_html(region):
    r = session.post(
        BASE,
        params={"ajax_form": 1, "_wrapper_format": "drupal_ajax"},
        headers={
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json",
            "Origin": "https://www.lifeblood.com.au",
            "Referer": BASE,
        },
        data={
            "form_id": "stock_level_form",
            "lb_region_select": region,
            "_triggering_element_name": "lb_region_select",
            "_drupal_ajax": 1,
        },
        timeout=30,
    )
    r.raise_for_status()
    return "".join(
        c["data"] for c in r.json()
        if c.get("command") == "insert" and isinstance(c.get("data"), str)
    )

def find_percent(d): # regex always looks cursed
    m = re.search(r"\d+(?:\.\d+)?%", " ".join(d.get("class", [])))
    return m.group(0) if m else ""

def parse(html, region):
    soup = BeautifulSoup(html, "html.parser")
    for d in soup.select(".drop-div"):
        level_el = d.select_one(".appeal-mode-label, .day-coverage")
        yield {
            "region": region,
            "type": d.find("strong").get_text(strip=True),
            "level": level_el.get_text(strip=True) if level_el else "",
            "description": d.get("aria-label", ""),
            "percent": find_percent(d) # todo: check later when better supply, only plasma seems to support % currently
        }

now = datetime.now(timezone.utc).isoformat(timespec="seconds")
rows = [dict(r, timestamp=now) for region in ["national"] # can expand to support individual states, don't want to spam them though
        for r in parse(fetch_html(region), region)]
if not rows:
    raise SystemExit("no rows parsed, not writing")

os.makedirs("docs", exist_ok=True)
new_file = not os.path.exists(OUT)
with open(OUT, "a", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["timestamp", "region", "type", "level", "percent"], extrasaction="ignore")
    if new_file:
        w.writeheader()
    w.writerows(rows)

print(f"wrote {len(rows)} rows")