#!/usr/bin/env python3
"""
OnderdelenLijn.nl Scraper - Complete implementatie
Automatische auto-onderdelen scraper met dynamische kenteken detectie
"""

import json
import time
import re
import argparse
import logging
import sys
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from bs4 import BeautifulSoup

# Configureer logging om naar de console (stdout) te schrijven
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - SCRAPER - %(levelname)s - %(message)s',
    stream=sys.stdout  # Zorgt ervoor dat het in Railway logs verschijnt
)


class OnderdelenLijnScraper:
    """
    Robuuste scraper voor onderdelenlijn.nl met dynamische kenteken detectie
    """
    
    def __init__(self, headless=True, timeout=15):
        """
        Initialiseer de scraper
        
        Args:
            headless (bool): Run browser in headless mode
            timeout (int): WebDriver timeout in seconds
        """
        self.timeout = timeout
        self.wait = None
        self.driver = None
        self.base_url = "https://www.onderdelenlijn.nl"
        self.search_url = f"{self.base_url}/auto-onderdelen-voorraad/zoeken/"
        
        # Setup WebDriver
        self._setup_driver(headless)
    
    def _setup_driver(self, headless):
        """
        Configureer Chrome WebDriver met optimale instellingen
        """
        chrome_options = Options()
        
        if headless:
            chrome_options.add_argument('--headless')
        
        # Performance en reliability optimalisaties - ESSENTIEEL voor Railway/Docker
        chrome_options.add_argument('--no-sandbox')  # Essentieel voor Railway/Docker
        chrome_options.add_argument('--disable-dev-shm-usage')  # Essentieel voor Railway/Docker  
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Timeouts voor productie omgeving
        chrome_options.add_argument('--page-load-strategy=eager')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-plugins')
        chrome_options.add_argument('--disable-images')  # Sneller laden
        chrome_options.add_argument('--aggressive-cache-discard')
        chrome_options.add_argument('--memory-pressure-off')
        
        # Cloud container optimalisaties  
        chrome_options.add_argument('--max_old_space_size=2048')
        chrome_options.add_argument('--disable-background-timer-throttling')
        chrome_options.add_argument('--disable-renderer-backgrounding')
        
        # Extra Railway.app compatibility
        chrome_options.add_argument('--disable-software-rasterizer')
        chrome_options.add_argument('--disable-background-networking')
        chrome_options.add_argument('--disable-default-apps')
        chrome_options.add_argument('--disable-sync')
        chrome_options.add_argument('--metrics-recording-only')
        chrome_options.add_argument('--no-first-run')
        chrome_options.add_argument('--safebrowsing-disable-auto-update')
        chrome_options.add_argument('--disable-web-security')
        chrome_options.add_argument('--allow-running-insecure-content')
        
        # ENHANCED User-Agent voor bot detectie vermijding - modern en common
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0')
        
        # Additional bot detection avoidance
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        try:
            logging.info("Installing ChromeDriver...")
            driver_path = ChromeDriverManager().install()
            logging.info(f"ChromeDriver path: {driver_path}")
            
            service = Service(driver_path)
            logging.info("Creating Chrome WebDriver...")
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Set server-compatible timeouts
            self.driver.set_page_load_timeout(self.timeout)
            self.driver.implicitly_wait(10)  # 10 seconds implicit wait
            
            logging.info("Setting up WebDriver properties...")
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.wait = WebDriverWait(self.driver, self.timeout)
            logging.info("WebDriver geïnitialiseerd met timeouts")
        except Exception as e:
            logging.error(f"Fout bij WebDriver setup: {e}", exc_info=True)
            raise
    
    def _handle_cookies(self):
        """
        Universele cookie popup handler
        """
        cookie_selectors = [
            '.cookie-close',
            '#btCloseCookie', 
            '.cookies .close',
            '.cookie-banner .close',
            '[class*="cookie"] [class*="close"]',
            '[class*="cookie"] [class*="accept"]'
        ]
        
        for selector in cookie_selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for element in elements:
                    if element.is_displayed() and element.is_enabled():
                        self.driver.execute_script("arguments[0].click();", element)
                        logging.info("Cookie popup gesloten")
                        time.sleep(1)
                        return True
            except Exception:
                continue
        return False
    
    def _debug_save_artifacts(self, error_type, part_name=None):
        """
        CRITICAL DEBUG FUNCTION: Save screenshot and page source when issues occur
        This helps diagnose bot detection, CAPTCHAs, unexpected popups, or layout changes
        """
        import os
        timestamp = time.strftime('%Y%m%d_%H%M%S')
        
        try:
            # MOST IMPORTANT: Save screenshot to see what the browser actually shows
            screenshot_name = f"debug_screenshot_{error_type}_{timestamp}.png"
            self.driver.save_screenshot(screenshot_name)
            logging.error(f"  🖼️ DEBUG: Screenshot saved as {screenshot_name}")
            
            # Save page source to analyze HTML structure
            page_source_name = f"debug_page_source_{error_type}_{timestamp}.html"
            with open(page_source_name, 'w', encoding='utf-8') as f:
                f.write(self.driver.page_source)
            logging.error(f"  📄 DEBUG: Page source saved as {page_source_name}")
            
            # Log current URL and basic info
            current_url = self.driver.current_url
            page_title = self.driver.title
            logging.error(f"  🌐 DEBUG: Current URL: {current_url}")
            logging.error(f"  📝 DEBUG: Page title: {page_title}")
            
            if part_name:
                logging.error(f"  🔍 DEBUG: Searching for part: {part_name}")
            
            # Log window size and viewport
            window_size = self.driver.get_window_size()
            logging.error(f"  📏 DEBUG: Window size: {window_size}")
            
        except Exception as e:
            logging.error(f"  ❌ DEBUG: Failed to save artifacts: {e}")
        
        logging.error("  💡 DEBUG: Check the saved screenshot and HTML file to diagnose the issue")
    
    def get_modeltype_dynamically(self, license_plate):
        """
        Dynamische kenteken lookup voor modeltype detectie
        
        Args:
            license_plate (str): Auto kenteken
            
        Returns:
            str: Modeltype ID of None bij falen
        """
        logging.info(f"Modeltype dynamisch ophalen voor kenteken {license_plate}...")
        
        try:
            # Navigeer naar zoekpagina
            self.driver.get(self.search_url)
            
            # Wait for page to load and handle cookies
            self.wait.until(EC.presence_of_element_located((By.ID, "objlicenseplate")))
            self._handle_cookies()
            
            # Vul kenteken in
            license_input = self.wait.until(
                EC.element_to_be_clickable((By.ID, "objlicenseplate"))
            )
            license_input.clear()
            license_input.send_keys(license_plate)
            
            # Submit met JavaScript voor reliability
            submit_button = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[type='submit'][value='Gegevens ophalen']")))
            self.driver.execute_script("arguments[0].click();", submit_button)
            
            # Wait for results to appear instead of fixed sleep
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".result-item, .search-results-list")))
            
            # Zoek naar result-item met data-type attribuut
            result_items = self.driver.find_elements(By.CSS_SELECTOR, ".result-item[data-type]")
            
            if result_items:
                modeltype = result_items[0].get_attribute("data-type")
                
                # Extract auto info
                try:
                    car_name = result_items[0].find_element(By.TAG_NAME, "span").text
                    logging.info(f"Modeltype gevonden: {modeltype}")
                    logging.info(f"Auto: {car_name}")
                except:
                    logging.info(f"Modeltype gevonden: {modeltype}")
                
                # De website navigeert automatisch naar de onderdelenlijst
                logging.info("Op onderdelenlijst pagina")
                
                return modeltype
            else:
                logging.warning("Geen modeltype gevonden")
                return None
                
        except Exception as e:
            logging.error(f"Fout bij dynamische modeltype lookup: {e}", exc_info=True)
            return None
    
    def detect_page_type(self):
        """
        Detecteer of we op een results page of category page zijn
        
        Returns:
            str: 'results' of 'category'
        """
        # Check voor results list
        results_list = self.driver.find_elements(By.CSS_SELECTOR, "ul#result-list")
        
        if results_list:
            logging.info("Results page gedetecteerd")
            return 'results'
        else:
            logging.info("Category page gedetecteerd")
            return 'category'
    
    def find_category_urls(self, part_name):
        """
        Vind alle categorie URLs die matchen met part_name uit search-results-list
        
        Args:
            part_name (str): Onderdeel naam om te zoeken
            
        Returns:
            list: Lijst van (category_name, url) tuples
        """
        logging.info(f"→ Zoeken naar categorieën voor '{part_name}'...")
        
        # Handle cookies eerst
        self._handle_cookies()
        
        category_urls = []
        
        try:
            # ROBUST MULTI-STAGE WAITING STRATEGY
            part_lower = part_name.lower()
            
            # STAGE 1: Wait for the main container to exist (confirms page structure loaded)
            logging.info(f"  🔍 STAGE 1: Wachten op search-results-list container...")
            container_wait = WebDriverWait(self.driver, 20)  # Longer wait for container
            
            try:
                container = container_wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div.search-results-list, div[class*='search-results-list']"))
                )
                logging.info(f"  ✅ STAGE 1: Container gevonden - pagina structuur geladen")
                
                # Give dynamic content time to populate
                time.sleep(2)
                
            except TimeoutException:
                logging.error("  ❌ STAGE 1 FAILED: Container niet gevonden - mogelijk bot detection of andere pagina")
                self._debug_save_artifacts("stage1_container_timeout")
                return []
            
            # STAGE 2: Now search for specific links within the confirmed container
            logging.info(f"  🔍 STAGE 2: Zoeken naar specifieke links voor '{part_name}'...")
            
            # Optimized XPath patterns focusing on confirmed container
            xpath_patterns = [
                # MOST RELIABLE: Search within confirmed container using title attribute
                f"//div[contains(@class, 'search-results-list')]//a[contains(translate(@title, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{part_lower}')]",
                
                # RELIABLE: Search within container using span text
                f"//div[contains(@class, 'search-results-list')]//a[contains(translate(span/text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{part_lower}')]",
                
                # FUZZY: Match without 's' (Velg vs Velgen)
                f"//div[contains(@class, 'search-results-list')]//a[contains(translate(@title, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{part_lower.rstrip('s')}')]",
                
                # FUZZY: Match without 'en' (Velg vs Velgen)
                f"//div[contains(@class, 'search-results-list')]//a[contains(translate(@title, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{part_lower.rstrip('en')}')]",
                
                # BROAD FALLBACK: Any link with keyword
                f"//a[contains(translate(@title, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{part_lower}')]"
            ]
            
            matching_links = []
            start_time = time.time()
            
            # Stage 2: Search for specific links with shorter timeout (container already confirmed)
            pattern_wait = WebDriverWait(self.driver, 10)
            
            for i, xpath_pattern in enumerate(xpath_patterns):
                try:
                    logging.info(f"  🔍 STAGE 2 Patroon {i+1}/{len(xpath_patterns)}: Specifieke link zoektocht...")
                    
                    # Search within confirmed container structure
                    matches = pattern_wait.until(EC.presence_of_all_elements_located((By.XPATH, xpath_pattern)))
                    
                    if matches:
                        elapsed = time.time() - start_time
                        matching_links = matches
                        logging.info(f"  ⚡ STAGE 2 SUCCESS: {len(matching_links)} links gevonden in {elapsed:.2f}s (patroon {i+1})")
                        break
                        
                except TimeoutException:
                    elapsed = time.time() - start_time
                    logging.info(f"  ⏱️ Patroon {i+1}: Timeout na {elapsed:.2f}s - probeer volgende patroon")
                    continue
                except Exception as e:
                    logging.error(f"  ❌ Patroon {i+1}: Unexpected error - {e}")
                    continue
            
            # If no matches found after all patterns, perform debugging
            if not matching_links:
                logging.error(f"  ❌ STAGE 2 FAILED: Geen matches gevonden voor '{part_name}' - debug artifacts worden opgeslagen")
                self._debug_save_artifacts("stage2_no_matches", part_name)
                return []
            
            for link in matching_links:
                try:
                    href = link.get_attribute('href')
                    title = link.get_attribute('title') or link.text.strip()
                    
                    if href and 'onderdeel' in href:
                        # Maak volledige URL
                        if not href.startswith('http'):
                            href = self.base_url + href
                        
                        category_urls.append((title, href))
                        
                except Exception as e:
                    continue
            
            logging.info(f"✓ Gevonden {len(category_urls)} categorie(s) voor '{part_name}'")
            for i, (title, url) in enumerate(category_urls[:3], 1):
                logging.info(f"  {i}. {title}")
            
            return category_urls
            
        except Exception as e:
            logging.info(f"⚠ Fout bij categorie zoeken: {e}")
            return []
    
    def extract_part_data(self, soup, search_info):
        """
        Extraheer onderdeel data uit BeautifulSoup object
        
        Args:
            soup: BeautifulSoup object van de pagina
            search_info: Dict met search metadata
            
        Returns:
            list: Lijst van part dictionaries
        """
        parts = []
        
        # Zoek onderdelen container
        parts_container = soup.find('ul', id='result-list')
        if not parts_container:
            return parts
        
        # Itereer over elk onderdeel
        part_items = parts_container.find_all('li', class_='shoppingcart')
        
        for item in part_items:
            part_data = {
                'search_license_plate': search_info.get('license_plate'),
                'search_part_name': search_info.get('part_name'),
                'category': search_info.get('category'),
                'scraped_at': time.strftime('%Y-%m-%d %H:%M:%S')
            }
            
            try:
                # Titel
                title_elem = item.find('div', class_='description')
                if title_elem:
                    bold_elem = title_elem.find('span', class_='bold')
                    if bold_elem:
                        part_data['title'] = bold_elem.get_text(strip=True)
                
                # Prijs
                price_elem = item.find('span', class_='price')
                if price_elem:
                    price_text = price_elem.get_text(strip=True)
                    if 'prijs op aanvraag' in price_text.lower():
                        part_data['price'] = 'Prijs op aanvraag'
                    else:
                        price_match = re.search(r'€\s*(\d+[\.\,]?\d*)', price_text)
                        if price_match:
                            price_value = price_match.group(1).replace(',', '.')
                            part_data['price'] = float(price_value)
                        else:
                            part_data['price'] = 'N/A'
                else:
                    part_data['price'] = 'N/A'
                
                # Aanbieder
                pricing_div = item.find('div', class_='pricing')
                if pricing_div:
                    supplier_elem = pricing_div.find('span', class_='block')
                    if supplier_elem:
                        part_data['supplier'] = supplier_elem.get_text(strip=True)
                
                # Specificaties
                specifications = {}
                spec_items = item.find_all('span', class_='item')
                for spec_item in spec_items:
                    try:
                        spans = spec_item.find_all('span')
                        if len(spans) >= 2:
                            key = spans[0].get_text(strip=True).replace(':', '')
                            value = spans[1].get_text(strip=True)
                            specifications[key] = value
                    except:
                        continue
                
                part_data['specifications'] = specifications
                
                # Afbeelding URL
                thumbnail_div = item.find('div', class_='thumbnail')
                if thumbnail_div:
                    img_elem = thumbnail_div.find('img')
                    if img_elem:
                        img_src = img_elem.get('src')
                        if img_src:
                            if not img_src.startswith('http'):
                                img_src = self.base_url + img_src
                            part_data['image_url'] = img_src
                        else:
                            part_data['image_url'] = 'N/A'
                    else:
                        part_data['image_url'] = 'N/A'
                else:
                    part_data['image_url'] = 'N/A'
                
                # Source URL
                onclick_attr = item.get('onclick')
                if onclick_attr and "window.location.href='" in onclick_attr:
                    try:
                        url_part = onclick_attr.split("'")[1]
                        part_data['source_url'] = self.base_url + url_part
                    except:
                        part_data['source_url'] = 'N/A'
                else:
                    part_data['source_url'] = 'N/A'
                
                # Alleen toevoegen als we minstens een titel hebben
                if part_data.get('title'):
                    parts.append(part_data)
                    
            except Exception as e:
                logging.info(f"⚠ Fout bij parsen onderdeel: {e}")
                continue
        
        return parts
    
    def scrape_category_results(self, category_name, category_url, search_info):
        """
        Scrape alle resultaten van een categorie URL met paginatie
        
        Args:
            category_name (str): Naam van de categorie
            category_url (str): URL van de categorie
            search_info (dict): Search metadata
            
        Returns:
            list: Alle gevonden onderdelen
        """
        logging.info(f"→ Scraping categorie: {category_name}")
        logging.info(f"  URL: {category_url}")
        
        all_parts = []
        page_number = 1
        
        try:
            # Navigeer naar categorie URL
            self.driver.get(category_url)
            time.sleep(3)
            
            # Handle cookies
            self._handle_cookies()
            
            # Paginatie loop
            while True:
                logging.info(f"  → Pagina {page_number} verwerken...")
                
                # Parse huidige pagina
                soup = BeautifulSoup(self.driver.page_source, 'lxml')
                search_info_with_category = {**search_info, 'category': category_name}
                page_parts = self.extract_part_data(soup, search_info_with_category)
                
                all_parts.extend(page_parts)
                logging.info(f"    ✓ {len(page_parts)} onderdelen gevonden")
                
                # Zoek naar volgende pagina knop
                try:
                    # Handle cookies voor click
                    self._handle_cookies()
                    
                    # Zoek next button - aangepaste selector
                    next_button = self.driver.find_element(By.CSS_SELECTOR, 'input[type="submit"][value=">"]')
                    
                    # Check of knop enabled is
                    if not next_button.is_enabled() or next_button.get_attribute('disabled'):
                        logging.info("    ✓ Laatste pagina bereikt")
                        break
                    
                    # Scroll naar knop en klik
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", next_button)
                    time.sleep(1)
                    
                    # Bewaar oude element voor staleness check
                    old_button = next_button
                    
                    # Klik op next button
                    self.driver.execute_script("arguments[0].click();", next_button)
                    
                    # Wacht tot pagina wordt bijgewerkt
                    try:
                        self.wait.until(EC.staleness_of(old_button))
                        time.sleep(2)
                    except TimeoutException:
                        time.sleep(3)  # Fallback wait
                    
                    page_number += 1
                    
                    # Safety limit
                    if page_number > 50:
                        logging.info("    ⚠ Pagina limiet bereikt (50)")
                        break
                        
                except NoSuchElementException:
                    logging.info("    ✓ Geen volgende pagina knop gevonden")
                    break
                except Exception as e:
                    logging.info(f"    ⚠ Fout bij paginatie: {e}")
                    break
            
            logging.info(f"✓ Categorie '{category_name}' voltooid: {len(all_parts)} onderdelen over {page_number} pagina(s)")
            return all_parts
            
        except Exception as e:
            logging.info(f"✗ Fout bij scraping categorie '{category_name}': {e}")
            return all_parts
    
    def scrape_parts(self, license_plate, part_name):
        """
        Hoofdfunctie voor het scrapen van onderdelen
        
        Args:
            license_plate (str): Auto kenteken
            part_name (str): Onderdeel naam
            
        Returns:
            dict: Resultaten georganiseerd per categorie
        """
        logging.info(f"\n🔍 Zoeken naar: {part_name}")
        logging.info(f"📋 Kenteken: {license_plate}\n")
        
        results = {
            'search_info': {
                'license_plate': license_plate,
                'part_name': part_name,
                'scraped_at': time.strftime('%Y-%m-%d %H:%M:%S')
            },
            'categories': {}
        }
        
        try:
            # Stap 1: Dynamische modeltype lookup
            modeltype = self.get_modeltype_dynamically(license_plate)
            
            if not modeltype:
                logging.info("✗ Kon modeltype niet bepalen")
                return results
            
            results['search_info']['modeltype'] = modeltype
            
            # Na modeltype lookup zijn we nu op de onderdelenlijst pagina
            # Stap 2: Detecteer pagina type
            page_type = self.detect_page_type()
            
            if page_type == 'results':
                # Direct results - scrape huidige pagina
                logging.info("→ Direct resultaten scrapen...")
                search_info = results['search_info']
                soup = BeautifulSoup(self.driver.page_source, 'lxml')
                parts = self.extract_part_data(soup, search_info)
                results['categories']['Direct Results'] = parts
                logging.info(f"✓ {len(parts)} onderdelen gevonden")
                
            else:
                # Category page - zoek en scrape categorieën
                # Stap 3: Vind categorie URLs
                category_urls = self.find_category_urls(part_name)
                
                if not category_urls:
                    logging.info("✗ Geen passende categorieën gevonden")
                    return results
                
                # Stap 4: Scrape elke categorie
                search_info = results['search_info']
                total_parts = 0
                
                for category_name, category_url in category_urls:
                    parts = self.scrape_category_results(category_name, category_url, search_info)
                    if parts:
                        results['categories'][category_name] = parts
                        total_parts += len(parts)
                
                logging.info(f"\n✓ Scraping voltooid: {total_parts} onderdelen in {len(results['categories'])} categorieën")
            
        except Exception as e:
            logging.info(f"✗ Fout bij scraping: {e}")
        
        return results
    
    def save_results(self, results, filename=None):
        """
        Sla resultaten op in JSON bestand
        
        Args:
            results (dict): Scraping resultaten
            filename (str): Output bestandsnaam
        """
        if not filename:
            timestamp = time.strftime('%Y%m%d_%H%M%S')
            license_plate = results['search_info']['license_plate'].replace('-', '')
            part_name = results['search_info']['part_name'].replace(' ', '_')
            filename = f"onderdelen_{license_plate}_{part_name}_{timestamp}.json"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=4, ensure_ascii=False)
            
            # Summary
            total_parts = sum(len(parts) for parts in results['categories'].values())
            logging.info(f"\n✓ Resultaten opgeslagen in: {filename}")
            logging.info(f"📊 Totaal: {total_parts} onderdelen in {len(results['categories'])} categorieën")
            
        except Exception as e:
            logging.info(f"✗ Fout bij opslaan: {e}")
    
    def close(self):
        """
        Sluit WebDriver
        """
        if self.driver:
            self.driver.quit()
            logging.info("✓ WebDriver gesloten")


