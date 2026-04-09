import logging
from typing import Any
from urllib.parse import urljoin

import aiohttp
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse

from open_webui.env import AIOHTTP_CLIENT_TIMEOUT
from open_webui.utils.auth import get_verified_user

router = APIRouter()

log = logging.getLogger(__name__)


def _get_documents_base_url(request: Request) -> str:
    base_url = (request.app.state.config.EXTERNAL_DOCUMENT_LOADER_URL or '').strip()
    if not base_url:
        raise HTTPException(status_code=400, detail='External document loader URL is not configured')
    return base_url.rstrip('/') + '/'


def _get_documents_headers(request: Request) -> dict[str, str]:
    headers: dict[str, str] = {'Accept': 'application/json'}
    api_key = (request.app.state.config.EXTERNAL_DOCUMENT_LOADER_API_KEY or '').strip()
    if api_key:
        headers['Authorization'] = f'Bearer {api_key}'
    return headers


async def _proxy_json_response(response: aiohttp.ClientResponse) -> JSONResponse:
    try:
        payload: Any = await response.json()
    except Exception:
        payload = {'detail': await response.text()}

    return JSONResponse(status_code=response.status, content=payload)


@router.post('')
async def create_document(
    request: Request,
    file: UploadFile = File(...),
    user=Depends(get_verified_user),
):
    base_url = _get_documents_base_url(request)
    target_url = urljoin(base_url, 'documents')
    headers = _get_documents_headers(request)

    form = aiohttp.FormData()
    form.add_field(
        'file',
        await file.read(),
        filename=file.filename or 'document',
        content_type=file.content_type or 'application/octet-stream',
    )

    timeout = aiohttp.ClientTimeout(total=AIOHTTP_CLIENT_TIMEOUT)
    async with aiohttp.ClientSession(timeout=timeout, trust_env=True) as session:
        try:
            async with session.post(target_url, data=form, headers=headers) as response:
                return await _proxy_json_response(response)
        except Exception as e:
            log.exception('Failed to proxy single document upload')
            raise HTTPException(status_code=502, detail=f'Failed to upload document: {e}')


@router.post('/batch')
async def create_documents_batch(
    request: Request,
    files: list[UploadFile] = File(...),
    user=Depends(get_verified_user),
):
    base_url = _get_documents_base_url(request)
    target_url = urljoin(base_url, 'documents/batch')
    headers = _get_documents_headers(request)

    form = aiohttp.FormData()
    for file in files:
        form.add_field(
            'files',
            await file.read(),
            filename=file.filename or 'document',
            content_type=file.content_type or 'application/octet-stream',
        )

    timeout = aiohttp.ClientTimeout(total=AIOHTTP_CLIENT_TIMEOUT)
    async with aiohttp.ClientSession(timeout=timeout, trust_env=True) as session:
        try:
            async with session.post(target_url, data=form, headers=headers) as response:
                return await _proxy_json_response(response)
        except Exception as e:
            log.exception('Failed to proxy batch document upload')
            raise HTTPException(status_code=502, detail=f'Failed to upload documents: {e}')


@router.get('/{document_id}')
async def get_document(
    request: Request,
    document_id: str,
    user=Depends(get_verified_user),
):
    base_url = _get_documents_base_url(request)
    target_url = urljoin(base_url, f'documents/{document_id}')
    headers = _get_documents_headers(request)

    timeout = aiohttp.ClientTimeout(total=AIOHTTP_CLIENT_TIMEOUT)
    async with aiohttp.ClientSession(timeout=timeout, trust_env=True) as session:
        try:
            async with session.get(target_url, headers=headers) as response:
                return await _proxy_json_response(response)
        except Exception as e:
            log.exception('Failed to proxy document status request')
            raise HTTPException(status_code=502, detail=f'Failed to get document status: {e}')
