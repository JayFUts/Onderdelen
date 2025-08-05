#!/usr/bin/env python3
"""
Onderdelenlijn.nl scraper - finale versie
Direct naar de juiste URL met modeltype
"""

import argparse
import sqlite3
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import sys
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time


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


def get_modeltype_dynamically(license_plate, driver):
    """
    Haalt het modeltype dynamisch op door het kenteken op te zoeken op de website.
    """
    print(f"→ Modeltype dynamisch ophalen voor kenteken {license_plate}...")
    
    try:
        # Ga naar de hoofdzoekpagina
        search_url = "https://www.onderdelenlijn.nl/auto-onderdelen-voorraad/zoeken/"
        driver.get(search_url)
        
        # Wacht tot de pagina geladen is
        time.sleep(2)
        
        # Verwijder cookie popup eerst
        try:
            cookie_elements = driver.find_elements(By.CSS_SELECTOR, '.cookie-close, #btCloseCookie, .cookies .close, .cookie-banner .close')
            for cookie_elem in cookie_elements:
                if cookie_elem.is_displayed():
                    cookie_elem.click()
                    time.sleep(1)
                    break
        except:
            pass
        
        # Vul het kenteken in
        license_input = driver.find_element(By.NAME, "m$mpc$objlicenseplate")
        license_input.clear()
        license_input.send_keys(license_plate)
        
        # Klik op "Gegevens ophalen" met JavaScript om interception te voorkomen
        submit_button = driver.find_element(By.NAME, "m$mpc$ctl17")
        driver.execute_script("arguments[0].click();", submit_button)
        
        # Wacht op resultaten
        time.sleep(3)
        
        # Zoek naar de result-item met data-type attribuut (dit is het modeltype)
        result_items = driver.find_elements(By.CSS_SELECTOR, ".result-item[data-type]")
        
        if result_items:
            modeltype = result_items[0].get_attribute("data-type")
            print(f"✓ Modeltype gevonden: {modeltype}")
            
            # Extract auto info for debugging
            try:
                car_name = result_items[0].find_element(By.TAG_NAME, "span").text
                print(f"  Auto: {car_name}")
            except:
                pass
                
            return modeltype
        else:
            print("⚠ Geen modeltype gevonden, probeer fallback...")
            return None
            
    except Exception as e:
        print(f"⚠ Fout bij dynamische modeltype lookup: {e}")
        return None


def get_modeltype(license_plate):
    """
    Backward compatibility wrapper - nu wordt dit vervangen door dynamische lookup
    """
    print(f"→ Modeltype ophalen voor kenteken {license_plate}...")
    
    # Fallback mapping voor als dynamische lookup mislukt
    modeltype_map = {
        # Volkswagen Golf V (1K1) 1.6 FSI 16V
        '27-XH-VX': '8601',
        '27XHVX': '8601',
        '27xhvx': '8601',
        
        # Toyota Yaris Verso (P2) 1.3 16V
        '37-LK-BB': '6593',
        '37LKBB': '6593',
        '37lkbb': '6593',
    }
    
    clean_plate = license_plate.upper().replace('-', '').replace(' ', '')
    modeltype = modeltype_map.get(clean_plate, '8601')  # Default naar Volkswagen Golf
    
    print(f"  Fallback modeltype: {modeltype}")
    return modeltype


def setup_webdriver():
    """
    Configureer Chrome WebDriver voor headless browsing
    """
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
    
    try:
        driver = webdriver.Chrome(options=chrome_options)
        return driver
    except Exception as e:
        print(f"✗ Fout bij starten WebDriver: {e}")
        print("  Zorg ervoor dat Chrome en chromedriver geïnstalleerd zijn")
        return None


