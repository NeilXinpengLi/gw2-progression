from fastapi import APIRouter, Body, HTTPException, Query, Request

from gw2_progression.services.credential_service import (
    delete_credential,
    get_credential,
    get_usage_stats,
    list_credentials,
    record_usage,
    save_credential,
    update_credential_status,
)
from gw2_progression.services.provider_service import get_scope_explanations, list_providers

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
async def post_credential(request: Request, body: dict = Body(...)):
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


@router.get("/{credential_id}")
async def get_credential_endpoint(credential_id: int):
    cred = await get_credential(credential_id)
    if not cred:
        raise HTTPException(status_code=404, detail="Credential not found")
    return {
        "id": cred["id"],
        "provider": cred["provider"],
        "label": cred["label"],
        "fingerprint": cred["fingerprint"],
        "status": cred.get("status", "unknown"),
        "scopes": cred.get("scopes", ""),
        "session_token": cred.get("session_token"),
    }


@router.post("/{credential_id}/validate")
async def post_validate_credential(credential_id: int):
    from gw2_progression.services.crypto import decrypt_value

    cred = await get_credential(credential_id)
    if not cred:
        raise HTTPException(status_code=404, detail="Credential not found")

    key = decrypt_value(cred["encrypted_value"])
    scopes = ""
    status = "valid"

    if cred["provider"] == "gw2":
        import httpx

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://api.guildwars2.com/v2/tokeninfo",
                    headers={"Authorization": f"Bearer {key}"},
                )
                if resp.status_code == 200:
                    info = resp.json()
                    scopes = ",".join(info.get("permissions", []))
                else:
                    status = "invalid"
        except Exception:
            status = "invalid"
    else:
        status = "unknown"

    await update_credential_status(credential_id, status, scopes)
    return {"status": status, "scopes": scopes}


@router.delete("/{credential_id}")
async def delete_credential_endpoint(credential_id: int):
    deleted = await delete_credential(credential_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Credential not found")
    return {"status": "deleted"}


@router.get("/{credential_id}/usage")
async def get_usage(credential_id: int):
    return await get_usage_stats(credential_id)


@router.post("/{credential_id}/usage")
async def post_usage(credential_id: int, body: dict = Body(...)):
    feature = body.get("feature", "unknown")
    provider = body.get("provider", "")
    cost = body.get("cost_copper", 0)
    await record_usage(credential_id, feature, provider, cost)
    return {"status": "recorded"}


@router.get("/providers")
async def list_all_providers(category: str | None = Query(None)):
    providers = await list_providers(category)
    explanations = await get_scope_explanations()
    return {"providers": providers, "scope_explanations": explanations}
