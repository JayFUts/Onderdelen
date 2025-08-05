#!/usr/bin/env python3
"""
Web scraper voor onderdelenlijn.nl
Zoekt auto-onderdelen op basis van kenteken en onderdeelnaam.
"""

import argparse
import sqlite3
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import sys


def setup_database(db_name='onderdelen.db'):
    """
    Maakt verbinding met SQLite database en creëert de parts tabel als deze niet bestaat.
    """
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS parts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            search_license_plate TEXT NOT NULL,
            search_part_name TEXT NOT NULL,
            part_title TEXT,
            price REAL,
            supplier_name TEXT,
            part_condition TEXT,
            warranty_months INTEGER,
            build_year INTEGER,
            engine_code TEXT,
            mileage_km INTEGER,
            source_url TEXT UNIQUE
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✓ Database geïnitialiseerd")


def save_part_data(part_data, db_name='onderdelen.db'):
    """
    Slaat onderdeelgegevens op in de database.
    Gebruikt INSERT OR IGNORE om duplicaten te voorkomen.
    """
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT OR IGNORE INTO parts (
                search_license_plate, search_part_name, part_title,
                price, supplier_name, part_condition, warranty_months,
                build_year, engine_code, mileage_km, source_url
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            part_data.get('search_license_plate'),
            part_data.get('search_part_name'),
            part_data.get('part_title'),
            part_data.get('price'),
            part_data.get('supplier_name'),
            part_data.get('part_condition'),
            part_data.get('warranty_months'),
            part_data.get('build_year'),
            part_data.get('engine_code'),
            part_data.get('mileage_km'),
            part_data.get('source_url')
        ))
        
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        print(f"⚠ Fout bij opslaan: {e}")
        return False
    finally:
        conn.close()


def extract_number(text):
    """
    Extraheert het eerste getal uit een string.
    """
    if not text:
        return None
    match = re.search(r'\d+[\.\,]?\d*', text.replace('.', ''))
    if match:
        return float(match.group().replace(',', '.'))
    return None


def find_part_link(parts_soup, part_name):
    """
    Zoekt de link naar de specifieke onderdelenpagina.
    """
    print(f"→ Stap 3: Zoeken naar link voor '{part_name}'...")
    
    normalized_search = part_name.lower().strip()
    
    # Zoek alle links op de pagina
    all_links = parts_soup.find_all('a', href=True)
    
    # Filter alleen links die naar /auto-onderdelen-voorraad/magazijn/ gaan
    magazijn_links = []
    for link in all_links:
        href = link.get('href', '')
        if '/auto-onderdelen-voorraad/magazijn/' in href and '/onderdeel/' in href:
            link_text = link.get_text(strip=True)
            magazijn_links.append((link_text, href))
    
    print(f"  Gevonden {len(magazijn_links)} onderdeel links")
    
    # Zoek exacte match
    for link_text, href in magazijn_links:
        if link_text.lower() == normalized_search:
            print(f"✓ Exacte match gevonden: {link_text}")
            print(f"  URL: {href}")
            return href
    
    # Als geen exacte match, toon eerste paar links
    print(f"✗ Geen exacte match gevonden voor '{part_name}'")
    if magazijn_links:
        print("  Eerste 5 onderdeel links:")
        for i, (text, href) in enumerate(magazijn_links[:5]):
            print(f"    {i+1}. '{text}'")
    
    return None


