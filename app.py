from flask import Flask, jsonify, render_template
from flask_cors import CORS
import csv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time

app = Flask(__name__)
CORS(app)

def get_chrome_driver():
    """Configurar ChromeDriver para local y Vercel"""
    chrome_options = Options()
    chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36')
    
    # Intentar local primero
    chromedriver_path = '/Users/macuser/.wdm/drivers/chromedriver/mac64/141.0.7390.78/chromedriver-mac-x64/chromedriver'
    
    if os.path.exists(chromedriver_path):
        service = Service(chromedriver_path)
        return webdriver.Chrome(service=service, options=chrome_options)
    else:
        # Para Vercel o sistema
        return webdriver.Chrome(options=chrome_options)

def scrape_once_caldas():
    """Función de scraping completa"""
    driver = get_chrome_driver()
    
    data = {"goleadores": [], "asistencias": [], "resultados": []}
    
    try:
        # ESTADÍSTICAS
        driver.get("https://www.espn.com.co/futbol/equipo/estadisticas/_/id/2919/liga/COL.1/temporada/2024")
        wait = WebDriverWait(driver, 15)
        time.sleep(5)
        
        tables = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "table")))
        
        for table in tables:
            try:
                parent = table.find_element(By.XPATH, "./ancestor::section")
                text = parent.text.lower()
                
                tipo = None
                if "goleador" in text:
                    tipo = "goleadores"
                elif "asistencia" in text:
                    tipo = "asistencias"
                else:
                    continue
                
                tbody = table.find_element(By.TAG_NAME, "tbody")
                rows = tbody.find_elements(By.TAG_NAME, "tr")
                
                for row in rows:
                    try:
                        cells = row.find_elements(By.TAG_NAME, "td")
                        if len(cells) >= 3:
                            nombre = cells[1].find_element(By.TAG_NAME, "a").text.strip()
                            juegos = cells[2].text.strip()
                            stat = cells[3].text.strip() if len(cells) > 3 else "0"
                            
                            item = {"nombre": nombre, "juegos": juegos}
                            if tipo == "goleadores":
                                item["goles"] = stat
                            else:
                                item["asistencias"] = stat
                            
                            data[tipo].append(item)
                    except:
                        continue
            except:
                continue
        
        # RESULTADOS
        driver.get("https://www.espn.com.co/futbol/equipo/resultados/_/id/2919/liga/COL.1/temporada/2024")
        time.sleep(5)
        
        table = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table")))
        tbody = table.find_element(By.TAG_NAME, "tbody")
        rows = tbody.find_elements(By.TAG_NAME, "tr")
        
        for row in rows:
            try:
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) >= 3:
                    data["resultados"].append({
                        "fecha": cells[0].text.strip(),
                        "partido": cells[1].text.strip(),
                        "resultado": cells[2].text.strip()
                    })
            except:
                continue
        
    except Exception as e:
        data["error"] = str(e)
    finally:
        driver.quit()
    
    return data

@app.route('/')
def index():
    """Página principal HTML"""
    return render_template('index.html')

@app.route('/api/scrape', methods=['GET'])
def api_scrape():
    """Endpoint API para obtener datos"""
    try:
        data = scrape_once_caldas()
        return jsonify({
            "success": True,
            "data": data,
            "total_goleadores": len(data.get("goleadores", [])),
            "total_asistencias": len(data.get("asistencias", [])),
            "total_resultados": len(data.get("resultados", []))
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/export/csv', methods=['GET'])
def export_csv():
    """Exportar datos y devolver rutas de archivos"""
    try:
        data = scrape_once_caldas()
        
        # Guardar CSVs
        if data["goleadores"]:
            with open('static/once_caldas_goleadores.csv', 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=["nombre", "juegos", "goles"])
                writer.writeheader()
                writer.writerows(data["goleadores"])
        
        if data["asistencias"]:
            with open('static/once_caldas_asistencias.csv', 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=["nombre", "juegos", "asistencias"])
                writer.writeheader()
                writer.writerows(data["asistencias"])
        
        if data["resultados"]:
            with open('static/once_caldas_resultados.csv', 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=["fecha", "partido", "resultado"])
                writer.writeheader()
                writer.writerows(data["resultados"])
        
        return jsonify({
            "success": True,
            "files": {
                "goleadores": "/static/once_caldas_goleadores.csv",
                "asistencias": "/static/once_caldas_asistencias.csv",
                "resultados": "/static/once_caldas_resultados.csv"
            }
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    print("🚀 Servidor iniciado en http://localhost:5000")
    print("📊 API disponible en http://localhost:5000/api/scrape")
    app.run(debug=True, host='0.0.0.0', port=5000)