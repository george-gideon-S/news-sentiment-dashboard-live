"""Vercel serverless function: live re-scrape -> JSON.

GET /api/refresh  ->  fresh scrape of all five feeds, scored + tagged.

This is what makes the deployed dashboard *live* rather than a static snapshot.
The page loads the committed data.json instantly, then this endpoint backs the
"Refresh" button (and the edge caches the result for a few minutes so we don't
re-scrape on every click).
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler

# Make the deployment root importable so we can pull in the shared engine.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import generate_payload  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            payload = generate_payload()
            status = 200
        except Exception as exc:  # never 500 the page into a blank state
            payload = {"error": f"{type(exc).__name__}: {exc}", "headlines": []}
            status = 502
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        # Let Vercel's edge cache the scrape for 5 min, serve stale for 10 more
        # while it revalidates -- keeps the feeds from getting hammered.
        self.send_header("Cache-Control", "s-maxage=300, stale-while-revalidate=600")
        self.end_headers()
        self.wfile.write(body)
