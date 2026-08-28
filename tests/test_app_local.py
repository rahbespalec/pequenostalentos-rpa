import importlib
import json

import app as app_module
from app import app


def test_starter_uses_current_runtime_port(monkeypatch):
    monkeypatch.setenv('PORT', '5050')
    importlib.reload(app_module)
    try:
        assert 'http://127.0.0.1:5050' in app_module.STARTER
        assert 'http://127.0.0.1:5000' not in app_module.STARTER
    finally:
        monkeypatch.delenv('PORT', raising=False)
        importlib.reload(app_module)


def test_create_session_works_without_docker():
    client = app.test_client()
    response = client.post('/api/session')

    assert response.status_code == 200, response.get_data(as_text=True)
    payload = response.get_json()
    assert 'id' in payload
    assert payload['id']

    status = client.get(f"/api/session/{payload['id']}/status")
    assert status.status_code == 200
    assert status.get_json()['status'] in {'ready', 'idle'}

    delete = client.delete(f"/api/session/{payload['id']}")
    assert delete.status_code == 200


def test_game_exposes_four_form_missions_and_light_theme():
    client = app.test_client()

    missions_response = client.get('/api/missions')
    assert missions_response.status_code == 200
    missions = missions_response.get_json()
    assert isinstance(missions, list)
    assert len(missions) >= 4
    assert [mission['id'] for mission in missions[:4]] == ['mission-01', 'mission-02', 'mission-03', 'mission-04']
    assert all('difficulty' in mission for mission in missions[:4])
    assert [mission['difficulty'] for mission in missions[:4]] == [1, 2, 3, 4]

    challenge_response = client.get('/desafio?mission_id=mission-04')
    assert challenge_response.status_code == 200
    html = challenge_response.get_data(as_text=True).lower()
    assert 'select' in html
    assert 'checkbox' in html or 'radio' in html

    styles_response = client.get('/static/css/style.css')
    assert styles_response.status_code == 200
    css = styles_response.get_data(as_text=True).lower()
    assert 'var(--bg)' in css
    assert '#f7f9fc' in css.lower() or '#f5f7fb' in css.lower()
