"""Verify supplied DOIs against Crossref; record failures rather than infer metadata."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.request import Request, urlopen

DOIS = ["10.1016/j.trd.2023.103928", "10.1016/j.trd.2017.06.020", "10.1016/j.trd.2024.104354",
        "10.3390/land13111894", "10.13284/j.cnki.rddl.20250873"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("docs/references/online_metadata.json"))
    args = parser.parse_args()
    report = {"checked_at": datetime.now(timezone.utc).isoformat(), "service": "https://api.crossref.org", "references": []}
    for doi in DOIS:
        url = "https://api.crossref.org/works/" + doi
        item = {"requested_doi": doi, "url": url}
        try:
            request = Request(url, headers={"User-Agent": "urban-flood-traffic-resilience/0.1 literature-verification"})
            with urlopen(request, timeout=20) as response:
                message = json.load(response)["message"]
            item.update({"status": "verified", "metadata": {key: message.get(key) for key in
                         ("DOI", "title", "author", "container-title", "volume", "issue", "page", "article-number", "published", "URL", "license")}})
        except Exception as exc:
            item.update({"status": "unavailable", "error": f"{type(exc).__name__}: {exc}"})
        report["references"].append(item)
        print(doi, item["status"], flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
