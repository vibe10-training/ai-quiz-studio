import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_CANDIDATE_FILES = ("env_local", "env_local.txt", ".env.local", ".env")


def parse_env_file(file_path: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    if not file_path.is_file():
        return values

    for raw_line in file_path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].strip()
        if "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip()
        if len(val) >= 2 and ((val[0] == '"' and val[-1] == '"') or (val[0] == "'" and val[-1] == "'")):
            val = val[1:-1]
        if key:
            values[key] = val
    return values


def load_merged_env() -> Dict[str, str]:
    merged: Dict[str, str] = {}
    for filename in ENV_CANDIDATE_FILES:
        merged.update(parse_env_file(PROJECT_ROOT / filename))
    # OS/Vercel environment variables take precedence over local files
    for key, val in os.environ.items():
        if val is not None and val != "":
            merged[key] = val
    return merged


@dataclass
class AISettings:
    endpoint: str
    api_key: str
    model: str
    api_version: str
    source_file_found: bool

    @property
    def is_configured(self) -> bool:
        return bool(self.endpoint and self.api_key)


def get_ai_settings() -> AISettings:
    env = load_merged_env()
    source_file_found = any((PROJECT_ROOT / name).is_file() for name in ENV_CANDIDATE_FILES)

    endpoint = (
        env.get("AI_ENDPOINT")
        or env.get("AZURE_OPENAI_ENDPOINT")
        or env.get("API_ENDPOINT")
        or env.get("ENDPOINT")
        or env.get("OPENAI_BASE_URL")
        or env.get("OPENAI_API_BASE")
        or env.get("LLM_ENDPOINT")
        or ""
    ).strip()

    api_key = (
        env.get("AI_API_KEY")
        or env.get("AZURE_OPENAI_API_KEY")
        or env.get("OPENAI_API_KEY")
        or env.get("API_KEY")
        or env.get("KEY")
        or env.get("GEMINI_API_KEY")
        or env.get("LLM_API_KEY")
        or ""
    ).strip()

    if not endpoint and env.get("OPENAI_API_KEY"):
        endpoint = "https://api.openai.com/v1"

    model = (
        env.get("AI_DEPLOYMENT")
        or env.get("AZURE_OPENAI_DEPLOYMENT")
        or env.get("DEPLOYMENT_NAME")
        or env.get("OPENAI_MODEL")
        or env.get("MODEL")
        or "gpt-4o-mini"
    ).strip()

    api_version = (
        env.get("AZURE_OPENAI_API_VERSION")
        or env.get("API_VERSION")
        or "2024-10-21"
    ).strip()

    return AISettings(
        endpoint=endpoint,
        api_key=api_key,
        model=model,
        api_version=api_version,
        source_file_found=source_file_found,
    )