def scrape_single_page(driver, license_plate, part_name):
    """
    Scrapt een enkele pagina met onderdelen
    """
    # Parse de HTML met BeautifulSoup
    soup = BeautifulSoup(driver.page_source, 'lxml')
    
    # Parse resultaten - nieuwe HTML structuur
    parts = []
    
    # Zoek naar de hoofdlijst met onderdelen
    parts_list_container = soup.find('ul', id='result-list')
    if not parts_list_container:
        print("⚠ Geen resultatenlijst (ul#result-list) gevonden")
        return []
    
    # Elk onderdeel is een 'li' met class 'shoppingcart'
    part_items = parts_list_container.find_all('li', class_='shoppingcart')
    
    if not part_items:
        print("⚠ Resultatenlijst gevonden maar 0 onderdelen")
        return []
    
    print(f"→ {len(part_items)} onderdelen gevonden op deze pagina")
    
    for part_item in part_items:
        try:
            part_data = {
                'search_license_plate': license_plate,
                'search_part_name': part_name
            }
            
            # Titel extraheren
            title_elem = part_item.find('span', class_='bold')
            if title_elem:
                part_data['part_title'] = title_elem.get_text(strip=True)
            
            # Prijs extraheren
            price_elem = part_item.find('span', class_='price')
            if price_elem:
                price_text = price_elem.get_text(strip=True)
                price_value = extract_number(price_text)
                if price_value:
                    part_data['price'] = price_value
            
            # Details extraheren (Bouwjaar, Motorcode, etc.)
            description_div = part_item.find('div', class_='description')
            if description_div:
                # Zoek alle detail items - correcte structuur
                detail_items = description_div.find_all('span', class_='item')
                for item in detail_items:
                    try:
                        # In de HTML is de structuur: <span class="item"><span class="grey">Key</span><span>Value</span></span>
                        spans = item.find_all('span')
                        if len(spans) >= 2:
                            key = spans[0].get_text(strip=True)  # Eerste span is de key (grey)
                            value = spans[1].get_text(strip=True)  # Tweede span is de value
                            
                            # Map specifieke velden
                            if key == 'Bouwjaar':
                                year_value = extract_number(value)
                                if year_value:
                                    part_data['build_year'] = int(year_value)
                            elif key == 'Motorcode':
                                part_data['engine_code'] = value
                            elif key == 'Tellerstand':
                                mileage_value = extract_number(value.replace('km', '').replace('.', ''))
                                if mileage_value:
                                    part_data['mileage_km'] = int(mileage_value)
                    except Exception as detail_error:
                        print(f"    Detail parsing error: {detail_error}")
                        continue
            
            # Leverancier en garantie uit pricing div
            pricing_div = part_item.find('div', class_='pricing')
            if pricing_div:
                # Leverancier - zoek naar "Aanbieder" text gevolgd door span.block
                pricing_text = pricing_div.get_text()
                if 'Aanbieder' in pricing_text:
                    supplier_elem = pricing_div.find('span', class_='block')
                    if supplier_elem:
                        part_data['supplier_name'] = supplier_elem.get_text(strip=True)
                
                # Garantie - zoek naar "Garantie" gevolgd door maanden
                warranty_match = re.search(r'Garantie\s+(\d+)\s*mnd', pricing_text)
                if warranty_match:
                    part_data['warranty_months'] = int(warranty_match.group(1))
            
            # Debug output voor eerste paar items
            if len(parts) < 3:
                print(f"    DEBUG Part {len(parts)+1}: Title='{part_data.get('part_title', 'N/A')}', Price={part_data.get('price', 'N/A')}")
                print(f"    DEBUG Supplier='{part_data.get('supplier_name', 'N/A')}', Year={part_data.get('build_year', 'N/A')}")
                print(f"    DEBUG Full part_data keys: {list(part_data.keys())}")
            
            # URL extraheren uit onclick attribute
            onclick_attr = part_item.get('onclick')
            if onclick_attr and "window.location.href='" in onclick_attr:
                try:
                    link_path = onclick_attr.split("'")[1]
                    part_data['source_url'] = f"https://www.onderdelenlijn.nl{link_path}"
                except:
                    pass
            
            # Conditie bepalen (Gebruikt/Nieuw uit beschrijving)
            if part_data.get('part_title'):
                if 'Gebruikte' in part_data['part_title']:
                    part_data['part_condition'] = 'Gebruikt'
                elif 'Nieuwe' in part_data['part_title']:
                    part_data['part_condition'] = 'Nieuw'
            
            # Alleen toevoegen als we tenminste een prijs hebben
            if part_data.get('price'):
                parts.append(part_data)
                
        except Exception as e:
            print(f"⚠ Fout bij parsen onderdeel: {e}")
            continue
    
    return parts


