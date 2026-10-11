"""Read public research metadata/abstracts and retain source evidence."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
import json
import requests
from bs4 import BeautifulSoup

OUT = Path(__file__).resolve().parent
CACHE = json.loads((OUT / "sources.json").read_text(encoding="utf-8")) if (OUT / "sources.json").exists() else {}
DOIS = [
    "10.1016/j.finr.2025.100088",
    "10.1080/0015198X.2025.2533099",
    "10.1002/rfe.1118",
    "10.1016/j.frl.2026.110360",
    "10.1016/j.ribaf.2025.103165",
    "10.1016/j.jbankfin.2024.107343",
    "10.1108/MF-08-2022-0397",
    "10.1016/j.frl.2022.103220",
    "10.1016/j.econmod.2022.105796",
    "10.2139/ssrn.2542534",
    "10.1017/S0022109024000085",
    "10.2139/ssrn.6811380",
    "10.1016/j.pacfin.2021.101607",
    "10.2139/ssrn.5130681",
    "10.2139/ssrn.5493686",
]


def fetch(doi):
    url = "https://api.openalex.org/works/https://doi.org/" + doi
    result = {"doi":doi,"url":"https://doi.org/"+doi,"queried_url":url}
    try:
        response = requests.get(url,timeout=35)
        result["status"] = response.status_code
        if response.status_code == 200:
            data = response.json()
            inverted = data.get("abstract_inverted_index") or {}
            tokens = {i:word for word, positions in inverted.items() for i in positions}
            result.update(title=data.get("title"),publication_date=data.get("publication_date"),
                          abstract=" ".join(tokens[i] for i in sorted(tokens)),
                          authors=[a.get("author",{}).get("display_name") for a in data.get("authorships",[])],
                          sources=[{k:x.get(k) for k in ["landing_page_url","pdf_url","is_oa"]} for x in data.get("locations",[])],
                          publication=data.get("primary_location",{}).get("source"))
    except requests.RequestException as exc:
        result["error"] = type(exc).__name__
    return result


items = list(CACHE.get("items",[]))
cached_dois = {x["doi"] for x in items if x.get("status")==200}
with ThreadPoolExecutor(max_workers=3) as executor:
    futures = [executor.submit(fetch,doi) for doi in DOIS if doi not in cached_dois]
    for f in as_completed(futures):
        result = f.result()
        items.append(result)
        print(json.dumps({k:result.get(k) for k in ["doi","title","publication_date","status","abstract"]},ensure_ascii=False),flush=True)
items.sort(key=lambda x:DOIS.index(x["doi"]))
pages = list(CACHE.get("public_pages",[]))
cached_urls = {x["requested_url"] for x in pages if x.get("status")==200}
for url in [
    "https://rpc.cfainstitute.org/research/financial-analysts-journal/2025/short-term-moving-average-distance",
    "https://ideas.repec.org/a/eee/ecmode/v110y2022ics0264999322000426.html",
    "https://ideas.repec.org/a/eee/jbfina/v170y2025ics0378426624002577.html",
]:
    if url in cached_urls:
        continue
    record = {"requested_url":url}
    try:
        response = requests.get(url,timeout=35)
        record.update(status=response.status_code,final_url=response.url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content,"html.parser")
            for element in soup(["script","style","nav","footer"]):
                element.decompose()
            body = soup.get_text(" ",strip=True)
            index = body.find("Abstract")
            record["abstract_context"] = body[index:index+2500] if index >= 0 else body[:2500]
    except requests.RequestException as exc:
        record["error"] = type(exc).__name__
    pages.append(record)
supplements = list(CACHE.get("crossref_supplements",[]))
cached_supplements = {x["doi"] for x in supplements if x.get("status")==200}
for doi in ["10.1016/j.finr.2025.100088","10.1016/j.jbankfin.2024.107343",
            "10.2139/ssrn.2542534","10.2139/ssrn.6811380"]:
    if doi in cached_supplements:
        continue
    record = {"doi":doi,"queried_url":"https://api.crossref.org/works/"+doi}
    try:
        response = requests.get(record["queried_url"],timeout=35)
        record["status"] = response.status_code
        if response.status_code==200:
            data = response.json()["message"]
            record.update({k:data.get(k) for k in ["title","volume","issue","published","published-print","published-online","created","abstract","container-title"]})
    except requests.RequestException as exc:
        record["error"] = type(exc).__name__
    supplements.append(record)
payload = {"retrieved_at_utc":datetime.now(timezone.utc).isoformat(),"items":items,"public_pages":pages,
           "crossref_supplements":supplements,
           "limits":"Public abstracts and metadata only. Publication date metadata may differ from issue date; no full-text verification unless stated."}
(OUT / "sources.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
print("Saved",len(items),"DOI records and",len(pages),"public-page excerpts.")
