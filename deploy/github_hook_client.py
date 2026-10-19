import hashlib
import hmac
import json
import os
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


def send_deployment(url, secret, repository, sha):
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or not parsed.hostname
            or not parsed.hostname.endswith(".pythonanywhere.com")
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path != "/update_server/"):
        raise ValueError("Use a URL HTTPS /update_server/ da sua aplicacao PythonAnywhere.")
    if not secret:
        raise ValueError("Configure o secret DEPLOY_WEBHOOK_SECRET no GitHub.")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("Repositorio invalido.")
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ValueError("Commit invalido.")

    payload = {
        "ref": "refs/heads/main", "after": sha,
        "repository": {"full_name": repository},
        "ci": {"conclusion": "success", "sha": sha},
    }
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signature = "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    request = Request(url, data=body, method="POST", headers={
        "Content-Type": "application/json", "Accept": "application/json",
        "X-GitHub-Event": "push", "X-Hub-Signature-256": signature,
    })
    try:
        with urlopen(request, timeout=210) as response:
            result = json.load(response)
    except HTTPError as error:
        raise RuntimeError(f"Webhook retornou HTTP {error.code}. Consulte o log do servidor.") from error
    except URLError as error:
        raise RuntimeError("Nao foi possivel conectar ao webhook do PythonAnywhere.") from error
    if not isinstance(result, dict) or result.get("status") not in {"deployed", "already_deployed", "ignored"}:
        raise RuntimeError("Resposta inesperada do webhook.")
    if result.get("sha") != sha:
        raise RuntimeError("O commit informado na resposta e diferente do solicitado.")
    return result


def main():
    try:
        result = send_deployment(
            os.environ.get("PYTHONANYWHERE_WEBHOOK_URL", ""),
            os.environ.get("DEPLOY_WEBHOOK_SECRET", ""),
            os.environ.get("GITHUB_REPOSITORY", ""),
            os.environ.get("GITHUB_SHA", ""),
        )
    except (ValueError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(f"Deploy: {result['status']} - commit {result['sha'][:7]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
