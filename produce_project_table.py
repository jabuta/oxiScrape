import os
import re
import html
import json
import requests
import unicodedata
import pandas as pd
from bs4 import BeautifulSoup

#########################
# CONFIG / CONSTANTS
#########################
MAIN_HTML = "projects_main.html"
OUTPUT_CSV = "final_projects.csv"
# The base URL for detail pages. Adjust if needed:
DETAIL_BASE_URL = "https://obrasporimpuestos.renovacionterritorio.gov.co/ObrasImpuestos/_DetalleProyecto?idProyecto="

#########################
# 1) PARSE MAIN TABLE
#########################
def parse_main_table(html_content):
    """
    Parse the main HTML (with <table id='_tblProyecto'>) 
    to get at least the UUID for each project. 
    You can also keep other columns like 'Nombre', 'Costo', 'Sector', etc.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    table = soup.find("table", id="_tblProyecto")
    if not table:
        print("Table with id='_tblProyecto' not found in main HTML.")
        return pd.DataFrame()
    
    projects = []
    tbody = table.find("tbody")
    if not tbody:
        print("No <tbody> found in main table.")
        return pd.DataFrame()
    
    for tr in tbody.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 9:
            continue
        
        # Basic columns from main table
        project = {
            "PROYECTOID": tds[0].get_text(strip=True),
            "Codigo": tds[1].get_text(strip=True),
            "Nombre_main": tds[2].get_text(strip=True),
            "Costo_main": tds[3].get_text(strip=True),
            "Sector_main": tds[4].get_text(strip=True),
            "Localizacion_main": tds[5].get_text(strip=True),
            "Clasificacion_main": tds[6].get_text(strip=True),
            "UUID": ""
        }
        
        # Attempt to grab the UUID from onclick
        detail_btn = tds[8].find("button", title="Ver Detalle")
        if detail_btn and "onclick" in detail_btn.attrs:
            onclick = detail_btn["onclick"]
            match = re.search(r"VerDetalleProyecto\('([^']+)'\)", onclick)
            if match:
                project["UUID"] = match.group(1)
        
        projects.append(project)
    
    df = pd.DataFrame(projects)
    return df

#########################
# 2) PARSE DETAIL PAGE
#########################
def parse_detail_page(html_content):
    """
    Parse the detail HTML for fields like:
    BPIN, Nombre_det, Objetivo, Costo_det, Beneficiarios, 
    FechaViabilizacion, Sector_det, Preinversion, Clasificacion_det,
    plus the table of location data (_tblDetallePryecto).
    """
    soup = BeautifulSoup(html_content, "lxml")

    def get_input_value(input_id):
        tag = soup.find("input", id=input_id)
        if tag and tag.has_attr("value"):
            return tag["value"].strip()
        return ""
    
    detail = {
        "BPIN": get_input_value("_CODIGOBPIN"),
        "Nombre_det": "",
        "Objetivo": "",
        "Costo_det": get_input_value("_COSTO"),
        "Beneficiarios": get_input_value("_BENEFICIARIOS"),
        "FechaViabilizacion": get_input_value("_FECHAVIABILIZACION"),
        "Sector_det": get_input_value("_SECTOR"),
        "Preinversion": get_input_value("_PREINVERSION"),
        "Clasificacion_det": get_input_value("_CLASIFICACION"),
        "LocTableHTML": "",
        "LocationData": []
    }
    
    # Nombre_det
    nombre_textarea = soup.find("textarea", id="_NOMBREPROYECTO")
    if nombre_textarea:
        detail["Nombre_det"] = html.unescape(nombre_textarea.get_text(strip=True))
    
    # Objetivo
    objetivo_textarea = soup.find("textarea", id="_DESCRIPCION")
    if objetivo_textarea:
        detail["Objetivo"] = html.unescape(objetivo_textarea.get_text(strip=True))

    # Extract location table
    loc_table = soup.find("table", id="_tblDetallePryecto")
    if loc_table:
        # We'll replace the class with "ubicacion-proyecto" so that 
        # the final output matches your sample's <table class="ubicacion-proyecto"> 
        # if you want the exact same HTML signature.
        loc_table["class"] = ["ubicacion-proyecto"]
        
        detail["LocTableHTML"] = str(loc_table)
        
        tbody = loc_table.find("tbody")
        if tbody:
            for tr in tbody.find_all("tr"):
                tds = tr.find_all("td")
                if len(tds) >= 3:
                    dept = tds[0].get_text(strip=True)
                    dane = tds[1].get_text(strip=True)
                    muni = tds[2].get_text(strip=True)
                    detail["LocationData"].append([dept, dane, muni])
    
    return detail

#########################
# 3) TRANSFORMATION
#########################
def remove_accents_and_lower(text):
    # Example: remove accents, convert to lowercase
    nfkd = unicodedata.normalize("NFD", text)
    without_accents = nfkd.encode("ascii", "ignore").decode("utf-8", "ignore")
    return without_accents.lower()

def create_slug(text):
    # Convert to a slug (lowercase, remove punctuation, spaces->hyphens)
    text = text.strip()
    # Remove accents
    text = remove_accents_and_lower(text)
    # Remove everything but alphanumeric, spaces, hyphens
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    # Replace spaces with hyphens
    text = re.sub(r"\s+", "-", text)
    # Remove repeated hyphens
    text = re.sub(r"-+", "-", text)
    return text

def correct_text_basic(text):
    # A simple demonstration of "correcting" text: 
    # - strip 
    # - unify spacing 
    # - maybe fix capitalization 
    if not text:
        return ""
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    # Make first letter uppercase, as an example
    return text[0].upper() + text[1:] if text else text

def build_jsonld(dept, dane, municipality):
    """
    Build a JSON-LD snippet for the first location row. 
    If you want multiple, adapt as needed.
    """
    if not dept:
        dept = ""
    if not municipality:
        municipality = ""
    # Example uses the same structure you provided, with escapable quotes
    data = {
        "@context": "https://schema.org",
        "@type": "Place",
        "address": {
            "@type": "PostalAddress",
            "addressLocality": municipality,
            "addressRegion": dept,
            "identifier": {
                "@type": "PropertyValue",
                "propertyID": "divipola",
                "value": dane
            }
        }
    }
    # We'll return it as a JSON string
    return json.dumps(data, ensure_ascii=False, indent=2)

#########################
# 4) BUILD FINAL ROW
#########################
def build_final_csv_row(idx, detail):
    """
    Combine fields from 'detail' to produce a row that 
    matches your final CSV structure:

    Index,BPIN,Name,name Corr,Meta Title,SLUG,Objective,
    Objective Corrected,Cost,Beneficiaries,Viabilization Date,
    Sector,Sector Corr,Preinvestment Costs,Classification,
    Location Data,LOC TABLE,Deptos,Jsonld
    """
    # Grab raw fields from detail
    bpin = detail["BPIN"]
    raw_name = detail["Nombre_det"]
    raw_objective = detail["Objetivo"]
    raw_cost = detail["Costo_det"]
    raw_benef = detail["Beneficiarios"]
    raw_fecha = detail["FechaViabilizacion"]
    raw_sector = detail["Sector_det"]
    raw_preinv = detail["Preinversion"]
    raw_clasif = detail["Clasificacion_det"]
    loc_data = detail["LocationData"]
    loc_table_html = detail["LocTableHTML"]

    # name Corr (some "correction" to your raw name)
    # For demonstration, let's just replicate your example:
    name_corr = correct_text_basic(raw_name)

    # Meta Title: You can define any logic. 
    # For demonstration, let's just make it "Short Headline for <name_corr>":
    meta_title = "Short headline: " + name_corr
    # But if you want EXACT text as in your sample CSV, you'd do so manually.

    # SLUG
    slug = create_slug(name_corr)

    # Objective Corrected
    objective_corr = correct_text_basic(raw_objective)

    # Sector Corr
    sector_corr = correct_text_basic(raw_sector)

    # Build "Location Data" as a string, e.g. "[['Dept','DANE','Muni'],...]"
    location_data_str = str(loc_data)

    # Deptos: if multiple, might join them with commas or pick the first one
    dept_set = {row[0] for row in loc_data}
    deptos_str = ", ".join(sorted(dept_set))

    # JSON-LD: pick first row if available
    jsonld_str = ""
    if loc_data:
        first_dept, first_dane, first_muni = loc_data[0]
        jsonld_str = build_jsonld(first_dept, first_dane, first_muni)

    # Return a dict in the EXACT order of columns you want
    return {
        "Index": idx,
        "BPIN": bpin,
        "Name": raw_name,
        "name Corr": name_corr,
        "Meta Title": meta_title,
        "SLUG": slug,
        "Objective": raw_objective,
        "Objective Corrected": objective_corr,
        "Cost": raw_cost,
        "Beneficiaries": raw_benef,
        "Viabilization Date": raw_fecha,
        "Sector": raw_sector,
        "Sector Corr": sector_corr,
        "Preinvestment Costs": raw_preinv,
        "Classification": raw_clasif,
        "Location Data": location_data_str,
        "LOC TABLE": loc_table_html,
        "Deptos": deptos_str,
        "Jsonld": jsonld_str
    }

#########################
# 5) MAIN FLOW
#########################
def main():
    # Step A: Read the main HTML
    if not os.path.exists(MAIN_HTML):
        print(f"Cannot find {MAIN_HTML}")
        return
    
    with open(MAIN_HTML, "r", encoding="utf-8") as f:
        main_html_content = f.read()
    
    df_main = parse_main_table(main_html_content)
    if df_main.empty:
        print("No projects found in main HTML. Exiting.")
        return
    
    print(f"Found {len(df_main)} projects in main table.")

    final_rows = []
    
    # Step B: For each row, fetch detail data
    for idx, row in df_main.iterrows():
        uuid_ = row.get("UUID", "")
        if not uuid_:
            print(f"[{idx}] No UUID found, skipping.")
            continue
        
        detail_url = DETAIL_BASE_URL + uuid_
        print(f"[{idx}] Fetching {detail_url}")
        
        try:
            resp = requests.get(detail_url, verify=False, timeout=15)
            if resp.status_code == 200:
                detail_data = parse_detail_page(resp.text)
                # Build the final row structure
                final_row = build_final_csv_row(idx, detail_data)
                final_rows.append(final_row)
            else:
                print(f"[{idx}] Error {resp.status_code} fetching detail for UUID={uuid_}")
        except Exception as ex:
            print(f"[{idx}] Exception fetching detail for {uuid_}: {ex}")
            
    
    if not final_rows:
        print("No detail data retrieved. Exiting.")
        return

    # Step C: Create DataFrame with columns in your exact order
    final_columns = [
        "Index", "BPIN", "Name", "name Corr", "Meta Title", "SLUG",
        "Objective", "Objective Corrected", "Cost", "Beneficiaries",
        "Viabilization Date", "Sector", "Sector Corr", "Preinvestment Costs",
        "Classification", "Location Data", "LOC TABLE", "Deptos", "Jsonld"
    ]
    df_final = pd.DataFrame(final_rows, columns=final_columns)

    # Step D: Write to CSV
    df_final.to_csv(OUTPUT_CSV, index=False, encoding="utf-8")
    print(f"\nDone! Final CSV is written to {OUTPUT_CSV}.")

if __name__ == "__main__":
    main()
