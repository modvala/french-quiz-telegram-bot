from fastapi.testclient import TestClient
from backend.app import app

client = TestClient(app)

print('POST /quiz/start')
r = client.post('/quiz/start', json={'user_id': 'inspector', 'n_questions': 3})
print(r.status_code)
print(r.json())

if r.status_code == 200:
    sid = r.json()['session_id']
    print('\nGET /quiz/question/{sid}/0')
    q = client.get(f'/quiz/question/{sid}/0')
    print(q.status_code)
    print(q.json())
else:
    print('Start failed')
