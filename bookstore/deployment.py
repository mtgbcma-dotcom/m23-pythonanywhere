import json
import os
import re
import subprocess
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings
from git import GitCommandError, InvalidGitRepositoryError, NoSuchPathError, Repo


class DeploymentError(Exception):
    pass


class DeploymentBusy(DeploymentError):
    pass


def valid_sha(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}", value) is not None


def read_state():
    try:
        state = json.loads(Path(settings.DEPLOY_STATE_PATH).read_text(encoding="utf-8"))
        return state if isinstance(state, dict) else {}
    except (OSError, ValueError):
        return {}


@contextmanager
def deployment_lock():
    import fcntl

    path = Path(settings.DEPLOY_LOCK_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise DeploymentBusy("Ja existe uma atualizacao em andamento.") from error
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def run_command(arguments, *, timeout):
    environment = os.environ.copy()
    environment["GIT_TERMINAL_PROMPT"] = "0"
    try:
        return subprocess.run(
            arguments, cwd=settings.DEPLOY_REPO_PATH, env=environment,
            check=True, capture_output=True, text=True, timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise DeploymentError("Uma etapa da atualizacao falhou. Consulte o log do servidor.") from error


def deploy_release(sha):
    if not valid_sha(sha):
        raise DeploymentError("Commit invalido.")
    python = Path(settings.DEPLOY_PYTHON)
    wsgi = Path(settings.DEPLOY_WSGI_FILE)
    if not python.is_file() or not wsgi.is_file():
        raise DeploymentError("Configure os caminhos do Python e do WSGI antes de publicar.")

    with deployment_lock():
        try:
            repo = Repo(settings.DEPLOY_REPO_PATH)
        except (InvalidGitRepositoryError, NoSuchPathError) as error:
            raise DeploymentError("O projeto precisa ser um clone Git.") from error
        try:
            if repo.head.is_detached or repo.active_branch.name != settings.DEPLOY_BRANCH:
                raise DeploymentError("O clone da hospedagem precisa estar na branch main.")
            if repo.is_dirty(untracked_files=False):
                raise DeploymentError("Existem alteracoes locais no clone da hospedagem.")

            run_command(["git", "fetch", "--no-tags", "origin", settings.DEPLOY_BRANCH], timeout=20)
            if repo.commit("FETCH_HEAD").hexsha != sha:
                return {"status": "ignored", "reason": "newer_commit", "sha": sha}

            if repo.head.commit.hexsha == sha and read_state().get("sha") == sha:
                return {"status": "already_deployed", "sha": sha}

            repo.git.merge("--ff-only", sha)
            run_command([str(python), "-m", "pip", "install", "--disable-pip-version-check",
                         "--no-input", "-r", "requirements.txt"], timeout=90)
            run_command([str(python), "manage.py", "migrate", "--noinput"], timeout=30)
            run_command([str(python), "manage.py", "collectstatic", "--noinput"], timeout=30)

            os.utime(wsgi, None)
            state = {"sha": sha, "deployed_at": datetime.now(timezone.utc).isoformat()}
            state_path = Path(settings.DEPLOY_STATE_PATH)
            state_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = state_path.with_suffix(".tmp")
            temporary.write_text(json.dumps(state), encoding="utf-8")
            temporary.replace(state_path)
            return {"status": "deployed", **state}
        except GitCommandError as error:
            raise DeploymentError("Nao foi possivel atualizar o clone por fast-forward.") from error
        finally:
            repo.close()
