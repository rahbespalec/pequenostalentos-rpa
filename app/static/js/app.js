let editor, pollTimer, currentMissionId = 'mission-01';
const sessionByMission = {};
const missionList = Array.isArray(window.MISSION_STARTERS) ? window.MISSION_STARTERS : [];
const missionMap = Object.fromEntries(missionList.map((mission) => [mission.id, mission]));

function getMissionById(missionId) {
  return missionMap[missionId] || missionList[0];
}

function refreshSessionPreview(sid) {
  const preview = document.getElementById('missionPreview');
  const screen = document.getElementById('screen');
  const screenEmpty = document.getElementById('screenEmpty');
  const timestamp = Date.now();
  const url = `/api/session/${sid}/screenshot?x=${timestamp}`;

  if (preview) {
    preview.src = url;
    preview.style.display = 'block';
  }

  if (screen && screenEmpty) {
    screen.src = url;
    screen.style.display = 'block';
    screenEmpty.style.display = 'none';
  }
}

function applyMission(missionId) {
  const mission = getMissionById(missionId);
  if (!mission) return;

  currentMissionId = mission.id;
  const tag = document.getElementById('currentMissionTag');
  const title = document.getElementById('currentMissionTitle');
  const summary = document.getElementById('currentMissionSummary');
  const progress = document.getElementById('currentMissionProgress');
  const bar = document.getElementById('currentMissionBar');
  const taskList = document.getElementById('currentMissionTasks');

  if (tag) tag.textContent = `MISSÃO ${mission.number}`;
  if (title) title.textContent = mission.title;
  if (summary) summary.textContent = mission.summary;
  const missionLink = document.getElementById('missionLink');
  if (missionLink) missionLink.href = `/desafio?mission_id=${mission.id}`;

  const progressByMission = {
    'mission-01': '24%',
    'mission-02': '48%',
    'mission-03': '72%',
    'mission-04': '100%',
  };
  if (progress) progress.textContent = progressByMission[mission.id] || '24%';
  if (bar) bar.style.width = progressByMission[mission.id] || '24%';

  if (taskList && Array.isArray(mission.tasks)) {
    taskList.innerHTML = mission.tasks.map((task, index) => {
      return `<li class="${index < mission.tasks.length - 1 ? 'done' : ''}">${task}</li>`;
    }).join('');
  }

  document.querySelectorAll('.phase-card').forEach((button) => {
    button.classList.toggle('phase-card--active', button.dataset.missionId === mission.id);
  });

  if (editor && mission.starter) {
    editor.setValue(mission.starter);
  }

  ensureSessionForMission(mission.id).then((sid) => {
    refreshSessionPreview(sid);
    ensurePollingForMission(mission.id);
  }).catch(() => {});
}

require.config({ paths:{vs:'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.52.2/min/vs'} });
require(['vs/editor/editor.main'], function(){
  editor = monaco.editor.create(document.getElementById('editor'), {
    value: window.STARTER,
    language: 'python',
    theme: 'vs',
    fontSize: 13,
    minimap: { enabled: false },
    automaticLayout: true,
    scrollBeyondLastLine: false,
    padding: { top: 14, bottom: 14 },
    roundedSelection: false,
    wordWrap: 'on',
    lineNumbers: 'on'
  });

  document.querySelectorAll('.phase-card').forEach((button) => {
    button.addEventListener('click', async () => {
      const missionId = button.dataset.missionId;
      const unlocked = getUnlockedMissions();
      if (!unlocked.includes(missionId)) return;
      applyMission(missionId);
    });
  });

  if (missionList.length) {
    // initialize unlocked missions in localStorage if empty
    const unlocked = getUnlockedMissions();
    if (!unlocked || !unlocked.length) {
      setUnlockedMissions([missionList[0].id]);
    }
    renderPhaseLocks();
    applyMission(missionList[0].id);
  }
});

async function createSession(missionId){
  setStatus('Criando ambiente…', 'running');
  try {
    const response = await fetch('/api/session', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mission_id: missionId })
    });
    const data = await response.json();
    if (!response.ok) throw Error(data.error || 'Não foi possível criar o ambiente.');
    if (data.status !== 'ready') {
      throw Error(data.error || data.logs || 'Ambiente indisponível no momento. Tente novamente em instantes.');
    }

    sessionByMission[missionId] = data.id;
    log('Ambiente virtual pronto.');
    setStatus('Pronto', 'idle');
    ensurePollingForMission(missionId);
    return data.id;
  } catch (error) {
    log(error.message);
    setStatus('Erro', 'error');
    throw error;
  }
}