def main():
    """
    Hoofdfunctie voor command-line gebruik
    """
    parser = argparse.ArgumentParser(
        description='OnderdelenLijn.nl Scraper',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Voorbeelden:
  python scraper_new.py "HF599X" "Remschijf"
  python scraper_new.py "37-LK-BB" "Deur" --output results.json
        '''
    )
    
    parser.add_argument('license_plate', help='Auto kenteken (bijv. HF599X)')
    parser.add_argument('part_name', help='Onderdeel naam (bijv. Remschijf)')
    parser.add_argument('--output', '-o', help='Output JSON bestand')
    parser.add_argument('--visible', action='store_true', help='Run browser in visible mode')
    
    args = parser.parse_args()
    
    # Initialiseer scraper
    scraper = OnderdelenLijnScraper(headless=not args.visible)
    
    try:
        # Scrape onderdelen
        results = scraper.scrape_parts(args.license_plate, args.part_name)
        
        # Sla resultaten op
        scraper.save_results(results, args.output)
        
    except KeyboardInterrupt:
        logging.info("\n⚠ Scraping onderbroken door gebruiker")
    except Exception as e:
        logging.info(f"✗ Onverwachte fout: {e}")
    finally:
        # Zorg dat WebDriver altijd wordt gesloten
        scraper.close()


if __name__ == '__main__':
    main()