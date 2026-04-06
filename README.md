# science_docs

## Run Server

Start the backend (it also serves the frontend from `web/` on the same port):

```bash
uvicorn api:app --reload --app-dir app --host 0.0.0.0 --port 8000
```

Open in browser:

- Frontend: `http://127.0.0.1:8000/`
- API docs: `http://127.0.0.1:8000/docs`