import ast, io, os, time, threading, traceback, contextlib
from flask import Flask, jsonify, Response, request
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

app=Flask(__name__)
driver=None
state={'status':'ready','logs':'Navegador virtual pronto.','started':None}
run_lock=threading.Lock()
ALLOWED_IMPORTS={'selenium','time'}
MAX_CODE=8000

def browser():
 global driver
 opts=webdriver.ChromeOptions();opts.add_argument('--no-sandbox');opts.add_argument('--disable-dev-shm-usage');opts.add_argument('--window-size=1100,680');opts.add_argument('--disable-gpu');opts.add_argument('--disable-notifications');opts.add_argument('--no-first-run');opts.add_argument('--no-default-browser-check');opts.add_argument('--disable-popup-blocking')
 driver=webdriver.Chrome(options=opts);driver.set_page_load_timeout(15)

def safe_import(name,globals=None,locals=None,fromlist=(),level=0):
 root=name.split('.')[0]
 if root not in ALLOWED_IMPORTS: raise ImportError(f'Importação não permitida: {name}')
 return __import__(name,globals,locals,fromlist,level)

def validate(code):
 if len(code)>MAX_CODE:raise ValueError('Código muito grande.')
 tree=ast.parse(code)
 banned=(ast.With,ast.AsyncWith,ast.Try,ast.Lambda,ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef)
 for n in ast.walk(tree):
  if isinstance(n,(ast.Import,ast.ImportFrom)):
   names=[a.name for a in n.names]
   for x in names:
    if x.split('.')[0] not in ALLOWED_IMPORTS: raise ValueError(f'Importação não permitida: {x}')
  if isinstance(n,banned):raise ValueError('Esta construção ainda não faz parte deste desafio.')
  if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id in {'open','exec','eval','compile','input','breakpoint','__import__'}:raise ValueError(f'Comando não permitido: {n.func.id}')
  if isinstance(n,ast.Attribute) and n.attr in {'system','popen','remove','unlink','rmtree','walk','listdir'}:raise ValueError('Acesso ao sistema de arquivos não permitido.')

def execute(code):
 global driver
 with run_lock:
  state.update(status='running',started=time.time(),logs='Executando automação...')
  try:
   validate(code)
   if driver is None:browser()
   out=io.StringIO();err=io.StringIO()
   safe={'__builtins__':{'len':len,'range':range,'str':str,'int':int,'float':float,'bool':bool,'print':print,'min':min,'max':max,'enumerate':enumerate,'list':list},'webdriver':webdriver,'By':By,'WebDriverWait':WebDriverWait,'EC':EC,'time':time,'driver':driver,'__import__':safe_import}
   with contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):exec(compile(ast.parse(code),'student_code.py','exec'),safe,{})
   state['logs']='\n'.join(x for x in ['Automação executada.','',out.getvalue().strip(), ''] if x) or 'Automação concluída.'
   state['status']='done'
  except Exception:
   state['status']='error';state['logs']='Erro na automação:\n'+traceback.format_exc(limit=3)

@app.get('/health')
def health():return jsonify(ok=True)
@app.get('/status')
def status():return jsonify(state)
@app.get('/screenshot')
def screenshot():
 try:
  if driver is None:browser()
  return Response(driver.get_screenshot_as_png(),mimetype='image/png')
 except Exception:return Response(b'',status=503)
@app.post('/run')
def run():
 if state['status']=='running':return jsonify(error='O robô já está executando.'),409
 data=request.get_json(silent=True) or {};code=data.get('code','')
 if not isinstance(code,str) or not code.strip():return jsonify(error='Código vazio.'),400
 threading.Thread(target=execute,args=(code,),daemon=True).start()
 return jsonify(ok=True,message='Seu código foi enviado ao robô.')

os.environ['DISPLAY']=':99'
threading.Thread(target=lambda: (os.system('Xvfb :99 -screen 0 1100x680x24 >/tmp/xvfb.log 2>&1 &'),os.system('fluxbox >/tmp/fluxbox.log 2>&1 &')),daemon=True).start()
time.sleep(1)
browser()
app.run(host='0.0.0.0',port=9000,threaded=True)
