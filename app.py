from __future__ import annotations

import csv
import io
import os
import re
import zipfile
from datetime import datetime
from typing import Iterable

from flask import Flask, jsonify, send_file, send_from_directory
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import unicodedata

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


def _slugify(value: str, default: str) -> str:
    """Generate a safe filename fragment from a heading or table title."""

    normalised = (
        unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    )
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", normalised).strip("-").lower()
    return slug or default


def _table_to_csv(table: dict) -> str:
    """Convert a scraped table dictionary into CSV text."""

    headers: list[str] = table.get("headers") or []
    rows: list[list[str]] = table.get("rows") or []

    column_count = max(
        [len(headers)] + [len(row) for row in rows]
    ) if (headers or rows) else 0

    writer_stream = io.StringIO()
    writer = csv.writer(writer_stream)

    if column_count:
        computed_headers = [
            headers[idx] if idx < len(headers) and headers[idx] else f"Columna {idx + 1}"
            for idx in range(column_count)
        ]
        writer.writerow(computed_headers)

        for row in rows:
            padded_row = [row[idx] if idx < len(row) else "" for idx in range(column_count)]
            writer.writerow(padded_row)

    return writer_stream.getvalue()


def _write_tables_to_zip(zip_file: zipfile.ZipFile, tables: Iterable[dict], folder: str) -> None:
    for index, table in enumerate(tables, start=1):
        title = table.get("title") or f"tabla-{index}"
        slug = _slugify(title, f"tabla-{index}")
        csv_content = _table_to_csv(table)

        filename = f"{folder}/{slug}.csv"
        zip_file.writestr(filename, csv_content or "")


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


@app.route("/api/export/csv", methods=["GET"])
def export_csv():
    try:
        data = scrape_once_caldas()
        buffer = io.BytesIO()

        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zip_file:
            _write_tables_to_zip(zip_file, data.get("estadisticas", []), "estadisticas")
            _write_tables_to_zip(zip_file, data.get("resultados", []), "resultados")

        buffer.seek(0)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"once_caldas_{timestamp}.zip"

        return send_file(
            buffer,
            mimetype="application/zip",
            as_attachment=True,
            download_name=filename,
        )
    except Exception as exc:  # pragma: no cover - defensive path
        return jsonify({"success": False, "error": str(exc)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    host = os.environ.get("HOST", "0.0.0.0")
    debug_env = os.environ.get("FLASK_DEBUG", "false").lower()
    debug_mode = debug_env in {"1", "true", "t", "yes", "y"}
    base_url = f"http://{host}:{port}"
    print(f"🚀 Servidor iniciado en {base_url}")
    print(f"📊 API disponible en {base_url}/api/scrape")
    app.run(debug=debug_mode, host=host, port=port)