async function ensureSessionForMission(missionId){
  if (sessionByMission[missionId]) return sessionByMission[missionId];
  return await createSession(missionId);
}

function ensurePollingForMission(missionId){
  clearInterval(pollTimer);
  pollTimer = setInterval(() => {
    const sid = sessionByMission[missionId];
    if (!sid) return;
    refreshSessionPreview(sid);
  }, 2000);
}

function setStatus(text, state){
  const element = document.getElementById('status');
  if (!element) return;
  element.textContent = text;
  element.className = 'status ' + state;
}

function log(text){
  const logs = document.getElementById('logs');
  if (!logs) return;
  logs.textContent += (logs.textContent ? '\n' : '') + text;
}

async function run(){
  if (!editor) return;

  const button = document.getElementById('run');
  button.disabled = true;
  setStatus('Executando…', 'running');
  log('');
  log('Iniciando automação...');

  try {
    const sid = await ensureSessionForMission(currentMissionId);

    const response = await fetch(`/api/session/${sid}/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code: editor.getValue() })
    });

    const data = await response.json();
    if (!response.ok) throw Error(data.error || 'Falha ao executar.');

    log(data.message || 'Código enviado ao robô.');
    await watchMissionSession(sid);
  } catch (error) {
    log(error.message || String(error));
    setStatus('Erro', 'error');
  }

  button.disabled = false;
}

async function watchMissionSession(sid){
  for (let i = 0; i < 120; i++) {
    await new Promise(resolve => setTimeout(resolve, 500));
    try {
      const response = await fetch(`/api/session/${sid}/status?x=${Date.now()}`);
      const data = await response.json();
      if (data.logs) document.getElementById('logs').textContent = data.logs;
      if (data.status === 'done') {
        setStatus('Concluído', 'success');
        markMissionCompleted(currentMissionId);
        return;
      }
      if (data.status === 'error') {
        setStatus('Erro', 'error');
        return;
      }
    } catch (error) {}
  }

  setStatus('Tempo esgotado', 'error');
}

function getUnlockedMissions(){
  try { return JSON.parse(localStorage.getItem('unlockedMissions') || 'null') || []; } catch(e){ return []; }
}

function setUnlockedMissions(list){
  localStorage.setItem('unlockedMissions', JSON.stringify(list));
}

function markMissionCompleted(missionId){
  const completed = JSON.parse(localStorage.getItem('completedMissions') || '[]');
  if (!completed.includes(missionId)) {
    completed.push(missionId);
    localStorage.setItem('completedMissions', JSON.stringify(completed));
  }
  // unlock next mission
  const idx = missionList.findIndex(m => m.id === missionId);
  if (idx >= 0 && idx + 1 < missionList.length) {
    const unlocked = getUnlockedMissions();
    const nextId = missionList[idx+1].id;
    if (!unlocked.includes(nextId)) {
      unlocked.push(nextId);
      setUnlockedMissions(unlocked);
      renderPhaseLocks();
      showNextMissionToast(nextId);
    }
  }
}

function renderPhaseLocks(){
  const unlocked = getUnlockedMissions();
  document.querySelectorAll('.phase-card').forEach((button) => {
    const id = button.dataset.missionId;
    if (!unlocked.includes(id)) {
      button.classList.add('phase-card--locked');
      button.setAttribute('aria-disabled', 'true');
    } else {
      button.classList.remove('phase-card--locked');
      button.removeAttribute('aria-disabled');
    }
  });
}

function showNextMissionToast(nextId){
  const mission = getMissionById(nextId);
  const el = document.createElement('div');
  el.className = 'next-toast';
  el.textContent = `Fase ${mission.number} desbloqueada: ${mission.title}`;
  el.style.position = 'fixed'; el.style.right = '20px'; el.style.bottom = '20px'; el.style.padding = '12px 16px'; el.style.background = '#111827'; el.style.color = '#fff'; el.style.borderRadius = '10px';
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 4000);
}
document.getElementById('run').addEventListener('click', run);

window.addEventListener('pagehide', () => {
  Object.values(sessionByMission).forEach((sid) => {
    try {
      fetch(`/api/session/${sid}`, { method: 'DELETE', keepalive: true });
    } catch (error) {}
  });
});