def scrape_part_prices(license_plate, part_name):
    """
    Scrapt onderdeelprijzen van onderdelenlijn.nl met Selenium en paginatie
    """
    # Formatteer parameters
    formatted_license_plate = license_plate.lower().replace('-', '').replace(' ', '')
    formatted_part_name = part_name.lower().replace(' ', '-')
    
    # Setup WebDriver EERST
    driver = setup_webdriver()
    if not driver:
        return []
    
    # Probeer dynamische modeltype lookup eerst
    modeltype = get_modeltype_dynamically(license_plate, driver)
    
    # Als dynamische lookup mislukt, gebruik fallback
    if not modeltype:
        print("→ Dynamische lookup mislukt, gebruik fallback...")
        modeltype = get_modeltype(license_plate)
    
    # Bouw de directe URL naar de car model page
    url = f"https://www.onderdelenlijn.nl/auto-onderdelen-voorraad/zoeken/kenteken/{formatted_license_plate}/modeltype/{modeltype}/"
    
    print(f"→ Navigeren naar auto model pagina: {url}")
    
    all_parts = []
    page_number = 1
    
    try:
        # Als we dynamische lookup hebben gebruikt, zijn we al op de juiste pagina
        # Anders navigeren we er expliciet naartoe
        current_url = driver.current_url
        if modeltype not in current_url:
            driver.get(url)
            print("✓ Navigatie naar model pagina uitgevoerd")
        else:
            print("✓ Al op de juiste model pagina na dynamische lookup")
        
        print("→ Wachten op JavaScript...")
        
        # Wacht op het laden van de resultaten (max 15 seconden)
        wait = WebDriverWait(driver, 15)
        
        # Wacht tot er prijzen verschijnen of een "geen resultaten" melding
        try:
            wait.until(
                lambda driver: ('€' in driver.page_source and 
                               ('table' in driver.page_source.lower() or 
                                'result' in driver.page_source.lower())) or 
                               'geen resultaten' in driver.page_source.lower() or
                               'gevonden (0)' in driver.page_source.lower()
            )
            
            print("✓ JavaScript content geladen")
            
        except TimeoutException:
            print("⚠ Timeout: JavaScript content niet volledig geladen")
        
        # Extra wachttijd voor volledige rendering
        time.sleep(3)
        
        # Verwijder eventuele cookie popups na navigatie
        try:
            cookie_elements = driver.find_elements(By.CSS_SELECTOR, '.cookie-close, #btCloseCookie, .cookies .close, .cookie-banner .close')
            for cookie_elem in cookie_elements:
                if cookie_elem.is_displayed():
                    cookie_elem.click()
                    print("✓ Cookie popup gesloten na navigatie")
                    time.sleep(1)
                    break
        except:
            pass
        
        # DEBUG: Save the first page
        with open("debug_selenium_output.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print("! DEBUG: Selenium pagina opgeslagen in debug_selenium_output.html")
        
        # UNIVERSELE CHECK: Results page of Category page?
        print("→ Controleren pagina type...")
        results_list = driver.find_elements(By.CSS_SELECTOR, "ul#result-list")
        
        if results_list:
            print("✓ Results page gedetecteerd - direct naar scraping")
        else:
            print("✓ Category page gedetecteerd - zoeken naar part link")
            part_found = False
            
            # Verwijder cookie popup EERST
            try:
                cookie_elements = driver.find_elements(By.CSS_SELECTOR, '.cookie-close, #btCloseCookie, .cookies .close, .cookie-banner .close')
                for cookie_elem in cookie_elements:
                    if cookie_elem.is_displayed():
                        cookie_elem.click()
                        print("✓ Cookie popup gesloten vóór part search")
                        time.sleep(1)
                        break
            except Exception as e:
                print(f"! Cookie popup handling: {e}")
            
            # Zoek naar part categorie link
            print(f"→ Zoeken naar onderdeelcategorie '{part_name}'...")
            
            try:
                # Zoek naar links die de part name bevatten (case-insensitive)
                part_links = driver.find_elements(By.XPATH, f"//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{part_name.lower()}')]")
                
                if not part_links:
                    # Probeer ook met href zoeken
                    formatted_part_name = part_name.lower().replace(' ', '-')
                    part_links = driver.find_elements(By.XPATH, f"//a[contains(@href, '{formatted_part_name}')]")
                
                if part_links:
                    print(f"✓ Gevonden {len(part_links)} mogelijke links voor '{part_name}'")
                    # Klik op de eerste match
                    part_link = part_links[0]
                    print(f"  Klik target: {part_link.get_attribute('title') or part_link.text}")
                    driver.execute_script("arguments[0].scrollIntoView(true);", part_link)
                    time.sleep(1)
                    # Use JavaScript click to avoid interception
                    driver.execute_script("arguments[0].click();", part_link)
                    print("✓ Klik op onderdeelcategorie uitgevoerd")
                    part_found = True
                    time.sleep(3)  # Wacht op nieuwe pagina
                else:
                    print(f"⚠ Geen directe links gevonden voor '{part_name}'")
                    
            except Exception as e:
                print(f"⚠ Fout bij zoeken naar part link: {e}")
            
            if not part_found:
                print("✗ Kon geen geschikte onderdeelcategorie vinden")
                return []
        
        # Check for basic failure cases
        if 'Gevonden (0)' in driver.page_source or 'geen resultaten' in driver.page_source.lower():
            print("✗ Geen resultaten gevonden")
            return []
        
        # Loop door alle pagina's
        while True:
            print(f"→ Pagina {page_number} verwerken...")
            
            # Scrape de huidige pagina
            page_parts = scrape_single_page(driver, license_plate, part_name)
            all_parts.extend(page_parts)
            
            # Zoek naar de "volgende pagina" knop
            try:
                # Eerst cookie popup sluiten als die er nog is
                try:
                    cookie_elements = driver.find_elements(By.CSS_SELECTOR, '.cookie-close, #btCloseCookie')
                    for cookie_elem in cookie_elements:
                        if cookie_elem.is_displayed():
                            cookie_elem.click()
                            time.sleep(1)
                            break
                except:
                    pass
                
                # Zoek naar pagination input met value=">"
                next_button = driver.find_element(By.CSS_SELECTOR, 'input[type="submit"][value=">"]')
                
                # Check of de knop disabled is
                if next_button.get_attribute('disabled'):
                    print("✓ Laatste pagina bereikt")
                    break
                
                print(f"→ Navigeren naar pagina {page_number + 1}...")
                
                # Scroll naar de knop en klik
                driver.execute_script("arguments[0].scrollIntoView(true);", next_button)
                time.sleep(1)
                driver.execute_script("arguments[0].click();", next_button)
                
                # Wacht op nieuwe content
                time.sleep(3)
                page_number += 1
                
                # Voorkom oneindige loops
                if page_number > 100:  # Safety limit
                    print("⚠ Pagina limiet bereikt (100)")
                    break
                    
            except Exception as e:
                print(f"✓ Geen volgende pagina meer gevonden: {e}")
                break
        
    except Exception as e:
        print(f"✗ Fout bij laden pagina: {e}")
        return []
    
    finally:
        # Sluit de browser
        driver.quit()
    
    print(f"✓ Totaal {len(all_parts)} onderdelen met prijzen gevonden over {page_number} pagina(s)")
    return all_parts


def main():
    parser = argparse.ArgumentParser(
        description='Web scraper voor onderdelenlijn.nl',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='Voorbeeld: python scraper_final.py 27-XH-VX "Aandrijfas links-voor"'
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
        print("\n✗ Geen onderdelen met prijzen gevonden")
        return
    
    # Data opslaan
    print(f"\n→ Data opslaan... ({len(parts)} onderdelen)")
    saved_count = 0
    
    for i, part in enumerate(parts):
        print(f"  Poging {i+1}: {part.get('part_title', 'Onbekend')} - €{part.get('price', '?')}")
        if save_part_data(part):
            saved_count += 1
            print(f"    ✓ Succesvol opgeslagen")
        else:
            print(f"    ✗ Opslaan mislukt")
            if i < 3:  # Debug eerste paar mislukte pogingen
                print(f"    DEBUG data: {part}")
    
    print(f"\n✓ Succesvol {saved_count} onderdelen opgeslagen in onderdelen.db")


if __name__ == '__main__':
    main()