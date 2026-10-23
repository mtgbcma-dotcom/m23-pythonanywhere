import ast
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import skipUnless
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings
from dotenv import dotenv_values
from git import Repo

from bookstore import deployment
from deploy.configure_pythonanywhere import configure


def identity(repo):
    with repo.config_writer() as config:
        config.set_value("user", "name", "Local Deployment Test")
        config.set_value("user", "email", "local-test@example.invalid")


@skipUnless(os.name == "posix", "O bloqueio do deploy utiliza o sistema Linux da hospedagem.")
class DeploymentRepositoryTests(SimpleTestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        remote = Repo.init(self.root / "remote.git", bare=True)
        self.addCleanup(remote.close)
        self.author = Repo.init(self.root / "author", initial_branch="main")
        self.addCleanup(self.author.close)
        identity(self.author)
        (self.root / "author/version.txt").write_text("first", encoding="utf-8")
        (self.root / "author/requirements.txt").write_text("# local test\n", encoding="utf-8")
        self.author.index.add(["version.txt", "requirements.txt"])
        self.author.index.commit("Initial version")
        self.author.create_remote("origin", str(self.root / "remote.git"))
        self.author.remotes.origin.push("main:main")
        self.clone_path = self.root / "deployment"
        self.clone = Repo.clone_from(str(self.root / "remote.git"), self.clone_path, branch="main")
        self.addCleanup(self.clone.close)
        identity(self.clone)
        self.initial = self.clone.head.commit.hexsha
        self.wsgi = self.root / "site_wsgi.py"
        self.wsgi.write_text("# WSGI test\n", encoding="utf-8")
        os.utime(self.wsgi, (1000, 1000))
        self.state = self.root / "state.json"
        settings = override_settings(
            DEPLOY_REPO_PATH=self.clone_path, DEPLOY_BRANCH="main", DEPLOY_PYTHON=sys.executable,
            DEPLOY_WSGI_FILE=str(self.wsgi), DEPLOY_STATE_PATH=self.state,
            DEPLOY_LOCK_PATH=self.root / "deploy.lock",
        )
        settings.enable()
        self.addCleanup(settings.disable)
        self.original_command = deployment.run_command
        self.application_commands = []
        self.command_patch = patch("bookstore.deployment.run_command", side_effect=self.command)
        self.command_patch.start()
        self.addCleanup(self.command_patch.stop)

    def command(self, arguments, *, timeout):
        if arguments[0] == "git":
            return self.original_command(arguments, timeout=timeout)
        self.application_commands.append(arguments)
        return subprocess.CompletedProcess(arguments, 0, "", "")

    def publish(self, text="second"):
        (self.root / "author/version.txt").write_text(text, encoding="utf-8")
        self.author.index.add(["version.txt"])
        commit = self.author.index.commit("Updated version")
        self.author.remotes.origin.push("main:main")
        return commit.hexsha

    def test_verified_commit_is_fetched_fast_forwarded_and_reloaded(self):
        sha = self.publish()
        result = deployment.deploy_release(sha)
        self.assertEqual(result["status"], "deployed")
        self.assertEqual(self.clone.head.commit.hexsha, sha)
        self.assertEqual((self.clone_path / "version.txt").read_text(), "second")
        self.assertEqual(json.loads(self.state.read_text())["sha"], sha)
        self.assertNotEqual(self.wsgi.stat().st_mtime, 1000)
        self.assertEqual(len(self.application_commands), 3)

    def test_repeated_delivery_does_not_repeat_installation_or_migrations(self):
        sha = self.publish()
        deployment.deploy_release(sha)
        result = deployment.deploy_release(sha)
        self.assertEqual(result["status"], "already_deployed")
        self.assertEqual(len(self.application_commands), 3)

    def test_old_ci_commit_does_not_deploy_a_newer_untested_commit(self):
        approved = self.publish("approved")
        self.publish("newer-not-approved")
        result = deployment.deploy_release(approved)
        self.assertEqual(result["reason"], "newer_commit")
        self.assertEqual(self.clone.head.commit.hexsha, self.initial)
        self.assertEqual(self.application_commands, [])
        self.assertFalse(self.state.exists())

    def test_local_changes_are_preserved_and_deployment_is_refused(self):
        sha = self.publish()
        (self.clone_path / "version.txt").write_text("local edit", encoding="utf-8")
        with self.assertRaises(deployment.DeploymentError):
            deployment.deploy_release(sha)
        self.assertEqual((self.clone_path / "version.txt").read_text(), "local edit")
        self.assertEqual(self.application_commands, [])

    def test_diverged_history_is_not_overwritten(self):
        sha = self.publish()
        (self.clone_path / "version.txt").write_text("local commit", encoding="utf-8")
        self.clone.index.add(["version.txt"])
        local_commit = self.clone.index.commit("Local change").hexsha
        with self.assertRaises(deployment.DeploymentError):
            deployment.deploy_release(sha)
        self.assertEqual(self.clone.head.commit.hexsha, local_commit)
        self.assertFalse(self.state.exists())

    def test_wrong_branch_is_not_changed(self):
        sha = self.publish()
        self.clone.git.checkout("-b", "feature")
        with self.assertRaises(deployment.DeploymentError):
            deployment.deploy_release(sha)
        self.assertEqual(self.clone.active_branch.name, "feature")

    def test_missing_wsgi_does_not_update_the_code(self):
        sha = self.publish()
        with override_settings(DEPLOY_WSGI_FILE=str(self.root / "missing.py")):
            with self.assertRaises(deployment.DeploymentError):
                deployment.deploy_release(sha)
        self.assertEqual(self.clone.head.commit.hexsha, self.initial)

    def test_invalid_commit_is_refused(self):
        with self.assertRaises(deployment.DeploymentError):
            deployment.deploy_release("not-a-commit")
        self.assertEqual(self.application_commands, [])

    def test_concurrent_delivery_cannot_update_the_same_clone(self):
        sha = self.publish()
        with deployment.deployment_lock():
            with self.assertRaises(deployment.DeploymentBusy):
                deployment.deploy_release(sha)

    def test_failed_migration_does_not_record_a_success_or_reload_wsgi(self):
        sha = self.publish()
        def fail_migration(arguments, *, timeout):
            if "migrate" in arguments:
                raise deployment.DeploymentError("Migration failed")
            return self.command(arguments, timeout=timeout)
        with patch("bookstore.deployment.run_command", side_effect=fail_migration):
            with self.assertRaises(deployment.DeploymentError):
                deployment.deploy_release(sha)
        self.assertFalse(self.state.exists())
        self.assertEqual(self.wsgi.stat().st_mtime, 1000)
        self.assertEqual(deployment.deploy_release(sha)["status"], "deployed")

    def test_runtime_database_and_private_environment_are_preserved(self):
        sha = self.publish()
        (self.clone_path / ".env").write_text("PRIVATE=test\n", encoding="utf-8")
        (self.clone_path / "data").mkdir()
        database = self.clone_path / "data/db.sqlite3"
        database.write_bytes(b"local-database")
        deployment.deploy_release(sha)
        self.assertEqual(database.read_bytes(), b"local-database")
        self.assertEqual((self.clone_path / ".env").read_text(), "PRIVATE=test\n")

    def test_missing_or_invalid_state_is_handled(self):
        self.assertEqual(deployment.read_state(), {})
        for content in ("not-json", "[]"):
            self.state.write_text(content)
            self.assertEqual(deployment.read_state(), {})


class PythonAnywhereConfigurationTests(SimpleTestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.repo = Repo.init(self.root, initial_branch="main")
        self.addCleanup(self.repo.close)
        identity(self.repo)
        (self.root / "manage.py").write_text("# test")
        self.repo.index.add(["manage.py"])
        self.repo.index.commit("Initial test project")
        self.repo.create_remote("origin", "https://github.com/owner/bookstore.git")

    def test_configuration_generates_private_keys_and_exact_paths(self):
        result = configure(self.root, "student", sys.executable)
        values = dotenv_values(self.root / ".env")
        self.assertEqual(values["DATABASE_ENGINE"], "sqlite")
        self.assertEqual(values["DJANGO_DEBUG"], "0")
        self.assertEqual(values["DEPLOY_REPOSITORY"], "owner/bookstore")
        self.assertGreaterEqual(len(values["DJANGO_SECRET_KEY"]), 64)
        self.assertGreaterEqual(len(values["DEPLOY_WEBHOOK_SECRET"]), 64)
        self.assertEqual(result["domain"], "student.pythonanywhere.com")
        wsgi_code = ast.parse(Path(result["wsgi_example"]).read_text(encoding="utf-8"))
        project_assignment = next(
            statement for statement in wsgi_code.body
            if isinstance(statement, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "project_dir"
                for target in statement.targets
            )
        )
        self.assertEqual(ast.literal_eval(project_assignment.value), str(self.root))
        self.assertNotIn(values["DEPLOY_WEBHOOK_SECRET"], json.dumps(result))
        if os.name == "posix":
            self.assertEqual((self.root / ".env").stat().st_mode & 0o077, 0)

    def test_existing_environment_is_never_overwritten(self):
        environment_file = self.root / ".env"
        environment_file.write_text("EXISTING=keep\n")
        with self.assertRaises(ValueError):
            configure(self.root, "student", sys.executable)
        self.assertEqual(environment_file.read_text(), "EXISTING=keep\n")

    def test_european_domain_can_be_configured(self):
        result = configure(self.root, "student", sys.executable, "student.eu.pythonanywhere.com")
        self.assertEqual(result["webhook_url"], "https://student.eu.pythonanywhere.com/update_server/")

    def test_non_github_or_ssh_remote_is_not_used(self):
        self.repo.remotes.origin.set_url("git@github.com:owner/bookstore.git")
        with self.assertRaises(ValueError):
            configure(self.root, "student", sys.executable)
        self.assertFalse((self.root / ".env").exists())
