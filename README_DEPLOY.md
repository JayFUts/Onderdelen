# 🚗 OnderdelenLijn Scraper

Automatische auto-onderdelen scraper voor onderdelenlijn.nl met dynamische kenteken detectie.

## Features

- ✅ **Automatische kenteken herkenning** - Geen vooraf configuratie nodig
- ✅ **Intelligente onderdeel matching** - Vindt alle relevante categorieën  
- ✅ **Multi-page scraping** - Schraapt alle beschikbare pagina's
- ✅ **Complete data extractie** - Prijzen, specs, afbeeldingen, leveranciers
- ✅ **JSON export** - Gestructureerde data output
- ✅ **Web API** - Railway.app deployment ready

## Local Usage

```bash
# Setup
cd prijs
source venv/bin/activate
pip install -r requirements.txt

# Scrape onderdelen
python scraper_new.py "HF599X" "Remschijf"
python scraper_new.py "37-LK-BB" "Deur"
python scraper_new.py "L991HS" "Motor"
```

## Web API Usage

```bash
# Start web server
python app.py

# API calls
curl -X POST http://localhost:5000/scrape \
  -H "Content-Type: application/json" \
  -d '{"license_plate": "HF599X", "part_name": "Remschijf"}'

# Check status
curl http://localhost:5000/status/JOB_ID

# Download results
curl http://localhost:5000/results/JOB_ID -o results.json
```

## Railway.app Deployment

1. Push to GitHub
2. Connect repository to Railway
3. Deploy automatically
4. Use web API endpoints

## Environment Variables

- `PORT` - Web server port (default: 5000)

## Supported Features

- **Kentekens**: Alle Nederlandse kentekens
- **Onderdelen**: Motors, remmen, deuren, bumpers, velgen, etc.
- **Output**: JSON met prijzen, specs, leveranciers, afbeeldingen
- **Paginatie**: Automatisch door alle beschikbare pagina's

## Architecture

```
Kenteken Input → Dynamische Auto Detectie → Pagina Type Check → 
[Results: Direct] OF [Category: Search → Click] → 
Multi-Page Scraping → JSON Export
```