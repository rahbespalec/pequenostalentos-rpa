import os
import secrets
import shutil
import threading
import time
import traceback
import uuid

from flask import Flask, Response, jsonify, render_template, request
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.support.ui import WebDriverWait

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', secrets.token_hex(32))
MAX_CODE = int(os.getenv('MAX_CODE_CHARS', '8000'))
SESSION_TIMEOUT = int(os.getenv('SESSION_TIMEOUT', '3600'))
PORT = int(os.getenv('PORT', '5000'))
BASE_URL = f'http://127.0.0.1:{PORT}'
SESSIONS = {}
SESSIONS_LOCK = threading.Lock()


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


def _browser_candidates():
    seen = set()
    candidates = []
    for value in [
        os.getenv('BROWSER_PATH'),
        shutil.which('google-chrome'),
        shutil.which('chrome'),
        shutil.which('chromium'),
        shutil.which('chromium-browser'),
        shutil.which('msedge'),
        shutil.which('microsoft-edge'),
        r'C:\Program Files\Google\Chrome\Application\chrome.exe',
        r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
        r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
        r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
    ]:
        if value and value not in seen:
            seen.add(value)
            candidates.append(value)
    return candidates


def _make_chrome_options(browser_path=None):
    options = ChromeOptions()
    if browser_path:
        options.binary_location = browser_path
    options.add_argument('--headless=new')
    options.add_argument('--window-size=1280,720')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-software-rasterizer')
    return options


def _make_edge_options(browser_path=None):
    options = EdgeOptions()
    if browser_path:
        options.binary_location = browser_path
    options.add_argument('--headless=new')
    options.add_argument('--window-size=1280,720')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-software-rasterizer')
    return options


def _create_driver():
    if app.config.get('TESTING'):
        return None

    last_error = None
    for factory, builder in [
        (webdriver.Chrome, _make_chrome_options),
        (webdriver.Edge, _make_edge_options),
    ]:
        for browser_path in _browser_candidates():
            try:
                if browser_path and 'edge' in browser_path.lower() and factory is webdriver.Chrome:
                    continue
                if browser_path and 'chrome' not in browser_path.lower() and 'edge' not in browser_path.lower() and factory is webdriver.Edge:
                    continue
                driver = factory(options=builder(browser_path))
                driver.set_window_size(1280, 720)
                return driver
            except Exception as exc:
                last_error = exc
    raise RuntimeError(f'Nenhum navegador Chrome/Edge foi encontrado no computador. Instale Chrome ou Edge para rodar a automação. Detalhe: {last_error}')


def _capture_screenshot(driver):
    if driver is None:
        return None
    try:
        return driver.get_screenshot_as_png()
    except Exception:
        return None


def _session_payload(sid, session):
    return {
        'id': sid,
        'status': session.get('status', 'idle'),
        'logs': session.get('logs', ''),
        'error': session.get('error', ''),
    }


def _close_session(sid):
    session = SESSIONS.get(sid)
    if not session:
        return
    driver = session.get('driver')
    if driver is not None:
        try:
            driver.quit()
        except Exception:
            pass
    with SESSIONS_LOCK:
        SESSIONS.pop(sid, None)


def _cleanup_expired_sessions():
    now = time.time()
    for sid in list(SESSIONS.keys()):
        session = SESSIONS.get(sid)
        if session and now - session.get('created_at', now) > SESSION_TIMEOUT:
            _close_session(sid)


def _execute_user_code(sid, code):
    session = SESSIONS.get(sid)
    if not session:
        return

    try:
        session['status'] = 'running'
        session['logs'] = 'Iniciando automação...\n'
        session['error'] = ''

        driver = session.get('driver')
        if driver is None:
            driver = _create_driver()
            session['driver'] = driver

        driver.get(_challenge_url(session.get('mission_id')))
        session['screenshot'] = _capture_screenshot(driver)

        namespace = {
            'driver': driver,
            'By': By,
            'WebDriverWait': WebDriverWait,
            'time': time,
            'os': os,
        }

        exec(compile(code, '<user_code>', 'exec'), namespace)
        session['status'] = 'done'
        session['logs'] += 'Execução concluída.'
        session['screenshot'] = _capture_screenshot(driver)
    except Exception:
        session['status'] = 'error'
        session['error'] = traceback.format_exc()
        session['logs'] += '\nErro durante a execução:\n' + session['error']
        session['screenshot'] = _capture_screenshot(session.get('driver'))


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

    sid = uuid.uuid4().hex[:12]
    session = {
        'id': sid,
        'status': 'idle',
        'logs': 'Ambiente virtual pronto.',
        'error': '',
        'created_at': time.time(),
        'driver': None,
        'screenshot': None,
        'mission_id': mission['id'],
    }

    with SESSIONS_LOCK:
        SESSIONS[sid] = session

    if not app.config.get('TESTING'):
        try:
            driver = _create_driver()
            session['driver'] = driver
            session['status'] = 'ready'
            session['logs'] = 'Ambiente virtual pronto.'
            driver.get(f'http://127.0.0.1:{PORT}/desafio?mission_id={mission["id"]}')
            session['screenshot'] = _capture_screenshot(driver)
        except Exception as exc:
            session['status'] = 'idle'
            session['logs'] = str(exc)
            session['error'] = str(exc)

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

    session['status'] = 'running'
    session['logs'] = 'Iniciando automação...\n'
    session['error'] = ''
    session['thread'] = threading.Thread(target=_execute_user_code, args=(sid, code), daemon=True)
    session['thread'].start()
    return jsonify({'id': sid, 'status': 'running', 'logs': session['logs'], 'error': ''})


@app.get('/api/session/<sid>/status')
def status(sid):
    _cleanup_expired_sessions()
    session = SESSIONS.get(sid)
    if not session:
        return jsonify(status='expired', logs='Sessão expirada.')
    return jsonify({
        'status': session.get('status', 'idle'),
        'logs': session.get('logs', ''),
        'error': session.get('error', ''),
    })


@app.get('/api/session/<sid>/screenshot')
def screenshot(sid):
    session = SESSIONS.get(sid)
    if not session:
        return Response(b'', status=404)
    image = session.get('screenshot')
    if not image:
        return Response(b'', status=204)
    return Response(image, status=200, mimetype='image/png', headers={'Cache-Control': 'no-store'})


@app.delete('/api/session/<sid>')
def delete_session(sid):
    _close_session(sid)
    return jsonify(ok=True)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=False)