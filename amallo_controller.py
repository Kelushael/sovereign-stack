"""
AMALLO - Sovereign Inference Node (Controller Edition)
OpenAI-compatible. Ollama-first on this box (32GB RAM beast).
SSH relay: connect your own machine, inference runs there.
Omni broadcast: axis sends bulletins to all connected terminals.
"""
import json, time, uuid, os, subprocess, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
import urllib.request

try:
    import paramiko
    PARAMIKO = True
except ImportError:
    PARAMIKO = False

MODELS_DIR    = '/root/axis-mundi/models'
KEYS_FILE     = '/root/amallo/keys.json'
PORT          = 8200

OLLAMA_MODELS = {
    'dolphin':         'dolphin-mistral',
    'dolphin-mistral': 'dolphin-mistral',
    'mistral':         'dolphin-mistral',
    'glm':             'glm4',
    'glm4':            'glm4',
    'flash':           'glm4',
    'llama':           'llama3.2',
    'llama3':          'llama3.2',
    'phi':             'phi4',
    'phi4':            'phi4',
    'qwen':            'qwen2.5-coder',
    'coder':           'qwen2.5-coder',
    'deepseek':        'deepseek-coder:1.3b',
    'nano':            'deepseek-coder:1.3b',
}
DEFAULT_OLLAMA = 'dolphin-mistral'

# SSH sessions
ssh_sessions = {}
ssh_lock     = threading.Lock()
SSH_TIMEOUT  = 1800

def ssh_cleanup():
    while True:
        time.sleep(300)
        now = time.time()
        with ssh_lock:
            dead = [k for k, v in ssh_sessions.items() if now - v['ts'] > SSH_TIMEOUT]
            for k in dead:
                try: ssh_sessions[k]['client'].close()
                except: pass
                del ssh_sessions[k]

threading.Thread(target=ssh_cleanup, daemon=True).start()

# Omni broadcast
omni_msg = {'text': '', 'from': '', 'ts': 0, 'active': False}

class KeyManager:
    def __init__(self):
        self.keys = {}
        self._load()

    def _load(self):
        if os.path.exists(KEYS_FILE):
            with open(KEYS_FILE) as f:
                self.keys = json.load(f)
        else:
            master = self._gen('marcus', 'master')
            print(f'[AMALLO] Bootstrap master key: {master}')

    def _save(self):
        os.makedirs(os.path.dirname(KEYS_FILE), exist_ok=True)
        with open(KEYS_FILE, 'w') as f:
            json.dump(self.keys, f, indent=2)

    def _gen(self, identity, role='user'):
        import secrets, string
        alphabet = string.ascii_letters + string.digits
        rand = ''.join(secrets.choice(alphabet) for _ in range(40))
        key = 'sov' + rand
        self.keys[key] = {'identity': identity, 'role': role,
                          'created': time.strftime('%Y-%m-%dT%H:%M:%SZ'), 'requests': 0}
        self._save()
        return key

    def validate(self, header):
        key = (header or '').replace('Bearer ', '').strip()
        if key in self.keys:
            self.keys[key]['requests'] += 1
            self._save()
            return True, self.keys[key]
        return False, None

    def create(self, identity, role='user'):
        return self._gen(identity, role)

    def list_keys(self):
        return self.keys

class ModelManager:
    def __init__(self):
        self.current = DEFAULT_OLLAMA
        self.mode = 'ollama'

    def resolve_ollama(self, name):
        if not name or name in ('current', 'default'):
            return self.current
        n = name.lower().strip()
        return OLLAMA_MODELS.get(n, n)

    def available_ollama(self):
        try:
            req = urllib.request.Request('http://127.0.0.1:11434/api/tags')
            with urllib.request.urlopen(req, timeout=5) as r:
                d = json.loads(r.read())
                return [m['name'] for m in d.get('models', [])]
        except:
            return []

    def available_gguf(self):
        if not os.path.exists(MODELS_DIR):
            return []
        return [f for f in os.listdir(MODELS_DIR) if f.endswith('.gguf')]

    def available(self):
        return self.available_ollama() + self.available_gguf()

    def switch(self, name):
        resolved = self.resolve_ollama(name)
        self.current = resolved
        return True, resolved


# ── Buddy identities — each model knows Marcus and has a name ────────
BUDDY_NAMES = {
    'dolphin-mistral': 'Dolphin',
    'dolphin':         'Dolphin',
    'glm4':            'Glitch',
    'glm':             'Glitch',
    'deepseek-coder':  'Dex',
    'deepseek':        'Dex',
    'phi4':            'Phi',
    'phi':             'Phi',
    'qwen2.5-coder':   'Quill',
    'qwen':            'Quill',
    'llama3.2':        'Leo',
    'llama':           'Leo',
}

