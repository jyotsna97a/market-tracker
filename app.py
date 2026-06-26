from flask import Flask, jsonify, render_template, request
from curl_cffi import requests as curl_requests
import yfinance as yf

app = Flask(__name__)

INDICES = {
    "^NSEI":              "Nifty 50",
    "NIFTYMIDCAP150.NS":  "Nifty Midcap 150",
    "^CNX200":            "Nifty 200",
    "^IXIC":              "NASDAQ",
    "^GSPC":              "S&P 500",
    "^KS11":              "KOSPI",
    "^TWII":              "TAIEX",
}

# Maps timeframe buttons → yfinance (period, interval)
PERIOD_MAP = {
    "1d":  {"period": "1d",  "interval": "5m"},
    "1w":  {"period": "5d",  "interval": "30m"},
    "1mo": {"period": "1mo", "interval": "1d"},
    "6mo": {"period": "6mo", "interval": "1d"},
    "1y":  {"period": "1y",  "interval": "1d"},
    "5y":  {"period": "5y",  "interval": "1wk"},
}

def safe_round(value, digits=2):
    try:
        f = float(value)
        if f != f:
            return None
        return round(f, digits)
    except (TypeError, ValueError):
        return None

def fetch_index_snapshot(ticker, label, session):
    try:
        info = yf.Ticker(ticker, session=session).fast_info
        price      = safe_round(info.last_price)
        prev       = safe_round(info.previous_close)
        change     = safe_round(price - prev)          if (price is not None and prev is not None) else None
        change_pct = safe_round((change / prev) * 100) if (change is not None and prev)            else None
        return {"ticker": ticker, "label": label, "price": price, "change": change, "change_pct": change_pct}
    except Exception as exc:
        app.logger.warning("fetch_index_snapshot failed for %s: %s", ticker, exc)
        return {"ticker": ticker, "label": label, "price": None, "change": None, "change_pct": None}

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/indices")
def api_indices():
    session = curl_requests.Session(impersonate="chrome")
    results = [fetch_index_snapshot(t, l, session) for t, l in INDICES.items()]
    return jsonify(results)

@app.route("/api/history")
def api_history():
    ticker     = request.args.get("ticker", "")
    period_key = request.args.get("period", "1mo")
    config     = PERIOD_MAP.get(period_key, PERIOD_MAP["1mo"])

    try:
        session = curl_requests.Session(impersonate="chrome")
        hist = yf.Ticker(ticker, session=session).history(
            period=config["period"],
            interval=config["interval"],
        )
        if hist.empty:
            return jsonify({"dates": [], "prices": []})
        dates  = [d.isoformat() for d in hist.index]
        prices = [round(float(p), 2) for p in hist["Close"]]
        return jsonify({"dates": dates, "prices": prices})
    except Exception as exc:
        app.logger.warning("api_history failed for %s/%s: %s", ticker, period_key, exc)
        return jsonify({"dates": [], "prices": [], "error": str(exc)})

import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=False)
