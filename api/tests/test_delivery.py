import hashlib
import hmac
import io
import json
from unittest.mock import patch
from urllib.error import HTTPError

from django.contrib.staticfiles.storage import staticfiles_storage
from django.test import Client, SimpleTestCase, override_settings

from bookstore.deployment import DeploymentBusy, DeploymentError
from bookstore.version import VERSION
from deploy.github_hook_client import send_deployment

SECRET = "only-for-webhook-tests"
SHA = "a" * 40


@override_settings(DEPLOY_ENABLED=True, DEPLOY_WEBHOOK_SECRET=SECRET,
                   DEPLOY_REPOSITORY="owner/bookstore", SECURE_SSL_REDIRECT=False)
class WebhookTests(SimpleTestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.deploy = patch("bookstore.views.deploy_release").start()
        self.addCleanup(patch.stopall)
        self.deploy.return_value = {"status": "deployed", "sha": SHA}

    def payload(self):
        return {"ref": "refs/heads/main", "after": SHA,
                "repository": {"full_name": "owner/bookstore"},
                "ci": {"conclusion": "success", "sha": SHA}}

    def post(self, payload=None, *, body=None, event="push", signature=None,
             content_type="application/json"):
        if body is None:
            body = json.dumps(self.payload() if payload is None else payload).encode()
        if signature is None:
            signature = "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
        return self.client.post("/update_server/", data=body, content_type=content_type,
                                HTTP_X_GITHUB_EVENT=event, HTTP_X_HUB_SIGNATURE_256=signature)

    def test_authenticated_approved_main_commit_deploys_without_csrf_cookie(self):
        response = self.post()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["sha"], SHA)
        self.deploy.assert_called_once_with(SHA)

    def test_get_does_not_trigger_deployment(self):
        self.assertEqual(self.client.get("/update_server/").status_code, 405)
        self.deploy.assert_not_called()

    @override_settings(DEPLOY_ENABLED=False)
    def test_webhook_disabled_in_local_environment(self):
        self.assertEqual(self.post().status_code, 404)
        self.deploy.assert_not_called()

    @override_settings(DEPLOY_WEBHOOK_SECRET="")
    def test_missing_secret_cannot_deploy(self):
        self.assertEqual(self.post().status_code, 503)
        self.deploy.assert_not_called()

    def test_missing_or_wrong_signature_cannot_deploy(self):
        for signature in ("", "sha256=invalid", "sha1=" + "a" * 40, "assinatura-invalida"):
            with self.subTest(signature=signature):
                self.assertEqual(self.post(signature=signature).status_code, 403)
        self.deploy.assert_not_called()

    def test_signature_binds_the_exact_request_body(self):
        body = json.dumps(self.payload()).encode()
        signature = "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
        self.assertEqual(self.post(body=body + b" ", signature=signature).status_code, 403)
        self.deploy.assert_not_called()

    def test_invalid_json_is_rejected(self):
        self.assertEqual(self.post(body=b"not-json").status_code, 400)
        self.deploy.assert_not_called()

    def test_json_array_is_rejected(self):
        self.assertEqual(self.post(payload=[]).status_code, 400)
        self.deploy.assert_not_called()

    def test_wrong_content_type_is_rejected(self):
        self.assertEqual(self.post(content_type="text/plain").status_code, 415)
        self.deploy.assert_not_called()

    def test_signed_ping_is_a_connection_check(self):
        self.assertEqual(self.post(payload={}, event="ping").json(), {"status": "ready"})
        self.deploy.assert_not_called()

    def test_other_repository_is_rejected(self):
        payload = self.payload()
        payload["repository"]["full_name"] = "someone/else"
        self.assertEqual(self.post(payload).status_code, 403)
        self.deploy.assert_not_called()

    def test_other_branch_is_ignored(self):
        payload = self.payload()
        payload["ref"] = "refs/heads/feature"
        self.assertEqual(self.post(payload).json()["status"], "ignored")
        self.deploy.assert_not_called()

    def test_other_event_is_ignored(self):
        self.assertEqual(self.post(event="pull_request").json()["status"], "ignored")
        self.deploy.assert_not_called()

    def test_invalid_commit_cannot_be_passed_to_git(self):
        payload = self.payload()
        payload["after"] = "--upload-pack=bad-command"
        self.assertEqual(self.post(payload).status_code, 400)
        self.deploy.assert_not_called()

    def test_failed_or_missing_ci_does_not_deploy(self):
        for ci in (None, {}, {"conclusion": "failure", "sha": SHA},
                   {"conclusion": "success", "sha": "b" * 40}):
            with self.subTest(ci=ci):
                payload = self.payload()
                payload["ci"] = ci
                self.assertEqual(self.post(payload).json()["reason"], "ci_not_approved")
        self.deploy.assert_not_called()

    def test_deployment_busy_is_reported(self):
        self.deploy.side_effect = DeploymentBusy()
        self.assertEqual(self.post().status_code, 409)

    def test_server_error_does_not_expose_internal_details(self):
        self.deploy.side_effect = DeploymentError("private-path-or-key")
        with self.assertLogs("bookstore.views", level="ERROR"):
            response = self.post()
        self.assertEqual(response.status_code, 500)
        self.assertNotIn(b"private-path-or-key", response.content)

    def test_outdated_commit_is_reported_without_claiming_deployment(self):
        self.deploy.return_value = {"status": "ignored", "reason": "newer_commit", "sha": SHA}
        self.assertEqual(self.post().json()["reason"], "newer_commit")


