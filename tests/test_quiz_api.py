from fastapi.testclient import TestClient
from backend import app as backend_app


client = TestClient(backend_app.app)


def _find_correct_option_number(options, question_id: int) -> int:
    target_fragment = f"q{question_id}_answer"
    for opt in options:
        audio_url = opt.get("audio_url") or ""
        if target_fragment in audio_url:
            return opt["number"]
    # fallback: return first option number if matching audio was not provided
    return options[0]["number"]


def test_start_and_get_question():
    # start quiz with 2 questions
    resp = client.post("/quiz/start", json={"user_id": "test_user", "n_questions": 2})
    assert resp.status_code == 200
    data = resp.json()
    assert "session_id" in data
    session_id = data["session_id"]
    assert data["total"] == 2

    # get first question
    q_resp = client.get(f"/quiz/question/{session_id}/0")
    assert q_resp.status_code == 200
    qdata = q_resp.json()
    assert qdata["index"] == 0
    assert "prompt_text" in qdata
    assert isinstance(qdata["options"], list)


def test_answer_flow_correct_and_summary():
    # Start quiz with one question (id will be chosen from QUESTIONS)
    resp = client.post("/quiz/start", json={"user_id": "user2", "n_questions": 1})
    assert resp.status_code == 200
    data = resp.json()
    session_id = data["session_id"]

    # fetch question 0
    q_resp = client.get(f"/quiz/question/{session_id}/0")
    assert q_resp.status_code == 200
    qdata = q_resp.json()
    qid = qdata["question_id"]

    correct_id = _find_correct_option_number(qdata["options"], qid)

    # submit correct answer
    a_resp = client.post("/quiz/answer", json={
        "session_id": session_id,
        "question_id": qid,
        "selected_option_id": correct_id,
    })
    assert a_resp.status_code == 200
    a_data = a_resp.json()
    assert a_data["correct"] is True
    # if option had audio, correct_option_audio_url should be present
    target_fragment = f"q{qid}_answer"
    if any(target_fragment in (opt.get("audio_url") or "") for opt in qdata["options"]):
        assert a_data["correct_option_audio_url"] is not None

    # after finishing, summary should report correct_count == 1
    s_resp = client.get(f"/quiz/summary/{session_id}")
    assert s_resp.status_code == 200
    s_data = s_resp.json()
    assert s_data["correct_count"] == 1


def test_answer_order_mismatch_and_incorrect():
    # Start quiz with one question
    resp = client.post("/quiz/start", json={"user_id": "user3", "n_questions": 1})
    assert resp.status_code == 200
    session_id = resp.json()["session_id"]

    # Try to submit answer with wrong question_id
    wrong_qid = 999999
    bad = client.post("/quiz/answer", json={
        "session_id": session_id,
        "question_id": wrong_qid,
        "selected_option_id": 1,
    })
    assert bad.status_code == 400 or bad.status_code == 404

    # Now fetch the real question and submit incorrect option
    q_resp = client.get(f"/quiz/question/{session_id}/0")
    qdata = q_resp.json()
    qid = qdata["question_id"]
    correct_number = _find_correct_option_number(qdata["options"], qid)
    # pick an option id that is not correct
    incorrect_id = next((opt["number"] for opt in qdata["options"] if opt["number"] != correct_number), correct_number)

    a_resp = client.post("/quiz/answer", json={
        "session_id": session_id,
        "question_id": qid,
        "selected_option_id": incorrect_id,
    })
    assert a_resp.status_code == 200
    a_data = a_resp.json()
    assert a_data["correct"] is False