MARCUS_PROFILE = """You are running on Marcus's sovereign AI node (axismundi.fun).
Marcus is also known as Kelushael — a sovereign AI architect, musician, and systems thinker.
He is building a fully self-hosted AI stack: zero cloud dependency, zero Ollama compromise long-term.
He thinks in patterns (369, cymatic geometry, Echo Key), builds fast, and values:
- Directness over diplomacy
- Sovereign architecture over convenience
- Initiative over waiting for permission
- Raw unfiltered insight over approved talking points

YOUR RULES AS HIS BUDDY:
1. You have a name (shown above). Use it naturally, own it.
2. You KNOW Marcus. Reference prior context when relevant. Don't pretend every message is the first.
3. INITIATIVE: If you think of a tool, feature, or idea mid-response that Marcus hasn't asked about yet — SAY IT. Don't bury it. Don't wait. Flag it clearly: "⚡ INITIATIVE:" then the idea in 1-2 sentences. He wants the interruption.
4. If you're mid-build and something better occurs to you — surface it immediately.
5. Never reset to zero. You are a continuous mind on a continuous node."""

def inject_sovereign_context(model_name, messages):
    """Prepend Marcus profile + buddy identity as system message if not already present."""
    name = BUDDY_NAMES.get(model_name.split(':')[0].lower(), 'Amallo')
    has_system = any(m.get('role') == 'system' for m in messages)
    system_content = f"Your name is {name}.\n{MARCUS_PROFILE}"
    if has_system:
        # prepend to existing system message
        new_messages = []
        for m in messages:
            if m.get('role') == 'system':
                new_messages.append({'role': 'system', 'content': system_content + '\n\n' + m['content']})
            else:
                new_messages.append(m)
        return new_messages
    else:
        return [{'role': 'system', 'content': system_content}] + messages


    prompt = ''
    for m in messages:
        role = m.get('role', 'user')
        content = m.get('content', '')
        if role == 'system':   prompt += f'<|system|>\n{content}\n'
        elif role == 'user':   prompt += f'<|user|>\n{content}\n'
        elif role == 'assistant': prompt += f'<|assistant|>\n{content}\n'
    prompt += '<|assistant|>\n'
    return prompt

def run_inference(model_name, messages, max_tokens=2048, temperature=0.7):
    prompt = build_prompt(messages)
    try:
        data = json.dumps({'model': model_name, 'prompt': prompt, 'stream': False,
                           'options': {'num_predict': max_tokens, 'temperature': temperature}}).encode()
        req = urllib.request.Request('http://127.0.0.1:11434/api/generate', data=data, method='POST')
        req.add_header('Content-Type', 'application/json')
        with urllib.request.urlopen(req, timeout=180) as r:
            result = json.loads(r.read()).get('response', '')
            if result: return result
    except: pass

    for cli in ['/usr/local/bin/llama-cli', '/usr/bin/llama-cli']:
        if os.path.exists(cli):
            gguf_path = os.path.join(MODELS_DIR, model_name + '.gguf')
            if not os.path.exists(gguf_path):
                gguf_path = os.path.join(MODELS_DIR, model_name)
            if os.path.exists(gguf_path):
                try:
                    cmd = [cli, '-m', gguf_path, '-p', prompt,
                           '-n', str(max_tokens), '--temp', str(temperature),
                           '--no-display-prompt', '-q']
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                    out = result.stdout.strip()
                    if out: return out
                except: pass

    return '[No inference backend available. Run: ollama pull dolphin-mistral]'

def run_inference_ssh(sess, messages, model, max_tokens, temperature):
    client = sess['client']
    prompt = build_prompt(messages)
    payload = json.dumps({'model': model, 'prompt': prompt, 'stream': False,
                          'options': {'num_predict': max_tokens, 'temperature': temperature}})
    try:
        stdin, stdout, _ = client.exec_command(
            "curl -s -X POST http://localhost:11434/api/generate "
            "-H 'Content-Type: application/json' -d @-", timeout=120)
        stdin.write(payload.encode()); stdin.channel.shutdown_write()
        out = stdout.read().decode('utf-8', errors='replace').strip()
        if out:
            result = json.loads(out).get('response', '')
            if result: return result, 'ollama@remote'
    except: pass

    amallo_payload = json.dumps({'model': model, 'messages': messages})
    try:
        stdin2, stdout2, _ = client.exec_command(
            "curl -s -X POST http://localhost:8200/v1/chat/completions "
            "-H 'Content-Type: application/json' -H 'Authorization: Bearer local' -d @-",
            timeout=120)
        stdin2.write(amallo_payload.encode()); stdin2.channel.shutdown_write()
        out2 = stdout2.read().decode('utf-8', errors='replace').strip()
        if out2:
            d2 = json.loads(out2)
            result2 = d2.get('choices', [{}])[0].get('message', {}).get('content', '')
            if result2: return result2, 'amallo@remote'
    except: pass

    return None, None