class HelloAndStaticTests(SimpleTestCase):
    def test_hello_is_public_and_links_to_the_api(self):
        response = self.client.get("/hello/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bookstore API")
        self.assertContains(response, "/api/")
        self.assertContains(response, VERSION)

    def test_hello_rejects_post(self):
        self.assertEqual(self.client.post("/hello/").status_code, 405)

    def test_hello_supports_head(self):
        self.assertEqual(self.client.head("/hello/").status_code, 200)

    def test_only_valid_release_sha_is_displayed(self):
        with patch("bookstore.views.read_state", return_value={"sha": SHA}):
            self.assertContains(self.client.get("/hello/"), SHA[:7])
        with patch("bookstore.views.read_state", return_value={"sha": "<script>bad</script>"}):
            self.assertNotContains(self.client.get("/hello/"), "<script>bad</script>")

    @override_settings(DEBUG=False)
    def test_whitenoise_serves_rest_framework_css_in_production_mode(self):
        url = staticfiles_storage.url("rest_framework/css/bootstrap.min.css")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/css", response["Content-Type"])
        response.close()


class DeploymentClientTests(SimpleTestCase):
    def setUp(self):
        self.open = patch("deploy.github_hook_client.urlopen").start()
        self.addCleanup(patch.stopall)
        self.open.return_value = io.BytesIO(json.dumps({"status": "deployed", "sha": SHA}).encode())

    def send(self, **overrides):
        values = {"url": "https://example.pythonanywhere.com/update_server/", "secret": SECRET,
                  "repository": "owner/bookstore", "sha": SHA}
        values.update(overrides)
        return send_deployment(**values)

    def test_client_signs_the_exact_body_and_sends_ci_metadata(self):
        self.assertEqual(self.send()["status"], "deployed")
        request = self.open.call_args.args[0]
        expected = "sha256=" + hmac.new(SECRET.encode(), request.data, hashlib.sha256).hexdigest()
        headers = {key.lower(): value for key, value in request.header_items()}
        self.assertEqual(headers["x-hub-signature-256"], expected)
        self.assertEqual(json.loads(request.data)["ci"], {"conclusion": "success", "sha": SHA})
        self.assertEqual(self.open.call_args.kwargs["timeout"], 290)

    def test_insecure_or_unexpected_target_is_rejected(self):
        for url in ("http://example.pythonanywhere.com/update_server/", "https://example.com/update_server/",
                    "https://example.pythonanywhere.com/other/", "https://u:p@example.pythonanywhere.com/update_server/"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                self.send(url=url)
        self.open.assert_not_called()

    def test_missing_secret_or_invalid_commit_is_rejected(self):
        for values in ({"secret": ""}, {"sha": "invalid"}, {"repository": "invalid"}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                self.send(**values)
        self.open.assert_not_called()

    def test_different_returned_commit_is_not_a_success(self):
        self.open.return_value = io.BytesIO(json.dumps({"status": "deployed", "sha": "b" * 40}).encode())
        with self.assertRaises(RuntimeError):
            self.send()

    def test_http_error_fails_the_deploy_step(self):
        self.open.side_effect = HTTPError("https://example.pythonanywhere.com", 403, "Forbidden", {}, None)
        with self.assertRaisesRegex(RuntimeError, "HTTP 403"):
            self.send()