def scrape_part_prices(license_plate, part_name):
    """
    Scrapt onderdeelprijzen van onderdelenlijn.nl via een 2-staps proces.
    """
    # Gebruik een session voor cookies en state
    session = requests.Session()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    session.headers.update(headers)
    
    # STAP 1: Haal de zoekpagina op en extraheer ASP.NET viewstate
    print("→ Stap 1: Zoekpagina ophalen...")
    search_url = "https://www.onderdelenlijn.nl/auto-onderdelen-voorraad/zoeken/"
    
    try:
        initial_response = session.get(search_url)
        if initial_response.status_code != 200:
            print(f"⚠ Fout bij ophalen zoekpagina: {initial_response.status_code}")
            return []
    except Exception as e:
        print(f"✗ Fout bij ophalen zoekpagina: {e}")
        return []
    
    # Parse de initiële pagina voor viewstate
    initial_soup = BeautifulSoup(initial_response.text, 'lxml')
    
    # Zoek alle form fields die we moeten meesturen
    form_data = {}
    
    # Viewstate velden
    viewstate = initial_soup.find('input', {'name': '__VIEWSTATE'})
    if viewstate:
        form_data['__VIEWSTATE'] = viewstate.get('value', '')
    
    viewstategenerator = initial_soup.find('input', {'name': '__VIEWSTATEGENERATOR'})
    if viewstategenerator:
        form_data['__VIEWSTATEGENERATOR'] = viewstategenerator.get('value', '')
    
    eventvalidation = initial_soup.find('input', {'name': '__EVENTVALIDATION'})
    if eventvalidation:
        form_data['__EVENTVALIDATION'] = eventvalidation.get('value', '')
    
    # Voeg de kenteken data toe
    form_data['m$mpc$objlicenseplate'] = license_plate.upper().replace('-', '')
    
    # BELANGRIJK: Voeg de submit button naam en waarde toe
    form_data['m$mpc$ctl17'] = 'Gegevens ophalen'
    
    # Debug: print alle form data
    print(f"→ Stap 2: POST request met kenteken {license_plate}...")
    
    try:
        post_response = session.post(search_url, data=form_data, allow_redirects=True)
        print(f"  Response status: {post_response.status_code}")
        
        if post_response.status_code != 200:
            print(f"⚠ POST request mislukt: {post_response.status_code}")
            return []
    except Exception as e:
        print(f"✗ Fout bij POST request: {e}")
        return []
    
    print("✓ Onderdelenlijst ontvangen")
    
    # Parse de HTML response direct
    parts_soup = BeautifulSoup(post_response.text, 'lxml')
    
    # --- DEBUGGING CODE ---
    with open("debug_parts_list.html", "w", encoding="utf-8") as f:
        f.write(post_response.text)
    print("! DEBUG: Onderdelenlijst opgeslagen in debug_parts_list.html")
    # --- EINDE DEBUGGING CODE ---
    
    # STAP 3: Zoek de link naar het specifieke onderdeel
    part_link = find_part_link(parts_soup, part_name)
    
    if not part_link:
        return []
    
    # Maak de volledige URL
    if not part_link.startswith('http'):
        part_url = 'https://www.onderdelenlijn.nl' + part_link
    else:
        part_url = part_link
    
    print(f"→ Stap 4: Resultaten ophalen van {part_url}")
    
    # STAP 4: Haal de uiteindelijke resultatenpagina op
    try:
        response = session.get(part_url)
        if response.status_code != 200:
            print(f"⚠ HTTP Status Code: {response.status_code}")
            return []
    except Exception as e:
        print(f"✗ Fout bij ophalen resultatenpagina: {e}")
        return []
    
    print("✓ Resultatenpagina succesvol opgehaald")
    
    # --- DEBUGGING CODE ---
    with open("debug_output.html", "w", encoding="utf-8") as f:
        f.write(response.text)
    print("! DEBUG: Resultaten opgeslagen in debug_output.html")
    # --- EINDE DEBUGGING CODE ---
    
    print("→ Resultaten parsen...")
    
    # HTML Parsen
    soup = BeautifulSoup(response.text, 'lxml')
    parts = []
    
    # Zoek naar de resultaten - onderdelenlijn gebruikt meestal een tabel structuur
    # Probeer verschillende selectors
    result_items = []
    
    # Methode 1: Zoek naar tabel rijen
    table = soup.find('table', class_=re.compile('result|part|product'))
    if table:
        result_items = table.find_all('tr')[1:]  # Skip header row
        print(f"  Gevonden: {len(result_items)} items in tabel")
    
    # Methode 2: Zoek naar divs met result class
    if not result_items:
        result_items = soup.find_all('div', class_=re.compile('result-item|part-item|product-item'))
        if result_items:
            print(f"  Gevonden: {len(result_items)} result divs")
    
    # Methode 3: Zoek naar articles
    if not result_items:
        result_items = soup.find_all('article', class_=re.compile('product|part'))
        if result_items:
            print(f"  Gevonden: {len(result_items)} articles")
    
    if not result_items:
        print("  ⚠ Geen resultaat items gevonden")
        # Check of er wel prijzen op de pagina staan
        if '€' in response.text or 'EUR' in response.text:
            print("  ℹ Er zijn wel prijzen gevonden, maar de HTML structuur is anders")
    
    for item in result_items:
        try:
            part_data = {
                'search_license_plate': license_plate,
                'search_part_name': part_name
            }
            
            # Titel extraheren
            title_elem = item.find(['h2', 'h3', 'h4'], class_=re.compile('title|name|heading'))
            if not title_elem:
                title_elem = item.find('a', class_=re.compile('product'))
            if title_elem:
                part_data['part_title'] = title_elem.get_text(strip=True)
            
            # Prijs extraheren
            price_elem = item.find(class_=re.compile('price|prijs'))
            if price_elem:
                price_text = price_elem.get_text(strip=True)
                price_value = extract_number(price_text)
                if price_value:
                    part_data['price'] = price_value
            
            # Leverancier extraheren
            supplier_elem = item.find(class_=re.compile('supplier|dealer|aanbieder'))
            if supplier_elem:
                part_data['supplier_name'] = supplier_elem.get_text(strip=True)
            
            # Staat/conditie extraheren
            condition_elem = item.find(string=re.compile('Gebruikt|Nieuw|Gereviseerd'))
            if condition_elem:
                part_data['part_condition'] = condition_elem.strip()
            
            # Garantie extraheren
            warranty_elem = item.find(string=re.compile(r'\d+\s*mnd'))
            if warranty_elem:
                warranty_months = extract_number(warranty_elem)
                if warranty_months:
                    part_data['warranty_months'] = int(warranty_months)
            
            # Bouwjaar extraheren
            year_elem = item.find(string=re.compile(r'20\d{2}|19\d{2}'))
            if year_elem:
                year_match = re.search(r'(20\d{2}|19\d{2})', year_elem)
                if year_match:
                    part_data['build_year'] = int(year_match.group())
            
            # Motorcode extraheren
            engine_elem = item.find(string=re.compile(r'[A-Z]{3,4}'))
            if engine_elem:
                engine_match = re.search(r'[A-Z]{3,4}', engine_elem)
                if engine_match:
                    part_data['engine_code'] = engine_match.group()
            
            # Kilometerstand extraheren
            mileage_elem = item.find(string=re.compile(r'\d+[\.\d]*\s*km'))
            if mileage_elem:
                mileage_value = extract_number(mileage_elem)
                if mileage_value:
                    part_data['mileage_km'] = int(mileage_value)
            
            # Bron URL extraheren
            link_elem = item.find('a', href=True)
            if link_elem:
                href = link_elem['href']
                if not href.startswith('http'):
                    href = 'https://www.onderdelenlijn.nl' + href
                part_data['source_url'] = href
            
            # Alleen toevoegen als we tenminste een titel en prijs hebben
            if part_data.get('part_title') and part_data.get('price'):
                parts.append(part_data)
                
        except Exception as e:
            print(f"⚠ Fout bij parsen van een resultaat: {e}")
            continue
    
    print(f"✓ {len(parts)} onderdelen gevonden")
    return parts


