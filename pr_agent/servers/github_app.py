import asyncio.locks
import copy
import os
import re
import uuid
from typing import Any, Dict, Tuple

import uvicorn
from fastapi import APIRouter, FastAPI, HTTPException, Request, Response
from starlette.background import BackgroundTasks
from starlette.middleware import Middleware
from starlette_context import context
from starlette_context.middleware import RawContextMiddleware

from pr_agent.config_loader import get_settings, global_settings
from pr_agent.log import LoggingFormat, get_logger, setup_logger
from pr_agent.servers.utils import verify_signature
from pr_agent.servers.github_webhook_handler import handle_request

setup_logger(fmt=LoggingFormat.JSON, level=get_settings().get("CONFIG.LOG_LEVEL", "DEBUG"))
base_path = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
build_number_path = os.path.join(base_path, "build_number.txt")
if os.path.exists(build_number_path):
    with open(build_number_path) as f:
        build_number = f.read().strip()
else:
    build_number = "unknown"
router = APIRouter()


@router.post("/api/v1/github_webhooks")
async def handle_github_webhooks(background_tasks: BackgroundTasks, request: Request, response: Response):
    """
    Receives and processes incoming GitHub webhook requests.
    Verifies the request signature, parses the request body, and passes it to the handle_request function for further
    processing.
    """
    get_logger().debug("Received a GitHub webhook")

    body = await get_body(request)

    installation_id = body.get("installation", {}).get("id")
    context["installation_id"] = installation_id
    context["settings"] = copy.deepcopy(global_settings)
    context["git_provider"] = {}
    background_tasks.add_task(handle_request, body, event=request.headers.get("X-GitHub-Event", None))
    return {}


@router.post("/api/v1/marketplace_webhooks")
async def handle_marketplace_webhooks(request: Request, response: Response):
    body = await get_body(request)
    get_logger().info(f'Request body:\n{body}')


async def get_body(request):
    try:
        body = await request.json()
    except Exception as e:
        get_logger().error("Error parsing request body", artifact={'error': e})
        raise HTTPException(status_code=400, detail="Error parsing request body") from e
    webhook_secret = getattr(get_settings().github, 'webhook_secret', None)
    if webhook_secret:
        body_bytes = await request.body()
        signature_header = request.headers.get('x-hub-signature-256', None)
        verify_signature(body_bytes, webhook_secret, signature_header)
    return body


@router.get("/")
async def root():
    return {"status": "ok"}


if get_settings().github_app.override_deployment_type:
    # Override the deployment type to app
    get_settings().set("GITHUB.DEPLOYMENT_TYPE", "app")
# get_settings().set("CONFIG.PUBLISH_OUTPUT_PROGRESS", False)
middleware = [Middleware(RawContextMiddleware)]
app = FastAPI(middleware=middleware)
app.include_router(router)


def start():
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "3000")))  # nosec B104


if __name__ == '__main__':
    start()
