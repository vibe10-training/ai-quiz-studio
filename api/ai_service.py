import json
import re
from typing import Any, Dict, List
import httpx

from .config import AISettings, get_ai_settings
from .models import QuizGenerateRequest, QuizGenerateResponse, QuizQuestion


class AIServiceError(Exception):
    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _build_prompts(req: QuizGenerateRequest) -> tuple[str, str]:
    difficulty_kr = {"easy": "쉬움", "medium": "보통", "hard": "어려움"}[req.difficulty]
    type_kr = "객관식(4지선다)" if req.question_type == "multiple_choice" else "주관식(단답형/서술형 핵심 답안)"

    system_prompt = (
        "당신은 한국 초·중·고 및 성인 교육 과정을 잘 이해하는 전문 퀴즈 출제 교사입니다. "
        "반드시 요청된 JSON 스키마만 출력하고, 마크다운 코드블록(```)이나 추가 설명 문장은 출력하지 마세요. "
        "모든 문제에는 학습자가 오답을 고쳐 이해할 수 있도록 구체적이고 친절한 'explanation'(해설)을 반드시 포함해야 합니다."
    )

    if req.question_type == "multiple_choice":
        format_rule = (
            '각 문항 객체는 {"id": 1, "type": "multiple_choice", "question": "문제 내용", '
            '"options": ["보기1", "보기2", "보기3", "보기4"], '
            '"answer": "정답 보기 텍스트(options 중 하나와 정확히 일치)", '
            '"explanation": "정답인 이유와 오답 선지에 대한 상세 해설"} 형식이어야 합니다.'
        )
    else:
        format_rule = (
            '각 문항 객체는 {"id": 1, "type": "short_answer", "question": "문제 내용", '
            '"options": null, '
            '"answer": "간결하고 명확한 모범 답안", '
            '"explanation": "모범 답안의 근거와 핵심 개념 해설"} 형식이어야 합니다.'
        )

    user_prompt = (
        f"다음 조건에 맞춰 {req.count}개의 문제를 출제해 주세요.\n"
        f"- 과목: {req.subject}\n"
        f"- 단원: {req.unit}\n"
        f"- 문제 유형: {type_kr}\n"
        f"- 난이도: {difficulty_kr}\n\n"
        f"출력 JSON 루트 형식:\n"
        f'{{"questions": [ ... ]}}\n\n'
        f"문항 규칙:\n{format_rule}\n"
        f"총 {req.count}문항을 중복 없이 출제하세요."
    )
    return system_prompt, user_prompt


def _extract_json_payload(raw_text: str) -> Dict[str, Any]:
    text = raw_text.strip()
    # Strip markdown code fences if model returns them despite instructions
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if fence_match:
        text = fence_match.group(1).strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        # Fallback: extract outermost JSON object
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise AIServiceError("AI 응답을 JSON으로 해석하지 못했습니다.", status_code=502)
        try:
            parsed = json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise AIServiceError(f"AI 응답 JSON 파싱 오류: {exc}", status_code=502)

    if isinstance(parsed, list):
        parsed = {"questions": parsed}
    if not isinstance(parsed, dict) or not isinstance(parsed.get("questions"), list):
        raise AIServiceError("AI 응답에 'questions' 목록이 포함되어 있지 않습니다.", status_code=502)
    return parsed