def main():
    """
    Hoofdfunctie die alles samenbrengt.
    """
    parser = argparse.ArgumentParser(
        description='Web scraper voor onderdelenlijn.nl',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='Voorbeeld: python scraper.py 27-XH-VX "Aandrijfas links-voor"'
    )
    
    parser.add_argument(
        'license_plate',
        help='Het kenteken van de auto (bv. 27-XH-VX)'
    )
    parser.add_argument(
        'part_name',
        help='De omschrijving van het onderdeel (bv. "Aandrijfas links-voor")'
    )
    
    args = parser.parse_args()
    
    print(f"\n🔍 Zoeken naar: {args.part_name}")
    print(f"📋 Kenteken: {args.license_plate}\n")
    
    # Database initialiseren
    setup_database()
    
    # Onderdelen scrapen
    parts = scrape_part_prices(args.license_plate, args.part_name)
    
    if not parts:
        print("\n✗ Geen onderdelen gevonden")
        return
    
    # Data opslaan
    print("\n→ Data opslaan...")
    saved_count = 0
    
    for part in parts:
        if save_part_data(part):
            saved_count += 1
            print(f"  ✓ {part.get('part_title', 'Onbekend')} - €{part.get('price', '?')}")
    
    print(f"\n✓ Succesvol {saved_count} onderdelen opgeslagen in onderdelen.db")


if __name__ == '__main__':
    main()