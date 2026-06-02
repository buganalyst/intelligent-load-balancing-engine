from flask import Flask, request, jsonify, render_template, redirect, url_for
import requests
import threading
import time
import json
import os
import hashlib
import random
import logging
import subprocess
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__,
            template_folder=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'templates'),
            static_folder=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'static'))

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config', 'server_config.json')

USE_CPP_LOGIC = True
CPP_EXECUTABLE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'algorithms', 'algo_logic.exe' if os.name == 'nt' else 'algo_logic')

def load_config():
    try:
        with open(CONFIG_PATH, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Config file not found: {e}. Using default configuration.")
        return {
            "load_balancer": {"host": "0.0.0.0", "port": 8000},
            "backend_servers": [
                {"id": "server_1", "url": "http://10.147.98.39:5001", "weight": 1, "location": "Dehradun"},
                {"id": "server_2", "url": "http://10.147.98.18:5002", "weight": 3, "location": "Dehradun"},
                {"id": "server_3", "url": "http://10.147.98.18:5003", "weight": 4, "location": "Dehradun"}
            ],
            "health_check": {"interval_seconds": 5, "timeout_seconds": 2}
        }

CONFIG = load_config()

state_lock = threading.Lock()

connections = {s['url']: 0 for s in CONFIG['backend_servers']}
requests_count = {s['url']: 0 for s in CONFIG['backend_servers']}
response_times = {s['url']: [] for s in CONFIG['backend_servers']}
health_status = {s['url']: True for s in CONFIG['backend_servers']}
last_checked = {s['url']: "Never" for s in CONFIG['backend_servers']}

current_algorithm = "round_robin"

rr_index = 0
wrr_index = 0

weighted_server_list = []
for server in CONFIG['backend_servers']:
    weight = server.get('weight', 1)
    for _ in range(weight):
        weighted_server_list.append(server)


def get_formatted_time():
    return datetime.now().strftime("%I:%M %p")


def get_formatted_datetime():
    return datetime.now().strftime("%B %d, %Y - %I:%M %p")


def select_server_cpp(algo, client_ip):
    if not os.path.exists(CPP_EXECUTABLE):
        return None
    
    try:
        input_data = ""
        for s in CONFIG['backend_servers']:
            url = s['url']
            w = s['weight']
            c = connections.get(url, 0)
            h = 1 if health_status.get(url, False) else 0
            input_data += f"{url},{w},{c},{h}\n"
        
        result = subprocess.run(
            [CPP_EXECUTABLE, algo, client_ip],
            input=input_data,
            capture_output=True,
            text=True,
            timeout=1
        )
        return result.stdout.strip()
    except Exception as e:
        logger.warning(f"C++ Logic failed: {e}. Falling back to Python.")
        return None


def algo_round_robin():
    global rr_index
    with state_lock:
        total_servers = len(CONFIG['backend_servers'])
        attempts = 0
        selected_server = None
        while attempts < total_servers:
            current_index = rr_index % total_servers
            server = CONFIG['backend_servers'][current_index]
            server_url = server['url']
            if health_status.get(server_url, False):
                selected_server = server
                rr_index = (rr_index + 1) % total_servers
                break
            rr_index = (rr_index + 1) % total_servers
            attempts += 1
        if selected_server is None:
            selected_server = CONFIG['backend_servers'][0]
            rr_index = (rr_index + 1) % total_servers
        return selected_server


def algo_weighted_round_robin():
    global wrr_index
    with state_lock:
        total_entries = len(weighted_server_list)
        if total_entries == 0:
            return CONFIG['backend_servers'][0]
        attempts = 0
        selected_server = None
        while attempts < total_entries:
            current_index = wrr_index % total_entries
            server = weighted_server_list[current_index]
            server_url = server['url']
            if health_status.get(server_url, False):
                selected_server = server
                wrr_index = (wrr_index + 1) % total_entries
                break
            wrr_index = (wrr_index + 1) % total_entries
            attempts += 1
        if selected_server is None:
            selected_server = weighted_server_list[0]
            wrr_index = (wrr_index + 1) % total_entries
        return selected_server


def algo_least_connections():
    min_connections = float('inf')
    selected_server = None
    with state_lock:
        for server in CONFIG['backend_servers']:
            server_url = server['url']
            if health_status.get(server_url, False):
                current_connections = connections.get(server_url, 0)
                if current_connections < min_connections:
                    min_connections = current_connections
                    selected_server = server
        if selected_server is None:
            selected_server = CONFIG['backend_servers'][0]
    return selected_server


def algo_ip_hash(client_ip):
    with state_lock:
        total_servers = len(CONFIG['backend_servers'])
        hash_object = hashlib.md5(client_ip.encode('utf-8'))
        hash_hex = hash_object.hexdigest()
        hash_integer = int(hash_hex, 16)
        server_index = hash_integer % total_servers
        selected_server = CONFIG['backend_servers'][server_index]
        server_url = selected_server['url']
        if not health_status.get(server_url, False):
            for i in range(1, total_servers):
                next_index = (server_index + i) % total_servers
                next_server = CONFIG['backend_servers'][next_index]
                next_url = next_server['url']
                if health_status.get(next_url, False):
                    selected_server = next_server
                    break
        return selected_server


def algo_random():
    with state_lock:
        healthy_servers = []
        for server in CONFIG['backend_servers']:
            server_url = server['url']
            if health_status.get(server_url, False):
                healthy_servers.append(server)
        if len(healthy_servers) == 0:
            return CONFIG['backend_servers'][0]
        random_index = random.randint(0, len(healthy_servers) - 1)
        return healthy_servers[random_index]


def select_server(client_ip):
    if USE_CPP_LOGIC:
        cpp_result = select_server_cpp(current_algorithm, client_ip)
        if cpp_result:
            for s in CONFIG['backend_servers']:
                if s['url'] == cpp_result:
                    return s
    
    if current_algorithm == "round_robin":
        return algo_round_robin()
    elif current_algorithm == "weighted_round_robin":
        return algo_weighted_round_robin()
    elif current_algorithm == "least_connections":
        return algo_least_connections()
    elif current_algorithm == "ip_hash":
        return algo_ip_hash(client_ip)
    elif current_algorithm == "random":
        return algo_random()
    else:
        return algo_round_robin()


def health_monitor():
    while True:
        for server in CONFIG['backend_servers']:
            url = server['url']
            try:
                response = requests.get(f"{url}/health", timeout=CONFIG['health_check']['timeout_seconds'])
                with state_lock:
                    health_status[url] = (response.status_code == 200)
                    last_checked[url] = get_formatted_time()
            except Exception as e:
                with state_lock:
                    health_status[url] = False
                    last_checked[url] = get_formatted_time()
        time.sleep(CONFIG['health_check']['interval_seconds'])


health_thread = threading.Thread(target=health_monitor, daemon=True)
health_thread.start()


@app.route("/")
def index():
    client_ip = request.remote_addr
    selected_server = select_server(client_ip)
    server_url = selected_server['url']
    start_time = time.time()
    
    with state_lock:
        connections[server_url] += 1
        requests_count[server_url] += 1
    
    try:
        response = requests.get(server_url, timeout=10)
        response_time = time.time() - start_time
        with state_lock:
            response_times[server_url].append(response_time)
            if len(response_times[server_url]) > 100:
                response_times[server_url] = response_times[server_url][-100:]
        return response.text
    except Exception as e:
        with state_lock:
            connections[server_url] -= 1
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        </head>
        <body class="bg-danger text-white text-center" style="padding: 50px;">
            <h1><i class="fas fa-exclamation-triangle"></i> Error</h1>
            <p>Failed to connect to backend server</p>
            <p><strong>Server:</strong> {server_url}</p>
            <p><strong>Error:</strong> {str(e)}</p>
            <a href="/" class="btn btn-light">Try Again</a>
            <a href="/dashboard" class="btn btn-light">Dashboard</a>
        </body>
        </html>
        """
    finally:
        with state_lock:
            connections[server_url] -= 1


@app.route("/dashboard")
def dashboard():
    server_data = []
    for server in CONFIG['backend_servers']:
        url = server['url']
        avg_response = 0
        if response_times[url]:
            avg_response = sum(response_times[url]) / len(response_times[url])
        server_data.append({
            'id': server['id'],
            'url': url,
            'weight': server['weight'],
            'location': server.get('location', 'Unknown'),
            'health': health_status[url],
            'active_connections': connections[url],
            'total_requests': requests_count[url],
            'avg_response_time': f"{avg_response:.3f}s",
            'last_checked': last_checked[url]
        })
    
    with state_lock:
        algo = current_algorithm
    
    return render_template('dashboard.html',
                         servers=server_data,
                         current_algo=algo,
                         current_time=get_formatted_datetime(),
                         total_servers=len(CONFIG['backend_servers']),
                         healthy_servers=sum(1 for s in server_data if s['health']),
                         total_requests=sum(requests_count.values()))


@app.route("/set_algorithm", methods=["POST"])
def set_algorithm():
    global current_algorithm
    new_algo = request.form.get('algorithm', 'round_robin')
    valid_algorithms = ['round_robin', 'weighted_round_robin', 'least_connections', 'ip_hash', 'random']
    with state_lock:
        if new_algo in valid_algorithms:
            current_algorithm = new_algo
    return redirect(url_for('dashboard'))


@app.route("/api/metrics")
def api_metrics():
    with state_lock:
        algo = current_algorithm
    metrics = {
        "timestamp": get_formatted_datetime(),
        "algorithm": algo,
        "total_servers": len(CONFIG['backend_servers']),
        "healthy_servers": sum(1 for url in health_status.values() if url),
        "total_requests": sum(requests_count.values()),
        "servers": []
    }
    for server in CONFIG['backend_servers']:
        url = server['url']
        avg_response = 0
        if response_times[url]:
            avg_response = sum(response_times[url]) / len(response_times[url])
        metrics["servers"].append({
            "id": server['id'],
            "url": url,
            "weight": server['weight'],
            "location": server.get('location', 'Unknown'),
            "health": health_status[url],
            "active_connections": connections[url],
            "total_requests": requests_count[url],
            "avg_response_time": f"{avg_response:.3f}s"
        })
    return jsonify(metrics)


@app.route("/reset_metrics", methods=["POST"])
def reset_metrics():
    global connections, requests_count, response_times
    with state_lock:
        connections = {s['url']: 0 for s in CONFIG['backend_servers']}
        requests_count = {s['url']: 0 for s in CONFIG['backend_servers']}
        response_times = {s['url']: [] for s in CONFIG['backend_servers']}
    return redirect(url_for('dashboard'))


@app.errorhandler(404)
def not_found(e):
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    </head>
    <body class="bg-light text-center" style="padding: 100px;">
        <h1 class="text-danger">404 - Page Not Found</h1>
        <a href="/" class="btn btn-primary">Home</a>
        <a href="/dashboard" class="btn btn-primary">Dashboard</a>
    </body>
    </html>
    """, 404


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("  DAA LOAD BALANCER SERVER - PHASE 2")
    print("=" * 70)
    print(f"  Host: {CONFIG['load_balancer']['host']}")
    print(f"  Port: {CONFIG['load_balancer']['port']}")
    print(f"  Backend Servers: {len(CONFIG['backend_servers'])}")
    print(f"  Algorithm: {current_algorithm}")
    print(f"  C++ Logic: {USE_CPP_LOGIC}")
    print(f"  Started: {get_formatted_datetime()}")
    print("=" * 70)
    print("\n  Access Points:")
    print("     - User Endpoint: http://localhost:8000/")
    print("     - Admin Dashboard: http://localhost:8000/dashboard")
    print("     - API Metrics: http://localhost:8000/api/metrics")
    print("=" * 70 + "\n")
    app.run(host=CONFIG['load_balancer']['host'], port=CONFIG['load_balancer']['port'], debug=False, threaded=True)
