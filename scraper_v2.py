#!/usr/bin/env python3
"""
Alternatieve versie van de scraper die direct naar de onderdelen URL gaat
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


def scrape_part_prices(license_plate, part_name):
    """
    Probeert direct de onderdelen URL te benaderen
    """
    # Formatteer de URL parameters
    formatted_license_plate = license_plate.lower().replace('-', '').replace(' ', '')
    formatted_part_name = part_name.lower().replace(' ', '-')
    
    # Probeer verschillende URL formats
    urls_to_try = [
        f"https://www.onderdelenlijn.nl/auto-onderdelen-voorraad/magazijn/kenteken/{formatted_license_plate}/onderdeel/{formatted_part_name}/",
        f"https://www.onderdelenlijn.nl/auto-onderdelen/{formatted_license_plate}/{formatted_part_name}/",
        f"https://www.onderdelenlijn.nl/onderdelen/{formatted_license_plate}/{formatted_part_name}/"
    ]
    
    session = requests.Session()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    session.headers.update(headers)
    
    for url in urls_to_try:
        print(f"→ Probeer URL: {url}")
        
        try:
            response = session.get(url, allow_redirects=True)
            print(f"  Status: {response.status_code}, Final URL: {response.url}")
            
            if response.status_code == 200:
                # Check of we resultaten hebben
                soup = BeautifulSoup(response.text, 'lxml')
                
                # Zoek naar indicatoren van resultaten
                if ('resultaten gevonden' in response.text or 
                    'onderdelen gevonden' in response.text or
                    'class="price"' in response.text or
                    'class="prijs"' in response.text):
                    
                    print("✓ Mogelijk resultaten gevonden!")
                    
                    # Save debug output
                    with open("debug_results.html", "w", encoding="utf-8") as f:
                        f.write(response.text)
                    print("! DEBUG: Resultaten opgeslagen in debug_results.html")
                    
                    # Parse resultaten
                    parts = parse_results(soup, license_plate, part_name)
                    if parts:
                        return parts
                        
        except Exception as e:
            print(f"  Fout: {e}")
            continue
    
    print("✗ Geen werkende URL gevonden")
    return []


def parse_results(soup, license_plate, part_name):
    """
    Parse de resultatenpagina voor onderdelen
    """
    parts = []
    
    # Probeer verschillende selectors voor resultaat items
    selectors = [
        ('div', {'class': 'result-item'}),
        ('div', {'class': 'part-item'}),
        ('article', {'class': 'product'}),
        ('div', {'class': 'listing'}),
        ('tr', {'class': 'part-row'}),
        ('div', {'class': re.compile('result|item|product|part', re.I)})
    ]
    
    result_items = []
    for tag, attrs in selectors:
        items = soup.find_all(tag, attrs)
        if items:
            result_items = items
            print(f"  Gevonden {len(items)} items met selector {tag}, {attrs}")
            break
    
    if not result_items:
        print("  Geen resultaat items gevonden")
        return []
    
    for item in result_items:
        try:
            part_data = {
                'search_license_plate': license_plate,
                'search_part_name': part_name
            }
            
            # Zoek prijs
            price_elem = item.find(class_=re.compile('price|prijs', re.I))
            if not price_elem:
                price_elem = item.find(string=re.compile(r'€\s*\d+'))
            if price_elem:
                price_text = price_elem.get_text(strip=True) if hasattr(price_elem, 'get_text') else str(price_elem)
                price_value = extract_number(price_text)
                if price_value:
                    part_data['price'] = price_value
            
            # Zoek titel
            title_elem = item.find(['h2', 'h3', 'h4', 'a'], class_=re.compile('title|name|heading', re.I))
            if title_elem:
                part_data['part_title'] = title_elem.get_text(strip=True)
            
            # Alleen toevoegen als we tenminste een prijs hebben
            if part_data.get('price'):
                parts.append(part_data)
                print(f"  ✓ Onderdeel: {part_data.get('part_title', 'Onbekend')} - €{part_data.get('price')}")
                
        except Exception as e:
            continue
    
    return parts


def main():
    parser = argparse.ArgumentParser(
        description='Alternatieve web scraper voor onderdelenlijn.nl'
    )
    
    parser.add_argument('license_plate', help='Het kenteken van de auto')
    parser.add_argument('part_name', help='De omschrijving van het onderdeel')
    
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
    print(f"\n→ Gevonden {len(parts)} onderdelen, bezig met opslaan...")
    saved_count = 0
    
    for part in parts:
        if save_part_data(part):
            saved_count += 1
    
    print(f"✓ {saved_count} onderdelen opgeslagen in onderdelen.db")


if __name__ == '__main__':
    main()