def _normalize_questions(raw_questions: List[Dict[str, Any]], req: QuizGenerateRequest) -> List[QuizQuestion]:
    normalized: List[QuizQuestion] = []
    for idx, item in enumerate(raw_questions, start=1):
        if not isinstance(item, dict):
            continue
        q_text = str(item.get("question", "")).strip()
        answer = str(item.get("answer", "")).strip()
        explanation = str(item.get("explanation", "")).strip() or "정답과 핵심 개념을 다시 확인해 보세요."
        if not q_text or not answer:
            continue

        options = None
        if req.question_type == "multiple_choice":
            raw_opts = item.get("options")
            if isinstance(raw_opts, list):
                options = [str(opt).strip() for opt in raw_opts if str(opt).strip()]
            if not options or len(options) < 2:
                continue
            # Ensure answer matches one of the options if AI returned index like "1" or "A"
            if answer not in options:
                if answer.isdigit():
                    opt_idx = int(answer) - 1
                    if 0 <= opt_idx < len(options):
                        answer = options[opt_idx]
                elif len(answer) == 1 and answer.upper() in "ABCD":
                    opt_idx = ord(answer.upper()) - ord("A")
                    if 0 <= opt_idx < len(options):
                        answer = options[opt_idx]

        normalized.append(
            QuizQuestion(
                id=len(normalized) + 1,
                type=req.question_type,
                question=q_text,
                options=options,
                answer=answer,
                explanation=explanation,
            )
        )

    if not normalized:
        raise AIServiceError("유효한 퀴즈 문항이 생성되지 않았습니다. 다시 시도해 주세요.", status_code=502)
    return normalized


async def _call_llm(settings: AISettings, system_prompt: str, user_prompt: str) -> str:
    endpoint = settings.endpoint.rstrip("/")
    lower_ep = endpoint.lower()

    headers: Dict[str, str] = {"Content-Type": "application/json"}
    params: Dict[str, str] = {}

    if "generativelanguage.googleapis.com" in lower_ep:
        # Google Gemini REST API
        url = endpoint if ":generateContent" in endpoint else f"{endpoint}/models/{settings.model}:generateContent"
        headers["x-goog-api-key"] = settings.api_key
        payload: Dict[str, Any] = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": {"temperature": 0.7, "responseMimeType": "application/json"},
        }
        provider = "gemini"
    elif "openai.azure.com" in lower_ep or "/openai/deployments" in lower_ep:
        # Azure OpenAI
        if "/chat/completions" in lower_ep:
            url = endpoint
        else:
            url = f"{endpoint}/openai/deployments/{settings.model}/chat/completions"
        if "api-version=" not in lower_ep:
            params["api-version"] = settings.api_version
        headers["api-key"] = settings.api_key
        payload = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
        }
        provider = "openai"
    else:
        # OpenAI & OpenAI-compatible endpoints (OpenRouter, Groq, Together, etc.)
        url = endpoint if endpoint.endswith("/chat/completions") else f"{endpoint}/chat/completions"
        headers["Authorization"] = f"Bearer {settings.api_key}"
        payload = {
            "model": settings.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        provider = "openai"

    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(url, headers=headers, params=params or None, json=payload)
    except httpx.TimeoutException:
        raise AIServiceError("AI 서버 응답 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요.", status_code=504)
    except httpx.RequestError as exc:
        raise AIServiceError(f"AI 서버 연결 중 오류가 발생했습니다: {exc}", status_code=502)

    if resp.status_code >= 400:
        detail = resp.text[:300]
        raise AIServiceError(
            f"AI API 호출 실패 (HTTP {resp.status_code}): {detail}",
            status_code=502 if resp.status_code >= 500 else 400,
        )

    data = resp.json()
    try:
        if provider == "gemini":
            return data["candidates"][0]["content"]["parts"][0]["text"]
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise AIServiceError("AI 응답 구조가 예상과 다릅니다.", status_code=502)


async def generate_quiz(req: QuizGenerateRequest) -> QuizGenerateResponse:
    settings = get_ai_settings()
    if not settings.is_configured:
        raise AIServiceError(
            "AI API 설정이 누락되었습니다. 프로젝트 루트의 env_local(또는 .env.local) 파일에 "
            "ENDPOINT와 KEY를 설정하거나 Vercel 환경 변수를 등록해 주세요.",
            status_code=500,
        )

    system_prompt, user_prompt = _build_prompts(req)
    raw_content = await _call_llm(settings, system_prompt, user_prompt)
    parsed = _extract_json_payload(raw_content)
    questions = _normalize_questions(parsed["questions"], req)

    return QuizGenerateResponse(
        subject=req.subject,
        unit=req.unit,
        question_type=req.question_type,
        difficulty=req.difficulty,
        questions=questions,
    )
