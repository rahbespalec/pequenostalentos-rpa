import os, time, uuid, threading, subprocess, requests
from flask import Flask, request, jsonify, Response

app=Flask(__name__)
TOKEN=os.getenv('RUNNER_TOKEN','dev-runner-token')
MAX=int(os.getenv('MAX_SESSIONS','30'))
TTL=int(os.getenv('JOB_TTL','900'))
CPU=os.getenv('JOB_CPU','0.75')
MEM=os.getenv('JOB_MEMORY','512m')
IMAGE=os.getenv('JOB_IMAGE','rpa-job:latest')
NETWORK=os.getenv('NETWORK','rpa_lab_network')
jobs={}
lock=threading.Lock()

def auth(): return request.headers.get('X-Runner-Token')==TOKEN

def cleanup_loop():
  while True:
    time.sleep(30); now=time.time()
    with lock: items=list(jobs.items())
    for sid,j in items:
      if now-j['created']>TTL:
        remove(sid)

def remove(sid):
  with lock: j=jobs.pop(sid,None)
  if j:
    subprocess.run(['docker','rm','-f',j['container']],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

@app.before_request

def guard():
  if not auth(): return jsonify(error='unauthorized'),401

@app.post('/sessions')
def create():
  with lock:
    active=len(jobs)
  if active>=MAX:return jsonify(error='Todos os ambientes estão ocupados. Tente novamente em alguns segundos.'),429
  data=request.get_json(silent=True) or {}
  url=data.get('url')
  sid=uuid.uuid4().hex[:12]; cname='rpa-job-'+sid
  cmd=['docker','run','-d','--name',cname,'--network',NETWORK,'--cpus',CPU,'--memory',MEM,'--pids-limit','180','--read-only','--tmpfs','/tmp:rw,nosuid,nodev','--tmpfs','/run:rw,nosuid,nodev','--tmpfs','/root:rw,nosuid,nodev',IMAGE]
  p=subprocess.run(cmd,capture_output=True,text=True)
  if p.returncode!=0:return jsonify(error='Não foi possível iniciar o navegador virtual.',detail=p.stderr[-500:]),500
  with lock: jobs[sid]={'container':cname,'created':time.time()}
  for _ in range(40):
    try:
      r=requests.get(f'http://{cname}:9000/health',timeout=1)
      if r.ok:
        if url:
          try:requests.post(f'http://{cname}:9000/run',json={'code':f'driver.get({url!r})'},timeout=3)
          except Exception:pass
        return jsonify(id=sid)
    except Exception:pass
    time.sleep(.25)
  remove(sid);return jsonify(error='O navegador demorou demais para iniciar.'),504

@app.post('/sessions/<sid>/run')
def run(sid):
  j=jobs.get(sid)
  if not j:return jsonify(error='Sessão expirada.'),404
  try:r=requests.post(f"http://{j['container']}:9000/run",json=request.get_json(force=True),timeout=3)
  except Exception as e:return jsonify(error='Falha ao conversar com o ambiente.',detail=str(e)),502
  return Response(r.content,status=r.status_code,content_type='application/json')

@app.get('/sessions/<sid>/status')
def status(sid):
  j=jobs.get(sid)
  if not j:return jsonify(status='error',logs='Sessão expirada.')
  try:r=requests.get(f"http://{j['container']}:9000/status",timeout=3);return Response(r.content,status=r.status_code,content_type='application/json')
  except Exception:return jsonify(status='error',logs='Ambiente indisponível.')

@app.get('/sessions/<sid>/screenshot')
def shot(sid):
  j=jobs.get(sid)
  if not j:return Response(b'',status=404)
  try:r=requests.get(f"http://{j['container']}:9000/screenshot",timeout=5);return Response(r.content,status=r.status_code,content_type='image/jpeg',headers={'Cache-Control':'no-store'})
  except Exception:return Response(b'',status=503)

@app.delete('/sessions/<sid>')
def delete(sid): remove(sid);return jsonify(ok=True)

threading.Thread(target=cleanup_loop,daemon=True).start()
app.run(host='0.0.0.0',port=7000,threaded=True)
