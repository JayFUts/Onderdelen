#!/usr/bin/env python3
"""
Railway.app Web API wrapper voor OnderdelenLijn Scraper
"""

from flask import Flask, request, jsonify, send_file, render_template
import os
import json
import tempfile
from scraper_new import OnderdelenLijnScraper
import threading
import time

app = Flask(__name__, template_folder='templates')

# Store voor actieve scraping jobs
active_jobs = {}

@app.route('/')
def home():
    """Render dashboard"""
    return render_template('dashboard.html')

@app.route('/api/docs')
def api_docs():
    """API documentatie"""
    return """
    <h1>🚗 OnderdelenLijn Scraper API</h1>
    <h2>Endpoints:</h2>
    <ul>
        <li><strong>POST /scrape</strong> - Start scraping job</li>
        <li><strong>GET /status/&lt;job_id&gt;</strong> - Check job status</li>
        <li><strong>GET /results/&lt;job_id&gt;</strong> - Download results</li>
        <li><strong>GET /health</strong> - Health check</li>
    </ul>
    
    <h2>Voorbeeld:</h2>
    <pre>
POST /scrape
{
    "license_plate": "HF599X",
    "part_name": "Remschijf"
}
    </pre>
    
    <p><strong>Response:</strong></p>
    <pre>
{
    "job_id": "abc123",
    "status": "started",
    "message": "Scraping gestart"
}
    </pre>
    """

@app.route('/health')
def health():
    """Health check voor Railway"""
    return {"status": "healthy", "service": "onderdelenlijn-scraper"}

@app.route('/scrape', methods=['POST'])
def start_scrape():
    """Start een nieuwe scraping job"""
    try:
        data = request.get_json()
        
        if not data or 'license_plate' not in data or 'part_name' not in data:
            return jsonify({
                "error": "Missing required fields: license_plate, part_name"
            }), 400
        
        license_plate = data['license_plate']
        part_name = data['part_name']
        
        # Generate job ID
        job_id = f"{license_plate.replace('-', '')}_{part_name.replace(' ', '_')}_{int(time.time())}"
        
        # Initialize job status
        active_jobs[job_id] = {
            'status': 'started',
            'license_plate': license_plate,
            'part_name': part_name,
            'results': None,
            'error': None,
            'started_at': time.time()
        }
        
        # Start scraping in background thread
        thread = threading.Thread(
            target=run_scraper_job,
            args=(job_id, license_plate, part_name)
        )
        thread.start()
        
        return jsonify({
            "job_id": job_id,
            "status": "started", 
            "message": f"Scraping gestart voor {license_plate} - {part_name}",
            "status_url": f"/status/{job_id}",
            "results_url": f"/results/{job_id}"
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/status/<job_id>')
def get_status(job_id):
    """Check status van scraping job"""
    if job_id not in active_jobs:
        return jsonify({"error": "Job not found"}), 404
    
    job = active_jobs[job_id]
    
    response = {
        "job_id": job_id,
        "status": job['status'],
        "license_plate": job['license_plate'],
        "part_name": job['part_name'],
        "started_at": job['started_at']
    }
    
    if job['status'] == 'completed' and job['results']:
        response['summary'] = {
            "total_parts": sum(len(parts) for parts in job['results']['categories'].values()),
            "categories": len(job['results']['categories']),
            "modeltype": job['results']['search_info'].get('modeltype')
        }
    
    if job['error']:
        response['error'] = job['error']
    
    return jsonify(response)

@app.route('/results/<job_id>')
def get_results(job_id):
    """Download results van scraping job"""
    if job_id not in active_jobs:
        return jsonify({"error": "Job not found"}), 404
    
    job = active_jobs[job_id]
    
    if job['status'] != 'completed':
        return jsonify({
            "error": "Job not completed yet",
            "status": job['status']
        }), 400
    
    if not job['results']:
        return jsonify({"error": "No results available"}), 404
    
    # Check if request wants JSON response (for dashboard)
    if request.headers.get('Accept') == 'application/json':
        return jsonify(job['results'])
    
    # Otherwise send as file download
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(job['results'], f, indent=2, ensure_ascii=False)
        temp_file = f.name
    
    # Send file and clean up
    def remove_file(response):
        try:
            os.unlink(temp_file)
        except:
            pass
        return response
    
    return send_file(
        temp_file,
        as_attachment=True,
        download_name=f"onderdelen_{job['license_plate'].replace('-', '')}_{job['part_name'].replace(' ', '_')}.json",
        mimetype='application/json'
    )

def run_scraper_job(job_id, license_plate, part_name):
    """Background thread voor scraping"""
    try:
        active_jobs[job_id]['status'] = 'running'
        
        # Initialize scraper optimized for cloud environment
        scraper = OnderdelenLijnScraper(headless=True, timeout=60)
        
        try:
            # Run scraping with timeout protection
            print(f"🚀 Starting scrape for {license_plate} - {part_name}")
            results = scraper.scrape_parts(license_plate, part_name)
            print(f"✅ Scrape completed for {license_plate}")
            
            # Update job status
            active_jobs[job_id]['status'] = 'completed'
            active_jobs[job_id]['results'] = results
            
        finally:
            scraper.close()
            
    except Exception as e:
        print(f"❌ Scrape failed for {license_plate}: {str(e)}")
        active_jobs[job_id]['status'] = 'failed'
        active_jobs[job_id]['error'] = str(e)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)