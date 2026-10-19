import argparse
import getpass
import json
import os
import re
import secrets
import sys
from pathlib import Path
from urllib.parse import urlsplit

from git import Repo


def configure(project, username, python, domain=None):
    project = Path(project).resolve()
    environment_file = project / ".env"
    if environment_file.exists():
        raise ValueError("O arquivo .env ja existe. Ele foi preservado; revise-o antes de continuar.")
    domain = domain or username + ".pythonanywhere.com"
    if not re.fullmatch(r"[a-zA-Z0-9.-]+\.pythonanywhere\.com", domain):
        raise ValueError("Dominio PythonAnywhere invalido.")
    with Repo(project) as repo:
        remote = urlsplit(repo.remotes.origin.url)
        if remote.scheme != "https" or remote.hostname != "github.com":
            raise ValueError("Use um clone publico HTTPS do GitHub.")
        repository = remote.path.strip("/").removesuffix(".git")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
            raise ValueError("Repositorio do GitHub invalido.")
        if repo.head.is_detached or repo.active_branch.name != "main":
            raise ValueError("O clone da hospedagem precisa estar na branch main.")

    (project / "data").mkdir(exist_ok=True)
    deployment_dir = project / ".deploy"
    deployment_dir.mkdir(exist_ok=True)
    wsgi_target = "/var/www/" + domain.replace(".", "_") + "_wsgi.py"
    values = {
        "DJANGO_DEBUG": "0", "DJANGO_SECRET_KEY": secrets.token_hex(48),
        "DJANGO_ALLOWED_HOSTS": domain,
        "DJANGO_CSRF_TRUSTED_ORIGINS": "https://" + domain,
        "DJANGO_SECURE_SSL_REDIRECT": "1", "DATABASE_ENGINE": "sqlite",
        "SQLITE_DB_PATH": str(project / "data" / "db.sqlite3"),
        "DEPLOY_ENABLED": "1", "DEPLOY_WEBHOOK_SECRET": secrets.token_hex(32),
        "DEPLOY_REPOSITORY": repository, "DEPLOY_PYTHON": str(Path(python).absolute()),
        "DEPLOY_WSGI_FILE": wsgi_target,
    }
    descriptor = os.open(environment_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        output.write("# Configuracao privada da hospedagem; nao incluir no Git.\n")
        output.writelines(f"{key}={json.dumps(value)}\n" for key, value in values.items())

    wsgi_example = deployment_dir / "pythonanywhere_wsgi.py"
    wsgi_example.write_text(
        "import os\nimport sys\n\n"
        f"project_dir = {str(project)!r}\n"
        "if project_dir not in sys.path:\n    sys.path.insert(0, project_dir)\n\n"
        "os.environ['DJANGO_SETTINGS_MODULE'] = 'bookstore.settings'\n"
        "from django.core.wsgi import get_wsgi_application\n"
        "application = get_wsgi_application()\n", encoding="utf-8",
    )
    return {"environment_file": str(environment_file), "domain": domain,
            "wsgi_example": str(wsgi_example), "wsgi_target": wsgi_target,
            "webhook_url": "https://" + domain + "/update_server/"}


def main():
    parser = argparse.ArgumentParser(description="Prepara a configuracao privada do PythonAnywhere.")
    parser.add_argument("--domain", help="Dominio exibido na aba Web, se diferente do padrao.")
    options = parser.parse_args()
    if sys.prefix == sys.base_prefix:
        parser.error("Ative o ambiente virtual da hospedagem antes de executar este comando.")
    try:
        result = configure(Path(__file__).resolve().parent.parent, getpass.getuser(),
                           sys.executable, options.domain)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    for key, value in result.items():
        print(f"{key}: {value}")
    print("Chaves privadas geradas no .env. Nenhuma chave foi exibida.")


if __name__ == "__main__":
    main()
