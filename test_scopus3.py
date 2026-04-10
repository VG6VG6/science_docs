import requests
import json

headers = {"X-ELS-APIKey": "c50cc08da4728dcadfb2c962a924874c", "Accept": "application/json"}
response = requests.get("https://api.elsevier.com/content/search/scopus", headers=headers, params={
    "query": 'TITLE("Semantic configuration model with natural transformations")',
    "count": 1
}, timeout=5)
print(json.dumps(response.json(), indent=2))
