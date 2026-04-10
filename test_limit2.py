import requests
import json
headers = {"X-ELS-APIKey": "c50cc08da4728dcadfb2c962a924874c", "Accept": "application/json"}
for c in [25, 50, 100, 200]:
    r = requests.get("https://api.elsevier.com/content/search/scopus", headers=headers, params={
        "query": 'AUTHOR-NAME("Wolfengagen, V.")',
        "count": c
    }, timeout=5)
    print(c, r.status_code)
