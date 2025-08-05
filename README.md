# Onderdelenlijn.nl Web Scraper

Een Python web scraper voor het zoeken en opslaan van auto-onderdelen van onderdelenlijn.nl.

## Installatie

1. Installeer de vereiste dependencies:
```bash
pip install -r requirements.txt
```

## Gebruik

```bash
python scraper.py <kenteken> "<onderdeelnaam>"
```

### Voorbeelden:
```bash
python scraper.py 27-XH-VX "Aandrijfas links-voor"
python scraper.py 12-AB-CD "Koplamp rechts"
python scraper.py 99-ZZ-99 "Uitlaat"
```

## Database

De scraper slaat alle gevonden onderdelen op in een SQLite database (`onderdelen.db`) met de volgende velden:
- `part_title`: Titel van het onderdeel
- `price`: Prijs in euro's
- `supplier_name`: Naam van de leverancier
- `part_condition`: Conditie (Gebruikt/Nieuw/Gereviseerd)
- `warranty_months`: Garantie in maanden
- `build_year`: Bouwjaar
- `engine_code`: Motorcode
- `mileage_km`: Kilometerstand
- `source_url`: Link naar het onderdeel

## Opmerking

Deze scraper werkt met de directe URL-structuur van onderdelenlijn.nl en hoeft geen formulieren te submitten.