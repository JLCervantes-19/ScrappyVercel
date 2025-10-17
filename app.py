from __future__ import annotations

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup

app = Flask(__name__, static_folder="static", static_url_path="/static")
CORS(app)

STATISTICS_URL = "https://www.espn.com.co/futbol/equipo/estadisticas/_/id/2919/liga/COL.1/temporada/2024"
RESULTS_URL = "https://www.espn.com.co/futbol/equipo/resultados/_/id/2919/temporada/2024"
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-CO,es;q=0.9,en;q=0.8",
}
REQUEST_PROXIES = {"http": None, "https": None}


def fetch_soup(url: str) -> BeautifulSoup:
    """Download the page content and return a BeautifulSoup document."""
    response = requests.get(
        url,
        headers=REQUEST_HEADERS,
        proxies=REQUEST_PROXIES,
        timeout=30,
    )
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def _clean_text(value: str) -> str:
    return " ".join(value.split())


def table_to_dict(table: BeautifulSoup, fallback_title: str | None = None) -> dict:
    """Convert a <table> element to a serialisable dictionary."""
    caption_tag = table.find("caption")
    title = (
        (table.get("aria-label") or "").strip()
        or (caption_tag.get_text(" ", strip=True) if caption_tag else "")
        or (fallback_title or "")
    )
    title = title or None

    headers = [
        _clean_text(th.get_text(" ", strip=True))
        for th in table.select("thead tr th")
        if _clean_text(th.get_text(" ", strip=True))
    ]

    body_rows = table.select("tbody tr")
    if not body_rows:
        # Fallback for tables without <tbody>
        body_rows = table.find_all("tr")
        if headers and body_rows:
            body_rows = body_rows[1:]

    rows = []
    for row in body_rows:
        cells = [
            _clean_text(cell.get_text(" ", strip=True))
            for cell in row.find_all(["td", "th"])
        ]
        if any(cells):
            rows.append(cells)

    return {"title": title, "headers": headers, "rows": rows}


def extract_tables_from_page(url: str, selectors: list[str]) -> list[dict]:
    """Scrape all <table> elements contained in any of the given selectors."""
    soup = fetch_soup(url)
    tables_data: list[dict] = []
    seen_tables: set[int] = set()

    for selector in selectors:
        for container in soup.select(selector):
            container_title = (container.get("aria-label") or "").strip() or None
            heading = container.find_previous(["h1", "h2", "h3", "h4"])
            heading_text = (
                heading.get_text(" ", strip=True) if heading is not None else None
            )
            fallback_title = container_title or heading_text

            for table in container.find_all("table"):
                table_id = id(table)
                if table_id in seen_tables:
                    continue
                seen_tables.add(table_id)
                tables_data.append(table_to_dict(table, fallback_title))

    return tables_data


def scrape_once_caldas() -> dict:
    """Scrape statistics and results tables for Once Caldas."""
    statistics_tables = extract_tables_from_page(
        STATISTICS_URL, ["div.ResponsiveTable"]
    )
    results_tables = extract_tables_from_page(
        RESULTS_URL, ["div.ResponsiveTable.Table__results"]
    )

    return {"estadisticas": statistics_tables, "resultados": results_tables}


@app.route("/")
def index():
    """Serve the static landing page."""
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/scrape", methods=["GET"])
def api_scrape():
    try:
        data = scrape_once_caldas()
        return jsonify(
            {
                "success": True,
                "data": data,
                "total_tablas_estadisticas": len(data.get("estadisticas", [])),
                "total_tablas_resultados": len(data.get("resultados", [])),
            }
        )
    except requests.HTTPError as exc:  # pragma: no cover - defensive path
        return (
            jsonify(
                {
                    "success": False,
                    "error": f"Error al descargar los datos: {exc.response.status_code}",
                }
            ),
            502,
        )
    except requests.RequestException as exc:  # pragma: no cover - defensive path
        return (
            jsonify(
                {
                    "success": False,
                    "error": f"No fue posible conectarse al sitio de ESPN: {exc}",
                }
            ),
            502,
        )
    except Exception as exc:  # pragma: no cover - defensive path
        return jsonify({"success": False, "error": str(exc)}), 500


if __name__ == "__main__":
    print("🚀 Servidor iniciado en http://localhost:5000")
    print("📊 API disponible en http://localhost:5000/api/scrape")
    app.run(debug=True, host="0.0.0.0", port=5000)
