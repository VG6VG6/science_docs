import requests
import json
headers = {"X-ELS-APIKey": "c50cc08da4728dcadfb2c962a924874c", "Accept": "application/json"}
response = requests.get("https://api.elsevier.com/content/search/scopus", headers=headers, params={
    "query": 'AUTHOR-NAME(Wolfengagen)',
    "count": 1
}, timeout=5)
print(json.dumps(response.json()["search-results"]["entry"][0], indent=2))
