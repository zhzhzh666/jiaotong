"""Independent publisher check for a DOI not registered in Crossref."""
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen

url = "https://www.rddl.com.cn/CN/10.13284/j.cnki.rddl.20250873"
result = {"checked_at": datetime.now(timezone.utc).isoformat(), "requested_url": url}
try:
    with urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=25) as response:
        result["final_url"] = response.url
        result["http_status"] = response.status
        text = response.read().decode("utf-8", errors="replace")
    result["title"] = re.findall(r"<title[^>]*>(.*?)</title>", text, re.S)
    result["doi_present"] = "10.13284/j.cnki.rddl.20250873" in text
    result["citation_meta"] = re.findall(r"<meta[^>]*(?:citation_|DC\.)[^>]*>", text, re.I)
except Exception as exc:
    result["error"] = repr(exc)
path = Path("docs/references/publisher_verification.json")
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, ensure_ascii=False, indent=2))
