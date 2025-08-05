#!/usr/bin/env python3
"""
Debug script om de exacte HTML structuur van links te analyseren
"""

import requests
from bs4 import BeautifulSoup
import sys

def analyze_links():
    # Lees de opgeslagen HTML
    with open('debug_parts_list.html', 'r', encoding='utf-8') as f:
        html = f.read()
    
    soup = BeautifulSoup(html, 'lxml')
    
    # Zoek alle links
    all_links = soup.find_all('a', href=True)
    
    print(f"Totaal aantal links: {len(all_links)}\n")
    
    # Zoek specifiek naar "Aandrijfas links-voor"
    target = "Aandrijfas links-voor"
    found_links = []
    
    for i, link in enumerate(all_links):
        link_text = link.get_text(strip=True)
        href = link.get('href', '')
        
        # Print info over links die "aandrijf" bevatten
        if 'aandrijf' in link_text.lower():
            print(f"Link #{i}:")
            print(f"  Text: '{link_text}'")
            print(f"  Href: '{href}'")
            print(f"  Parent tag: {link.parent.name if link.parent else 'None'}")
            print(f"  Classes: {link.get('class', [])}")
            print()
            
            if link_text == target:
                found_links.append((link_text, href))
    
    print(f"\nGevonden exacte matches voor '{target}': {len(found_links)}")
    for text, href in found_links:
        print(f"  → {text}: {href}")
    
    # Analyseer de container structuur
    print("\n=== Container Analyse ===")
    containers = soup.find_all('div', class_=lambda x: x and 'search' in str(x).lower())
    print(f"Gevonden {len(containers)} containers met 'search' in de class")
    
    for container in containers[:3]:
        print(f"\nContainer: {container.get('class', [])}")
        links_in_container = container.find_all('a', href=True)
        print(f"  Bevat {len(links_in_container)} links")
        if links_in_container:
            print(f"  Eerste link: '{links_in_container[0].get_text(strip=True)}'")

if __name__ == '__main__':
    analyze_links()