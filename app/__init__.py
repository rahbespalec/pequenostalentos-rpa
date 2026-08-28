import os
import secrets
import threading
import time
import uuid

import requests
from flask import Flask, Response, jsonify, render_template, request

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', secrets.token_hex(32))
MAX_CODE = int(os.getenv('MAX_CODE_CHARS', '8000'))
SESSION_TIMEOUT = int(os.getenv('SESSION_TIMEOUT', '3600'))
PORT = int(os.getenv('PORT', '5000'))
BASE_URL = os.getenv('INTERNAL_BASE_URL', f'http://web:{PORT}')
RUNNER_URL = os.getenv('RUNNER_URL', 'http://runner:7000')
RUNNER_TOKEN = os.getenv('RUNNER_TOKEN', 'dev-runner-token')
SESSIONS = {}
SESSIONS_LOCK = threading.Lock()


def _runner_headers():
    return {'X-Runner-Token': RUNNER_TOKEN}


def _challenge_url(mission_id=None):
    if mission_id:
        return f'{BASE_URL}/desafio?mission_id={mission_id}'
    return f'{BASE_URL}/desafio'


@app.context_processor
def inject_static_version():
    try:
        base = os.path.join(app.root_path, 'static')
        candidates = [
            os.path.join('css', 'style.css'),
            os.path.join('js', 'app.js'),
        ]
        mtimes = []
        for rel in candidates:
            fp = os.path.join(base, rel)
            if os.path.exists(fp):
                mtimes.append(str(int(os.path.getmtime(fp))))
        if mtimes:
            return {'static_version': max(mtimes)}
    except Exception:
        pass
    return {'static_version': str(int(time.time()))}

STARTER = f'''# Missão 01 - Cadastro inicial
# O navegador virtual já está pronto.

from selenium.webdriver.common.by import By

driver.get("{_challenge_url('mission-01')}")

# 1. Encontre o campo de nome
# 2. Digite seu nome
# 3. Clique em Cadastrar

# Dica:
# campo = driver.find_element(By.ID, "nome")
# campo.send_keys("Seu Nome")
# driver.find_element(By.ID, "cadastrar").click()
'''

MISSIONS = [
    {
        'id': 'mission-01',
        'number': '01',
        'title': 'Cadastro',
        'difficulty': 1,
        'summary': 'Preencha um campo simples e confirme o cadastro inicial.',
        'description': 'Primeiro contato com o desafio: identificar o campo e validar o fluxo de cadastro.',
        'tasks': ['Localizar o campo', 'Preencher o nome', 'Confirmar o cadastro'],
        'starter': STARTER,
    },
    {
        'id': 'mission-02',
        'number': '02',
        'title': 'Contato',
        'difficulty': 2,
        'summary': 'Escolha a opção correta em um select para seguir o fluxo.',
        'description': 'Agora o robô precisa entender um formulário com seleção de canais e seguir para a próxima etapa.',
        'tasks': ['Abrir o menu de canais', 'Selecionar a opção certa', 'Continuar no formulário'],
        'starter': f'''# Missão 02 - Seleção de canal
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select

driver.get("{_challenge_url('mission-02')}")

# 1. Localize o select de canal
# 2. Escolha "email"
# 3. Clique em continuar
# Dica:
# select = Select(driver.find_element(By.ID, "canal"))
# select.select_by_value("email")
# driver.find_element(By.ID, "continuar").click()
''',
    },
    {
        'id': 'mission-03',
        'number': '03',
        'title': 'Preferências',
        'difficulty': 3,
        'summary': 'Combine checkboxes e radios para personalizar a experiência.',
        'description': 'A terceira fase usa múltiplos campos e exige mais atenção ao combinar respostas.',
        'tasks': ['Marcar opções relevantes', 'Escolher perfil', 'Salvar preferências'],
        'starter': f'''# Missão 03 - Preferências
from selenium.webdriver.common.by import By

driver.get("{_challenge_url('mission-03')}")

# 1. Marque a opção de notificações
# 2. Selecione o perfil "profissional"
# 3. Clique em salvar preferências
# Dica:
# driver.find_element(By.ID, "notificacoes").click()
# driver.find_element(By.ID, "perfil-profissional").click()
# driver.find_element(By.ID, "salvar-preferencias").click()
''',
    },
    {
        'id': 'mission-04',
        'number': '04',
        'title': 'Cadastro completo',
        'difficulty': 4,
        'summary': 'Monte um formulário completo com select, checkbox, rádio e observações.',
        'description': 'A missão final reúne todos os elementos de um formulário real: seleção, opções, além de texto livre para concluir a jornada.',
        'tasks': ['Escolher setor', 'Ativar funcionalidades', 'Definir prioridade', 'Enviar formulário'],
        'starter': f'''# Missão 04 - Cadastro completo
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select

driver.get("{_challenge_url('mission-04')}")

# 1. Selecione o setor "tecnologia"
# 2. Marque "relatórios" e "automacao"
# 3. Escolha a prioridade "alta"
# 4. Escreva uma observação
# 5. Clique em concluir cadastro
# Dica:
# Select(driver.find_element(By.ID, "setor")).select_by_value("tecnologia")
# driver.find_element(By.ID, "relatorios").click()
# driver.find_element(By.ID, "prioridade-alta").click()
# driver.find_element(By.ID, "observacoes").send_keys("Tudo ok")
# driver.find_element(By.ID, "concluir").click()
''',
    },
]


