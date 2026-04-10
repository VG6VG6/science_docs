from app.config import settings
from app.scopus_client import _scopus_request
import json
data = _scopus_request({
    "query": 'TITLE("Semantic configuration model with natural transformations")',
    "count": 1,
})
print(json.dumps(data.get("search-results", {}).get("entry", []), indent=2))
