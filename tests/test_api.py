import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from api.config import parse_env_file
from api.index import app


client = TestClient(app)


def test_health_endpoint():
    res = client.get("/api/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert "ai_configured" in body


def test_root_serves_html():
    res = client.get("/")
    assert res.status_code == 200
    assert "AI 퀴즈 스튜디오" in res.text


def test_parse_env_local_file(tmp_path: Path):
    env_file = tmp_path / "env_local"
    env_file.write_text(
        '# comment\nENDPOINT="https://example.openai.azure.com"\nKEY=\'secret-123\'\nMODEL=gpt-4o-mini\n',
        encoding="utf-8",
    )
    parsed = parse_env_file(env_file)
    assert parsed["ENDPOINT"] == "https://example.openai.azure.com"
    assert parsed["KEY"] == "secret-123"
    assert parsed["MODEL"] == "gpt-4o-mini"


def test_generate_quiz_validation_error():
    res = client.post(
        "/api/quiz/generate",
        json={"subject": "   ", "unit": "이차방정식", "question_type": "multiple_choice", "count": 5},
    )
    assert res.status_code == 422


def test_generate_multiple_choice_with_explanation():
    mock_llm_output = json.dumps(
        {
            "questions": [
                {
                    "id": 1,
                    "type": "multiple_choice",
                    "question": "이차방정식 x^2 - 5x + 6 = 0의 해는?",
                    "options": ["x = 1, 6", "x = 2, 3", "x = -2, -3", "x = 1, 5"],
                    "answer": "x = 2, 3",
                    "explanation": "(x - 2)(x - 3) = 0으로 인수분해되므로 해는 2와 3입니다.",
                }
            ]
        },
        ensure_ascii=False,
    )

    with patch("api.ai_service.get_ai_settings") as mock_settings, patch(
        "api.ai_service._call_llm", new=AsyncMock(return_value=mock_llm_output)
    ):
        mock_settings.return_value.is_configured = True
        res = client.post(
            "/api/quiz/generate",
            json={
                "subject": "수학",
                "unit": "이차방정식",
                "question_type": "multiple_choice",
                "count": 1,
                "difficulty": "medium",
            },
        )

    assert res.status_code == 200
    data = res.json()
    assert data["subject"] == "수학"
    assert data["unit"] == "이차방정식"
    assert len(data["questions"]) == 1
    assert data["questions"][0]["answer"] == "x = 2, 3"
    assert "인수분해" in data["questions"][0]["explanation"]


def test_generate_short_answer_with_code_fence_and_explanation():
    mock_llm_output = (
        "```json\n"
        '{"questions": [{"id": 1, "type": "short_answer", '
        '"question": "식물이 빛 에너지를 이용해 양분을 합성하는 작용은?", '
        '"options": null, "answer": "광합성", '
        '"explanation": "엽록체에서 빛 에너지를 이용해 포도당과 산소를 생성합니다."}]}\n'
        "```"
    )

    with patch("api.ai_service.get_ai_settings") as mock_settings, patch(
        "api.ai_service._call_llm", new=AsyncMock(return_value=mock_llm_output)
    ):
        mock_settings.return_value.is_configured = True
        res = client.post(
            "/api/quiz/generate",
            json={
                "subject": "과학",
                "unit": "광합성",
                "question_type": "short_answer",
                "count": 1,
                "difficulty": "easy",
            },
        )

    assert res.status_code == 200
    data = res.json()
    assert data["questions"][0]["type"] == "short_answer"
    assert data["questions"][0]["answer"] == "광합성"
    assert "엽록체" in data["questions"][0]["explanation"]