def _session_payload(sid, session):
    return {
        'id': sid,
        'status': session.get('status', 'idle'),
        'logs': session.get('logs', ''),
        'error': session.get('error', ''),
    }


def _close_session(sid):
    with SESSIONS_LOCK:
        session = SESSIONS.pop(sid, None)
    runner_id = session.get('runner_id') if session else None
    if runner_id:
        try:
            requests.delete(f'{RUNNER_URL}/sessions/{runner_id}', headers=_runner_headers(), timeout=5)
        except Exception:
            pass


def _cleanup_expired_sessions():
    now = time.time()
    for sid in list(SESSIONS.keys()):
        session = SESSIONS.get(sid)
        if session and now - session.get('created_at', now) > SESSION_TIMEOUT:
            _close_session(sid)


@app.get('/')
def index():
    return render_template('index.html', missions=MISSIONS, starter=STARTER)


@app.get('/api/missions')
def missions_route():
    return jsonify(MISSIONS)


@app.get('/desafio')
def desafio():
    mission_id = request.args.get('mission_id', 'mission-01')
    mission = next((item for item in MISSIONS if item['id'] == mission_id), MISSIONS[0])
    return render_template('challenge.html', mission=mission, missions=MISSIONS)


@app.get('/health')
def health():
    _cleanup_expired_sessions()
    return jsonify(ok=True, sessions=len(SESSIONS))


@app.post('/api/session')
def create_session():
    data = request.get_json(silent=True) or {}
    mission_id = data.get('mission_id', 'mission-01')
    mission = next((item for item in MISSIONS if item['id'] == mission_id), MISSIONS[0])

    session = {
        'status': 'idle',
        'logs': 'Ambiente virtual pronto.',
        'error': '',
        'created_at': time.time(),
        'mission_id': mission['id'],
        'runner_id': None,
    }

    try:
        resp = requests.post(f'{RUNNER_URL}/sessions', headers=_runner_headers(), timeout=(5, 15))
        payload = resp.json()
        if resp.status_code >= 400:
            raise RuntimeError(payload.get('error', 'Não foi possível iniciar o ambiente.'))
        session['runner_id'] = payload['id']
        session['status'] = 'ready'
        session['logs'] = 'Ambiente virtual pronto.'
    except Exception as exc:
        session['status'] = 'idle'
        session['logs'] = str(exc)
        session['error'] = str(exc)

    sid = uuid.uuid4().hex[:12]
    with SESSIONS_LOCK:
        SESSIONS[sid] = session

    return jsonify(_session_payload(sid, session))


@app.post('/api/session/<sid>/run')
def run_session(sid):
    session = SESSIONS.get(sid)
    if not session:
        return jsonify(error='Sessão expirada.'), 404

    data = request.get_json(silent=True) or {}
    code = data.get('code', '')
    if not isinstance(code, str) or not code.strip():
        return jsonify(error='Digite um código antes de executar.'), 400
    if len(code) > MAX_CODE:
        return jsonify(error=f'O código pode ter no máximo {MAX_CODE} caracteres.'), 400

    runner_id = session.get('runner_id')
    if not runner_id:
        return jsonify(error='Ambiente virtual indisponível. Recarregue a página.'), 503

    try:
        resp = requests.post(
            f'{RUNNER_URL}/sessions/{runner_id}/run',
            json={'code': code},
            headers=_runner_headers(),
            timeout=(5, 15),
        )
        payload = resp.json()
    except Exception as exc:
        return jsonify(error=f'Falha ao conversar com o ambiente: {exc}'), 502

    if resp.status_code >= 400:
        return jsonify(payload), resp.status_code

    session['status'] = 'running'
    return jsonify(payload)


@app.get('/api/session/<sid>/status')
def status(sid):
    _cleanup_expired_sessions()
    session = SESSIONS.get(sid)
    if not session:
        return jsonify(status='expired', logs='Sessão expirada.')

    runner_id = session.get('runner_id')
    if not runner_id:
        return jsonify({
            'status': session.get('status', 'idle'),
            'logs': session.get('logs', ''),
            'error': session.get('error', ''),
        })

    try:
        resp = requests.get(f'{RUNNER_URL}/sessions/{runner_id}/status', headers=_runner_headers(), timeout=5)
        payload = resp.json()
    except Exception:
        return jsonify(status='error', logs='Ambiente indisponível.')

    session['status'] = payload.get('status', session.get('status'))
    return jsonify(payload)


@app.get('/api/session/<sid>/screenshot')
def screenshot(sid):
    session = SESSIONS.get(sid)
    if not session:
        return Response(b'', status=404)

    runner_id = session.get('runner_id')
    if not runner_id:
        return Response(b'', status=204)

    try:
        resp = requests.get(f'{RUNNER_URL}/sessions/{runner_id}/screenshot', headers=_runner_headers(), timeout=5)
    except Exception:
        return Response(b'', status=503)

    if resp.status_code != 200 or not resp.content:
        return Response(b'', status=204)

    return Response(resp.content, status=200, mimetype='image/jpeg', headers={'Cache-Control': 'no-store'})


@app.delete('/api/session/<sid>')
def delete_session(sid):
    _close_session(sid)
    return jsonify(ok=True)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=False)
