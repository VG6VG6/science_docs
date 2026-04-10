from app.scopus_client import search_articles_by_author
res = search_articles_by_author("Wolfengagen")
if res.articles:
    import json
    print(json.dumps(res.articles[0].__dict__, indent=2))
else:
    print(res.scopus_error or "No articles")
