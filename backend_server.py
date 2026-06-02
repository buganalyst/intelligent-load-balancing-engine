from flask import Flask, request, jsonify
import socket
import os
import time
import random
from datetime import datetime

app = Flask(__name__)

START_TIME = datetime.now()
REQUEST_COUNT = 0


def get_formatted_time():
    return datetime.now().strftime("%I:%M %p")


def get_uptime():
    delta = datetime.now() - START_TIME
    hours, remainder = divmod(int(delta.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}h {minutes}m {seconds}s"


@app.route("/")
def home():
    global REQUEST_COUNT
    REQUEST_COUNT += 1
    
    hostname = socket.gethostname()
    ip_address = request.host.split(':')[0]
    user = os.getenv("USER") or os.getenv("USERNAME") or "System"
    port = request.environ.get('SERVER_PORT', 'Unknown')
    
    processing_time = random.uniform(0.05, 0.2)
    time.sleep(processing_time)
    
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Backend Server - {hostname}</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
        <style>
            body {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            }}
            .server-card {{
                background: white;
                border-radius: 20px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                padding: 40px;
                max-width: 600px;
                width: 90%;
            }}
            .server-icon {{
                font-size: 60px;
                color: #667eea;
                margin-bottom: 20px;
            }}
            .info-row {{
                display: flex;
                justify-content: space-between;
                padding: 12px 0;
                border-bottom: 1px solid #eee;
            }}
            .info-label {{
                font-weight: 600;
                color: #555;
            }}
            .info-value {{
                color: #333;
                font-family: 'Courier New', monospace;
            }}
            .status-badge {{
                background: #28a745;
                color: white;
                padding: 5px 15px;
                border-radius: 20px;
                font-size: 14px;
            }}
        </style>
    </head>
    <body>
        <div class="server-card">
            <div class="text-center">
                <i class="fas fa-server server-icon"></i>
                <h2 class="mb-3">Backend Server Response</h2>
                <span class="status-badge">
                    <i class="fas fa-check-circle"></i> Online
                </span>
            </div>
            
            <div class="mt-4">
                <div class="info-row">
                    <span class="info-label"><i class="fas fa-desktop"></i> Hostname:</span>
                    <span class="info-value">{hostname}</span>
                </div>
                <div class="info-row">
                    <span class="info-label"><i class="fas fa-network-wired"></i> IP Address:</span>
                    <span class="info-value">{ip_address}</span>
                </div>
                <div class="info-row">
                    <span class="info-label"><i class="fas fa-port"></i> Port:</span>
                    <span class="info-value">{port}</span>
                </div>
                <div class="info-row">
                    <span class="info-label"><i class="fas fa-user"></i> User:</span>
                    <span class="info-value">{user}</span>
                </div>
                <div class="info-row">
                    <span class="info-label"><i class="fas fa-stopwatch"></i> Uptime:</span>
                    <span class="info-value">{get_uptime()}</span>
                </div>
                <div class="info-row">
                    <span class="info-label"><i class="fas fa-tachometer-alt"></i> Processing Time:</span>
                    <span class="info-value">{processing_time:.3f}s</span>
                </div>
            </div>
            
            <div class="mt-4 text-center">
                <small class="text-muted">
                    <i class="fas fa-info-circle"></i> 
                    This server is part of the DAA Project
                </small>
            </div>
        </div>
    </body>
    </html>
    """


@app.route("/health")
def health_check():
    return jsonify({"status": "healthy", "time": get_formatted_time()})


@app.route("/metrics")
def metrics():
    return jsonify({
        "hostname": socket.gethostname(),
        "requests": REQUEST_COUNT,
        "uptime": get_uptime(),
        "time": get_formatted_time(),
        "status": "healthy"
    })


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    else:
        port = 5003
    
    print(f"Starting Backend Server on Port {port}")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)