import hashlib
import hmac
import json
import logging

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_safe

from .deployment import DeploymentBusy, DeploymentError, deploy_release, read_state, valid_sha
from .version import VERSION

logger = logging.getLogger(__name__)


@require_safe
def hello(request):
    state = read_state()
    sha = state.get("sha", "")
    return render(request, "hello_world.html", {
        "version": VERSION,
        "commit": sha[:7] if valid_sha(sha) else "",
        "deployed_at": state.get("deployed_at", ""),
    })


@csrf_exempt
@require_POST
def update_server(request):
    if not settings.DEPLOY_ENABLED:
        return JsonResponse({"status": "disabled"}, status=404)
    if not settings.DEPLOY_WEBHOOK_SECRET or not settings.DEPLOY_REPOSITORY:
        return JsonResponse({"status": "not_configured"}, status=503)

    body = request.body
    signature = request.headers.get("X-Hub-Signature-256", "")
    expected = "sha256=" + hmac.new(
        settings.DEPLOY_WEBHOOK_SECRET.encode("utf-8"), body, hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(signature.encode("utf-8"), expected.encode("ascii")):
        return JsonResponse({"status": "invalid_signature"}, status=403)
    if request.content_type != "application/json":
        return JsonResponse({"status": "invalid_content_type"}, status=415)
    try:
        payload = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"status": "invalid_json"}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({"status": "invalid_payload"}, status=400)

    event = request.headers.get("X-GitHub-Event", "")
    if event == "ping":
        return JsonResponse({"status": "ready"})
    repository = payload.get("repository")
    if not isinstance(repository, dict) or repository.get("full_name") != settings.DEPLOY_REPOSITORY:
        return JsonResponse({"status": "invalid_repository"}, status=403)
    if event != "push" or payload.get("ref") != "refs/heads/" + settings.DEPLOY_BRANCH:
        return JsonResponse({"status": "ignored", "reason": "event_or_branch"})
    sha = payload.get("after")
    if not valid_sha(sha):
        return JsonResponse({"status": "invalid_commit"}, status=400)
    ci = payload.get("ci")
    if not isinstance(ci, dict) or ci.get("conclusion") != "success" or ci.get("sha") != sha:
        return JsonResponse({"status": "ignored", "reason": "ci_not_approved"})
    try:
        result = deploy_release(sha)
    except DeploymentBusy:
        return JsonResponse({"status": "busy"}, status=409)
    except DeploymentError:
        logger.exception("Falha ao atualizar a aplicacao.")
        return JsonResponse({"status": "deployment_failed"}, status=500)
    return JsonResponse(result)
