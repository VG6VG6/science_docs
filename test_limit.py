import requests
import json
headers = {"X-ELS-APIKey": "c50cc08da4728dcadfb2c962a924874c", "Accept": "application/json"}
response = requests.get("https://api.elsevier.com/content/search/scopus", headers=headers, params={
    "query": 'AUTHOR-NAME("Wolfengagen, V.")',
    "count": 200
}, timeout=5)
print("count 200:", response.status_code, response.text[:200])

response2 = requests.get("https://api.elsevier.com/content/search/scopus", headers=headers, params={
    "query": 'AUTHOR-NAME("Wolfengagen, V.")',
    "count": 25
}, timeout=5)
print("count 25:", response2.status_code, response2.text[:200])
