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
    """Background thread voor scraping - Server-compatible version"""
    import threading
    import time as time_module
    
    try:
        active_jobs[job_id]['status'] = 'running'
        start_time = time_module.time()
        
        # Initialize scraper with built-in timeouts (server-compatible)
        scraper = OnderdelenLijnScraper(headless=True, timeout=30)
        
        # Set additional Selenium timeouts for server environment
        if scraper.driver:
            scraper.driver.set_page_load_timeout(60)  # 60 seconds page load timeout
            scraper.driver.implicitly_wait(10)  # 10 seconds implicit wait
        
        try:
            # Run scraping with server-compatible approach
            print(f"🚀 Starting scrape for {license_plate} - {part_name}")
            print(f"📍 Python version: {__import__('sys').version}")
            print(f"📍 Current working directory: {__import__('os').getcwd()}")
            
            # Test basic functionality first
            try:
                print("📍 Testing Chrome binary availability...")
                import subprocess
                result = subprocess.run(['google-chrome', '--version'], 
                                      capture_output=True, text=True, timeout=10)
                print(f"📍 Chrome version: {result.stdout.strip()}")
            except Exception as e:
                print(f"⚠️ Chrome check failed: {e}")
            
            # Check if scraper initialized properly
            if not scraper.driver:
                raise Exception("WebDriver failed to initialize")
            
            print("📍 WebDriver initialized successfully")
            
            # Monitor job duration and enforce 4-minute limit (increased from 2 minutes)
            def check_timeout():
                while active_jobs[job_id]['status'] == 'running':
                    elapsed = time_module.time() - start_time
                    if elapsed > 240:  # 4 minutes (increased from 120 seconds)
                        print(f"⏰ Job timeout after {elapsed:.1f} seconds")
                        active_jobs[job_id]['status'] = 'failed'
                        active_jobs[job_id]['error'] = f"Job timed out after {elapsed:.1f} seconds"
                        try:
                            scraper.close()
                        except:
                            pass
                        return
                    time_module.sleep(5)  # Check every 5 seconds
            
            # Start timeout monitor in background
            timeout_thread = threading.Thread(target=check_timeout, daemon=True)
            timeout_thread.start()
            
            # Run the actual scraping
            results = scraper.scrape_parts(license_plate, part_name) 
            
            # Check if job was timed out during scraping
            if active_jobs[job_id]['status'] == 'failed':
                return  # Job was timed out by monitor thread
            
            print(f"✅ Scrape completed for {license_plate}")
            
            # Update job status
            active_jobs[job_id]['status'] = 'completed'
            active_jobs[job_id]['results'] = results
            
        finally:
            try:
                scraper.close()
            except:
                pass
            
    except Exception as e:
        print(f"❌ Scrape failed for {license_plate}: {str(e)}")
        active_jobs[job_id]['status'] = 'failed'
        active_jobs[job_id]['error'] = str(e)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)