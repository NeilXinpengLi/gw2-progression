from fastapi import APIRouter, Body, HTTPException, Request

from gw2_progression.services.credential_service import (
    delete_credential,
    get_key_by_provider,
    list_credentials,
    save_credential,
)

router = APIRouter(prefix="/credentials", tags=["credentials"])


def _get_session(request: Request) -> str | None:
    token = request.cookies.get("session_token")
    if token:
        return token
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return None


@router.post("")
async def post_credential(
    request: Request,
    body: dict = Body(...),
):
    provider = body.get("provider", "")
    api_key = body.get("api_key", "")
    label = body.get("label", "")
    if not provider or not api_key:
        raise HTTPException(status_code=422, detail="provider and api_key are required")
    session = _get_session(request)
    result = await save_credential(provider, api_key, label, session)
    return result


@router.get("")
async def get_credentials(request: Request):
    session = _get_session(request)
    return await list_credentials(session)


@router.delete("/{credential_id}")
async def delete_credential_endpoint(credential_id: int):
    deleted = await delete_credential(credential_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Credential not found")
    return {"status": "deleted"}


@router.get("/providers")
async def list_providers():
    return [
        {"id": "openai", "name": "OpenAI", "models": ["gpt-4o-mini", "gpt-4o"]},
        {"id": "anthropic", "name": "Anthropic", "models": ["claude-3-5-haiku", "claude-3-5-sonnet"]},
        {"id": "deepseek", "name": "DeepSeek", "models": ["deepseek-chat"]},
        {"id": "gemini", "name": "Google Gemini", "models": ["gemini-2.0-flash"]},
        {"id": "ollama", "name": "Ollama (Local)", "models": ["llama3", "qwen2"]},
    ]
