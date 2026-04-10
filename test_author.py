import sys
import json
from app.scopus_client import search_articles_by_author
try:
    res = search_articles_by_author("Wolfengagen, V.")
    print(json.dumps(res.articles[0].__dict__, indent=2))
except Exception as e:
    print(e)
