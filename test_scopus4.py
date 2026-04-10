import requests
import json

headers = {"X-ELS-APIKey": "c50cc08da4728dcadfb2c962a924874c", "Accept": "application/json"}
# Fetching the abstract directly to see if abstract API provides all authors
response = requests.get("https://api.elsevier.com/content/abstract/scopus_id/85176321727", headers=headers, timeout=5)
print(json.dumps(response.json(), indent=2))
