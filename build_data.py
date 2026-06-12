"""Regenerate the committed data.json snapshot from a live scrape.

    python build_data.py

The deployed page reads data.json on load (so it shows real data instantly,
even before the serverless function warms up). Re-run this and redeploy whenever
you want to refresh the baked-in snapshot.
"""
import json
import pathlib

from core import generate_payload


def main():
    payload = generate_payload()
    out = pathlib.Path(__file__).parent / "data.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {out}  ->  {payload['total']} headlines")
    for r in payload["feeds"]:
        flag = "ok  " if r["ok"] else "FAIL"
        print(f"  [{flag}] {r['name']:<16} count={r['count']} {r['error'] or ''}")


if __name__ == "__main__":
    main()
