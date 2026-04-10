import requests
import json
headers = {"Accept": "application/json"}
response = requests.get("https://api.crossref.org/works/10.1016/j.cogsys.2023.101185", timeout=5)
print(json.dumps(response.json(), indent=2))