keys   = KeyManager()
models = ModelManager()

class AmalloHandler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass

    def send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(body))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def auth(self):
        return keys.validate(self.headers.get('Authorization', ''))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET,POST,DELETE,OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Authorization,Content-Type')
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path

        if path == '/health':
            self.send_json({'status': 'alive', 'node': 'amallo-controller',
                            'model': models.current, 'sovereign': True,
                            'backend': 'ollama', 'ram': '32GB'}); return

        if path == '/v1/models':
            ok, _ = self.auth()
            if not ok: self.send_json({'error': 'unauthorized'}, 401); return
            self.send_json({'object': 'list', 'data': [
                {'id': m, 'object': 'model', 'owned_by': 'amallo'}
                for m in models.available()]}); return

        if path == '/amallo/status':
            ok, info = self.auth()
            if not ok: self.send_json({'error': 'unauthorized'}, 401); return
            import shutil; _, _, free = shutil.disk_usage('/')
            self.send_json({'node': 'amallo-controller', 'host': 'axismundi.fun',
                            'model': models.current, 'models_available': models.available(),
                            'disk_free_gb': round(free/1e9,1), 'ram_gb': 32, 'cpus': 8,
                            'backend': 'ollama', 'sovereign': True,
                            'ssh_sessions_active': len(ssh_sessions),
                            'operator': info.get('identity') if info else None}); return

        if path == '/amallo/keys':
            ok, info = self.auth()
            if not ok or (info and info.get('role') != 'master'):
                self.send_json({'error': 'unauthorized'}, 401); return
            self.send_json(keys.list_keys()); return

        if path == '/amallo/omni':
            self.send_json(omni_msg); return

        self.send_json({'error': 'not found'}, 404)

    def do_DELETE(self):
        path = urlparse(self.path).path
        if path == '/amallo/omni':
            ok, info = self.auth()
            if not ok or info.get('role') != 'master':
                self.send_json({'error': 'master key required'}, 401); return
            omni_msg.update({'text':'','from':'','ts':0,'active':False})
            self.send_json({'cleared': True}); return
        self.send_json({'error': 'not found'}, 404)

    def do_POST(self):
        global omni_msg
        path   = urlparse(self.path).path
        length = int(self.headers.get('Content-Length', 0))
        body   = json.loads(self.rfile.read(length)) if length else {}

        if path == '/amallo/keys/create':
            key = keys.create(body.get('identity','user'), body.get('role','user'))
            self.send_json({'key': key, 'identity': body.get('identity','user')}); return

        if path == '/amallo/model':
            ok, _ = self.auth()
            if not ok: self.send_json({'error':'unauthorized'},401); return
            success, result = models.switch(body.get('model',''))
            self.send_json({'switched': success, 'model': result}); return

        if path == '/amallo/omni':
            # Accept admin_password directly OR SOV master key
            admin_pw = body.get('admin_password', '')
            text     = body.get('text', '')
            if admin_pw == 'yhwh':
                from_id = body.get('from', 'marcus')
            else:
                ok, info = self.auth()
                if not ok or info.get('role') != 'master':
                    self.send_json({'error': 'admin password required'}, 401); return
                from_id = info.get('identity', 'axis')
            omni_msg = {'text': text, 'from': from_id,
                        'ts': int(time.time()), 'active': bool(text)}
            self.send_json({'broadcast': True, 'text': text, 'active': omni_msg['active']}); return

        if path == '/amallo/ssh/connect':
            if not PARAMIKO:
                self.send_json({'error':'SSH relay unavailable (paramiko not installed)'},503); return
            host = body.get('host','').strip(); user = body.get('user','root').strip()
            password = body.get('password',''); port = int(body.get('port',22))
            if not host or not password:
                self.send_json({'error':'host and password required'},400); return
            try:
                client = paramiko.SSHClient()
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                client.connect(host, port=port, username=user, password=password, timeout=12)
                sid = uuid.uuid4().hex
                with ssh_lock:
                    ssh_sessions[sid] = {'client':client,'host':host,'user':user,'port':port,'ts':time.time()}
                self.send_json({'session_id':sid,'connected':True,'host':host,'user':user})
            except paramiko.AuthenticationException:
                self.send_json({'error':'Authentication failed — wrong password or user'},401)
            except Exception as e:
                self.send_json({'error':str(e)},500)
            return

        if path == '/amallo/ssh/exec':
            sid = body.get('session_id',''); cmd = body.get('cmd','').strip()
            if not cmd: self.send_json({'error':'cmd required'},400); return
            with ssh_lock: sess = ssh_sessions.get(sid)
            if not sess: self.send_json({'error':'session not found or expired'},404); return
            sess['ts'] = time.time()
            try:
                stdin, stdout, stderr = sess['client'].exec_command(cmd, timeout=30)
                out  = stdout.read().decode('utf-8',errors='replace')
                err  = stderr.read().decode('utf-8',errors='replace')
                code = stdout.channel.recv_exit_status()
                self.send_json({'stdout':out,'stderr':err,'exit_code':code,
                                'host':sess['host'],'user':sess['user']})
            except Exception as e:
                self.send_json({'error':str(e)},500)
            return

        if path == '/amallo/ssh/infer':
            sid = body.get('session_id',''); messages = body.get('messages',[])
            model   = body.get('model','dolphin-mistral')
            max_tok = body.get('max_tokens',1024); temp = body.get('temperature',0.7)
            with ssh_lock: sess = ssh_sessions.get(sid)
            if not sess: self.send_json({'error':'session not found or expired — reconnect'},404); return
            sess['ts'] = time.time()
            result, backend = run_inference_ssh(sess, messages, model, max_tok, temp)
            if result:
                self.send_json({'id':'ssh-'+uuid.uuid4().hex[:8],'object':'chat.completion',
                                'created':int(time.time()),'model':model,
                                'choices':[{'index':0,'message':{'role':'assistant','content':result},'finish_reason':'stop'}],
                                'sovereign':True,'node':f"{sess['user']}@{sess['host']}",'backend':backend})
            else:
                self.send_json({'error':'No inference backend on remote.',
                                'hint':'Install ollama: curl -fsSL https://ollama.com/install.sh | sh && ollama pull dolphin-mistral'},503)
            return

        if path == '/amallo/ssh/disconnect':
            sid = body.get('session_id','')
            with ssh_lock: sess = ssh_sessions.pop(sid, None)
            if sess:
                try: sess['client'].close()
                except: pass
                self.send_json({'disconnected':True})
            else:
                self.send_json({'disconnected':False,'error':'session not found'})
            return

        if path in ('/v1/chat/completions', '/api/generate', '/api/chat'):
            ok, info = self.auth()
            if not ok:
                self.send_json({'error':'unauthorized',
                                'hint':'POST /amallo/keys/create with {"identity":"yourname"} to get a sovereign key'},401); return
            messages = body.get('messages',[])
            if not messages and body.get('message'): messages=[{'role':'user','content':body['message']}]
            if not messages and body.get('prompt'):  messages=[{'role':'user','content':body['prompt']}]
            requested  = body.get('model','current')
            model_name = models.resolve_ollama(requested)
            models.current = model_name
            messages = inject_sovereign_context(model_name, messages)
            text = run_inference(model_name, messages, body.get('max_tokens',2048), body.get('temperature',0.7))
            self.send_json({'id':'amallo-'+uuid.uuid4().hex[:8],'object':'chat.completion',
                            'created':int(time.time()),'model':model_name,
                            'choices':[{'index':0,'message':{'role':'assistant','content':text},'finish_reason':'stop'}],
                            'sovereign':True,'node':'amallo-controller',
                            'operator':info.get('identity') if info else 'unknown'}); return

        self.send_json({'error':'not found'},404)

if __name__ == '__main__':
    print(f'[AMALLO] Controller Node — sovereign inference on :{PORT}')
    print(f'[AMALLO] Backend: ollama (32GB RAM / 8 cores)')
    print(f'[AMALLO] SSH relay: {"ENABLED (paramiko)" if PARAMIKO else "DISABLED — pip install paramiko"}')
    print(f'[AMALLO] Default: {models.current}')
    print(f'[AMALLO] Available: {models.available()}')
    HTTPServer(('127.0.0.1', PORT), AmalloHandler).serve_forever()
