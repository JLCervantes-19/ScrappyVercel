from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import time

app = Flask(__name__, static_folder='static', template_folder='static')
CORS(app)

def get_chrome_driver():
    """Configurar ChromeDriver para local y Vercel"""
    chrome_options = Options()
    chrome_options.add_argument('--headless')
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
    
    data = {
        "goleadores": [],
        "asistencias": [],
        "resultados": []
    }
    
    try:
        wait = WebDriverWait(driver, 20)
        
        # ========== PARTE 1: ESTADÍSTICAS DE JUGADORES ==========
        print("📊 Extrayendo estadísticas...")
        driver.get("https://www.espn.com.co/futbol/equipo/estadisticas/_/id/2919/liga/COL.1/temporada/2024")
        time.sleep(6)
        
        try:
            # Buscar todas las secciones
            sections = driver.find_elements(By.CSS_SELECTOR, "section.Card")
            
            for section in sections:
                try:
                    # Identificar tipo de estadística
                    header = section.find_element(By.CSS_SELECTOR, "h2, h3").text.lower()
                    
                    tipo = None
                    if "goleador" in header:
                        tipo = "goleadores"
                    elif "asistencia" in header:
                        tipo = "asistencias"
                    else:
                        continue
                    
                    print(f"  → Procesando {tipo}...")
                    
                    # Buscar la tabla
                    table = section.find_element(By.TAG_NAME, "table")
                    tbody = table.find_element(By.TAG_NAME, "tbody")
                    rows = tbody.find_elements(By.TAG_NAME, "tr")
                    
                    for row in rows:
                        try:
                            cells = row.find_elements(By.TAG_NAME, "td")
                            if len(cells) >= 3:
                                # Nombre del jugador
                                try:
                                    nombre = cells[1].find_element(By.TAG_NAME, "a").text.strip()
                                except:
                                    nombre = cells[1].text.strip()
                                
                                if not nombre:
                                    continue
                                
                                # Juegos jugados
                                juegos = cells[2].text.strip()
                                
                                # Goles o Asistencias (columna 3)
                                stat_value = cells[3].text.strip() if len(cells) > 3 else "0"
                                
                                if tipo == "goleadores":
                                    data["goleadores"].append({
                                        "nombre": nombre,
                                        "juegos": juegos,
                                        "goles": stat_value
                                    })
                                else:
                                    data["asistencias"].append({
                                        "nombre": nombre,
                                        "juegos": juegos,
                                        "asistencias": stat_value
                                    })
                        except Exception as e:
                            continue
                    
                    print(f"    ✓ {len(data[tipo])} registros extraídos")
                    
                except Exception as e:
                    continue
                    
        except Exception as e:
            print(f"❌ Error en estadísticas: {e}")
        
        # ========== PARTE 2: RESULTADOS DE PARTIDOS ==========
        print("\n📅 Extrayendo resultados...")
        driver.get("https://www.espn.com.co/futbol/equipo/resultados/_/id/2919/temporada/2024")
        time.sleep(6)
        
        try:
            # Scroll para cargar todos los partidos
            for _ in range(3):
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
            
            # Buscar secciones por mes
            sections = driver.find_elements(By.CSS_SELECTOR, "section.Card")
            
            for section in sections:
                try:
                    # Verificar si tiene una tabla de resultados
                    table = section.find_element(By.TAG_NAME, "table")
                    tbody = table.find_element(By.TAG_NAME, "tbody")
                    rows = tbody.find_elements(By.TAG_NAME, "tr")
                    
                    for row in rows:
                        try:
                            cells = row.find_elements(By.TAG_NAME, "td")
                            
                            if len(cells) >= 3:
                                # Fecha
                                fecha = cells[0].text.strip()
                                
                                # Equipos (buscar dentro de la celda)
                                partido_cell = cells[1]
                                
                                # Intentar extraer equipos
                                try:
                                    equipos_links = partido_cell.find_elements(By.TAG_NAME, "a")
                                    if len(equipos_links) >= 2:
                                        equipo1 = equipos_links[0].text.strip()
                                        equipo2 = equipos_links[1].text.strip()
                                        partido = f"{equipo1} vs {equipo2}"
                                    else:
                                        partido = partido_cell.text.strip().replace('\n', ' vs ')
                                except:
                                    partido = partido_cell.text.strip().replace('\n', ' vs ')
                                
                                # Resultado
                                resultado = cells[2].text.strip()
                                
                                # Validar que tenga datos
                                if fecha and partido and resultado:
                                    data["resultados"].append({
                                        "fecha": fecha,
                                        "partido": partido,
                                        "resultado": resultado
                                    })
                        except Exception as e:
                            continue
                            
                except Exception as e:
                    continue
            
            print(f"  ✓ {len(data['resultados'])} partidos extraídos")
                    
        except Exception as e:
            print(f"❌ Error en resultados: {e}")
        
    except Exception as e:
        print(f"❌ Error general: {e}")
        data["error"] = str(e)
    
    finally:
        driver.quit()
    
    return data

@app.route('/')
def index():
    """Página principal"""
    return send_from_directory('static', 'index.html')

@app.route('/api/scrape', methods=['GET'])
def api_scrape():
    """Endpoint principal de scraping"""
    try:
        print("\n🚀 Iniciando scraping...")
        data = scrape_once_caldas()
        
        return jsonify({
            "success": True,
            "data": data,
            "total_goleadores": len(data.get("goleadores", [])),
            "total_asistencias": len(data.get("asistencias", [])),
            "total_resultados": len(data.get("resultados", []))
        })
    except Exception as e:
        print(f"❌ Error en API: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health():
    """Health check para Vercel"""
    return jsonify({"status": "ok", "message": "API Once Caldas funcionando"})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 Servidor iniciado en http://localhost:{port}")
    print(f"📊 API disponible en http://localhost:{port}/api/scrape")
    app.run(debug=True, host='0.0.0.0', port=port)
