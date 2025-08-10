import os
import json
import threading
import time
from flask import Flask, jsonify, request, render_template_string
import docker
import subprocess

# Configurações
DATA_DIR = os.getenv("DATA_DIR", "/data")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK", "")
TRIGGER_LABEL = os.getenv("TRIGGER_LABEL", "notify")
TRIGGER_VALUE = os.getenv("TRIGGER_VALUE", "true")
EVENTS = os.getenv("EVENTS", "start,stop").split(",")
MESSAGE_TEMPLATE = os.getenv("MESSAGE_TEMPLATE", "Container {name} {event}")

def init_config():
    global config
    try:
        ensure_data_dir()
        config = load_config()
        print(f"✅ Config loaded from {CONFIG_FILE}")
        if not config:
            print("ℹ️ No existing config, starting with empty config")
    except Exception as e:
        print(f"❌ Failed to load config: {e}")
        config = {}

app = Flask(__name__)
client = docker.from_env()
config_lock = threading.Lock()
config = {}

# Utils
def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)

def load_config():
    ensure_data_dir()
    if not os.path.exists(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def save_config(cfg):
    try:
        ensure_data_dir()
        temp_file = f"{CONFIG_FILE}.tmp"
        with open(temp_file, "w") as f:
            json.dump(cfg, f, indent=2)
        os.replace(temp_file, CONFIG_FILE)
        print(f"🔄 Config saved to {CONFIG_FILE}")
    except Exception as e:
        print(f"🔥 Failed to save config: {e}")


def notify(message):
    print(f"🚀 Notificação: {message}")   
  
    if DISCORD_WEBHOOK:
        try:
            subprocess.run([
                "curl", "-s", "-H", "Content-Type: application/json",
                "-d", json.dumps({"content": message}),
                DISCORD_WEBHOOK
            ], check=False)
        except Exception as e:
            print(f"Erro Discord: {e}")

# Docker Events Listener
def docker_events_listener():
    while True:
        try:
            for event in client.events(decode=True):
                try:
                    if event.get("Type") != "container":
                        continue

                    action = event.get("Action")
                    if action not in EVENTS:
                        continue

                    labels = event["Actor"]["Attributes"]
                    if labels.get(TRIGGER_LABEL) == TRIGGER_VALUE:
                        container_id = event.get("id")
                        name = labels.get("name", container_id[:12])
                        
                        with config_lock:
                            container_config = config.get(container_id, {"start": True, "stop": True})
                            
                            if (action == "start" and container_config.get("start")) or \
                               (action == "stop" and container_config.get("stop")):
                                msg = MESSAGE_TEMPLATE.format(name=name, event=action)
                                notify(msg)
                                
                except Exception as e:
                    print(f"Erro ao processar evento: {e}")
                    time.sleep(1)
                    
        except Exception as e:
            print(f"Erro no listener: {e}")
            time.sleep(5)

# Interface HTML atualizada
INDEX_HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Docker Events UI</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
  <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/font/bootstrap-icons.css" rel="stylesheet">
  <style>
    :root {
      --portainer-dark-bg: #252e3b;
      --portainer-card-bg: #2c3a4a;
      --portainer-blue: #3498db;
      --portainer-light-text: #ecf0f1;
      --portainer-dark-text: #2c3e50;
      --portainer-border: #3d4e60;
      --switch-active: #2ecc71;
      --text-highlight: #a8d8ff; /* Novo: para texto destacado no dark mode */
    }
    
    body.dark {
      background-color: var(--portainer-dark-bg);
      color: var(--portainer-light-text);
    }
    
    .dark .container-card {
      background-color: var(--portainer-card-bg);
      border: 1px solid var(--portainer-border);
    }
    
    .dark .text-muted {
      color: var(--text-highlight) !important; /* Texto mais visível */
    }
    
    .dark .form-switch .form-check-input:checked {
      background-color: var(--switch-active);
      border-color: var(--switch-active);
    }
    
    body.light {
      background-color: #f5f7fa;
      color: var(--portainer-dark-text);
    }
    
    .light .container-card {
      background-color: white;
      border: 1px solid #dfe6e9;
    }
    
    .light .form-switch .form-check-input:checked {
      background-color: var(--switch-active); /* Verde no light mode também */
      border-color: var(--switch-active);
    }
    
    .container-card {
      padding: 1rem;
      margin-bottom: 1rem;
      border-radius: 0.375rem;
      transition: all 0.2s;
    }
    
    .container-card:hover {
      transform: translateY(-2px);
      box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    .status-indicator {
      width: 10px;
      height: 10px;
      border-radius: 50%;
      display: inline-block;
      margin-right: 8px;
    }
    
    .status-running {
      background-color: #2ecc71;
      box-shadow: 0 0 8px #2ecc71;
    }
    
    .status-stopped {
      background-color: #e74c3c;
    }
    
    .form-switch .form-check-input {
      width: 2.5em;
      height: 1.4em;
      cursor: pointer;
    }
    
    .theme-toggle {
      cursor: pointer;
      font-size: 1.2rem;
      transition: all 0.2s;
      color: var(--portainer-blue);
    }
    
    .badge {
      font-weight: 500;
    }
    
    .last-updated {
      font-size: 0.8rem;
    }
    
    /* Melhorias específicas para legibilidade */
    .dark .card-title {
      color: #ffffff !important;
    }
    
    .dark .form-check-label {
      color: #e0e0e0;
    }
    
    .light .form-check-label {
      color: #333333;
    }
    
    /* Ajuste para o texto da label */
    .label-display {
      font-family: monospace;
      background-color: rgba(0,0,0,0.1);
      padding: 2px 6px;
      border-radius: 4px;
    }
    
    .dark .label-display {
      background-color: rgba(255,255,255,0.1);
    }
  </style>
</head>
<body class="dark">
  <div class="container py-4">
    <div class="d-flex justify-content-between align-items-center mb-4">
      <div>
        <h2 class="mb-1">
          <i class="bi bi-hdd-stack me-2" style="color: var(--portainer-blue)"></i> 
          Docker Discord Notify
        </h2>
        <p class="mb-0">
          <i class="bi bi-tag-fill me-1"></i>
          <span class="label-display">{{ trigger_label }}={{ trigger_value }}</span>
        </p>
      </div>
      <div>
        <i class="bi bi-moon-fill theme-toggle" id="themeToggle"></i>
      </div>
    </div>

    <div class="mb-3 d-flex justify-content-between align-items-center">
      <div class="d-flex gap-2">
        <span class="badge bg-success">
          <i class="bi bi-play-fill me-1"></i>
          <span id="runningCount">0</span>
        </span>
        <span class="badge bg-danger">
          <i class="bi bi-stop-fill me-1"></i>
          <span id="stoppedCount">0</span>
        </span>
      </div>
      <div class="last-updated">
        <i class="bi bi-clock-history me-1"></i>
        <span id="lastUpdated"></span>
      </div>
    </div>

    <div id="list"></div>
  </div>

  <script>
    // Tema
    const themeToggle = document.getElementById('themeToggle');
    const body = document.body;
    
    function initTheme() {
      const savedTheme = localStorage.getItem('theme') || 'dark';
      body.classList.add(savedTheme);
      themeToggle.className = savedTheme === 'dark' 
        ? 'bi bi-sun-fill theme-toggle' 
        : 'bi bi-moon-fill theme-toggle';
    }
    
    themeToggle.addEventListener('click', () => {
      const newTheme = body.classList.contains('dark') ? 'light' : 'dark';
      body.classList.remove('dark', 'light');
      body.classList.add(newTheme);
      localStorage.setItem('theme', newTheme);
      themeToggle.className = newTheme === 'dark' 
        ? 'bi bi-sun-fill theme-toggle' 
        : 'bi bi-moon-fill theme-toggle';
    });

    // Atualização de containers
    async function fetchContainers() {
      try {
        const res = await fetch('/api/containers');
        const data = await res.json();
        updateContainerList(data);
      } catch (error) {
        console.error('Error:', error);
        document.getElementById('list').innerHTML = `
          <div class="alert alert-danger">
            <i class="bi bi-exclamation-triangle-fill me-2"></i>
            Error loading containers
          </div>`;
      }
    }

    function updateContainerList(containers) {
      const list = document.getElementById('list');
      
      if(!containers.length) {
        list.innerHTML = `
          <div class="alert alert-info">
            <i class="bi bi-info-circle-fill me-2"></i>
            No containers found
          </div>`;
        return;
      }
      
      let running = 0;
      let stopped = 0;
      let html = '';
      
      containers.forEach(c => {
        if(c.Status === 'running') running++;
        else stopped++;
        
        html += `
          <div class="container-card">
            <div class="d-flex justify-content-between align-items-center">
              <div>
                <h6 class="mb-1 d-flex align-items-center">
                  <span class="status-indicator status-${c.Status} me-2"></span>
                  ${c.Name}
                  <small class="text-muted ms-2">${c.IdShort}</small>
                </h6>
                <div class="d-flex align-items-center gap-2">
                  <small class="text-muted">${c.Image.split(':')[0]}</small>
                  <span class="badge bg-${c.Status === 'running' ? 'success' : 'danger'}">
                    ${c.Status}
                  </span>
                </div>
              </div>
              <div class="d-flex gap-3">
                <div class="form-switch">
                  <input class="form-check-input" type="checkbox" 
                    id="start-${c.Id}" ${c.start ? 'checked' : ''}
                    onchange="toggleSetting('${c.Id}','start', this)">
                  <label class="form-check-label" for="start-${c.Id}">Start</label>
                </div>
                <div class="form-switch">
                  <input class="form-check-input" type="checkbox" 
                    id="stop-${c.Id}" ${c.stop ? 'checked' : ''}
                    onchange="toggleSetting('${c.Id}','stop', this)">
                  <label class="form-check-label" for="stop-${c.Id}">Stop</label>
                </div>
              </div>
            </div>
          </div>`;
      });
      
      document.getElementById('runningCount').textContent = running;
      document.getElementById('stoppedCount').textContent = stopped;
      document.getElementById('lastUpdated').textContent = new Date().toLocaleTimeString();
      list.innerHTML = html;
    }

    async function toggleSetting(id, eventType, element) {
      try {
        const response = await fetch('/api/toggle', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({id, event: eventType})
        });
        
        if(!response.ok) {
          element.checked = !element.checked;
          throw new Error('Request failed');
        }
        
        // Feedback visual
        const switchDiv = element.parentElement;
        switchDiv.classList.add('bg-opacity-10', 'bg-success');
        setTimeout(() => switchDiv.classList.remove('bg-opacity-10', 'bg-success'), 300);
        
      } catch (error) {
        console.error('Error:', error);
      }
    }

    // Inicialização
    document.addEventListener('DOMContentLoaded', () => {
      initTheme();
      fetchContainers();
      setInterval(fetchContainers, 5000);
    });
  </script>
</body>
</html>
"""

# Rotas
@app.route("/")
def index():
    global config
    config = load_config()
    return render_template_string(INDEX_HTML, trigger_label=TRIGGER_LABEL, trigger_value=TRIGGER_VALUE)

@app.route("/api/toggle", methods=["POST"])
def api_toggle():
    data = request.get_json()
    with config_lock:
        if data["id"] not in config:
            config[data["id"]] = {"start": True, "stop": True}
        config[data["id"]][data["event"]] = not config[data["id"]][data["event"]]
        save_config(config)
        print(f"🔄 Updated config for {data['id']}: {config[data['id']]}")
    return jsonify({"status": "ok"})

@app.route("/api/containers")
def api_containers():
    containers = []
    try:
        for container in client.containers.list(all=True):
            try:
                info = container.attrs
                labels = info.get("Config", {}).get("Labels", {}) or {}
                if labels.get(TRIGGER_LABEL) == TRIGGER_VALUE:
                    cid = container.id
                    with config_lock:
                        entry = config.get(cid, {"start": True, "stop": True})
                    
                    containers.append({
                        "Id": cid,
                        "IdShort": cid[:12],
                        "Name": container.name,
                        "Image": info.get("Config", {}).get("Image", ""),
                        "Status": container.status,
                        "start": entry.get("start", True),
                        "stop": entry.get("stop", True),
                    })
            except Exception as e:
                print(f"Error processing container: {e}")
    except Exception as e:
        print(f"Error listing containers: {e}")
    
    return jsonify(containers)

# Inicialização
if __name__ == "__main__":
    print("Starting Docker Events Monitor")
    print(f"Monitoring containers with label: {TRIGGER_LABEL}={TRIGGER_VALUE}")
    
    try:
        client.ping()
        print("Docker connection OK")
        
        # Inicializa configuração primeiro
        init_config()
        print(f"Initial config: {config}")
        
        # Verifica acesso ao /data
        try:
            with open(os.path.join(DATA_DIR, "test.txt"), "w") as f:
                f.write("test")
            os.remove(os.path.join(DATA_DIR, "test.txt"))
            print(f"✅ Verified write access to {DATA_DIR}")
        except Exception as e:
            print(f"❌ Cannot write to {DATA_DIR}: {e}")
        
        # Inicia listener
        threading.Thread(
            target=docker_events_listener,
            daemon=True,
            name="DockerEventsListener"
        ).start()
        
        # Inicia servidor web
        app.run(host="0.0.0.0", port=8080)
        
    except Exception as e:
        print(f"Failed to start: {e}")
        exit(1)
