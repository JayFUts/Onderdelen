#!/usr/bin/env python3
"""
Debug versie van de scraper om de HTML structuur te analyseren
"""

import requests
from bs4 import BeautifulSoup

def debug_page(license_plate, part_name):
    # URL constructie
    formatted_license_plate = license_plate.lower().replace(' ', '')
    formatted_part_name = part_name.lower().replace(' ', '-')
    
    url = f"https://www.onderdelenlijn.nl/auto-onderdelen-voorraad/magazijn/kenteken/{formatted_license_plate}/onderdeel/{formatted_part_name}/"
    
    print(f"URL: {url}\n")
    
    # HTTP Request
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    response = requests.get(url, headers=headers)
    print(f"Status Code: {response.status_code}")
    print(f"Content Length: {len(response.text)} characters\n")
    
    # HTML Parsen
    soup = BeautifulSoup(response.text, 'lxml')
    
    # Zoek naar mogelijke product containers
    print("=== Zoeken naar product containers ===")
    
    # Probeer verschillende selectors
    selectors = [
        ('div', {'class': 'product'}),
        ('div', {'class': 'item'}),
        ('div', {'class': 'result'}),
        ('article', None),
        ('div', {'class': 'card'}),
        ('div', {'class': 'listing'}),
        ('tr', None),  # Misschien een tabel?
        ('div', {'id': 'results'}),
    ]
    
    for tag, attrs in selectors:
        elements = soup.find_all(tag, attrs)
        if elements:
            print(f"✓ Gevonden: {len(elements)} {tag} elementen met attrs={attrs}")
            # Toon eerste element
            if len(elements) > 0:
                print(f"  Eerste element preview: {str(elements[0])[:200]}...")
    
    # Zoek naar prijzen
    print("\n=== Zoeken naar prijzen ===")
    price_patterns = ['€', 'EUR', 'euro', 'prijs', 'price']
    for pattern in price_patterns:
        elements = soup.find_all(string=lambda text: text and pattern in text.lower())
        if elements:
            print(f"✓ Gevonden {len(elements)} elementen met '{pattern}'")
            for i, elem in enumerate(elements[:3]):
                print(f"  {i+1}: {elem.strip()}")
    
    # Zoek naar alle links
    print("\n=== Alle links op de pagina ===")
    links = soup.find_all('a', href=True)
    detail_links = [link for link in links if 'onderdeel' in link.get('href', '').lower() or 'product' in link.get('href', '').lower()]
    print(f"Totaal links: {len(links)}")
    print(f"Product/onderdeel links: {len(detail_links)}")
    
    # Save een sample van de HTML voor verdere analyse
    with open('debug_output.html', 'w', encoding='utf-8') as f:
        f.write(soup.prettify())
    print("\n✓ Volledige HTML opgeslagen in debug_output.html")

if __name__ == '__main__':
    debug_page('27-XH-VX', 'Aandrijfas links-voor')