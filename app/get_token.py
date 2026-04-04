import base64
import hashlib
import secrets
import string
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlparse

import requests

from app_config import AppConfig, OAuthConfig, load_app_config
from airport import build_requests_proxies
from runtime_log import log


def generate_code_verifier(length=128):
    alphabet = string.ascii_letters + string.digits + "-._~"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def generate_code_challenge(code_verifier):
    sha256_hash = hashlib.sha256(code_verifier.encode()).digest()
    return base64.urlsafe_b64encode(sha256_hash).decode().rstrip("=")


class OAuthCallbackState:
    def __init__(self, port: int) -> None:
        self.port = port
        self._lock = threading.Lock()
        self.auth_code = None
        self.auth_error = None
        self.auth_error_description = None

    def reset(self) -> None:
        with self._lock:
            self.auth_code = None
            self.auth_error = None
            self.auth_error_description = None

    def update(self, code, error, error_description) -> None:
        with self._lock:
            self.auth_code = code
            self.auth_error = error
            self.auth_error_description = error_description

    def snapshot(self):
        with self._lock:
            return self.auth_code, self.auth_error, self.auth_error_description


class ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True


class OAuthCallbackServer:
    def __init__(self, port: int) -> None:
        self.port = port
        self.state = OAuthCallbackState(port=port)
        self._server = ReusableThreadingHTTPServer(
            ("localhost", port), self._build_handler()
        )
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            daemon=True,
            name=f"oauth-callback-{port}",
        )
        self._thread.start()

    def _build_handler(self):
        callback_state = self.state

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                parsed = urlparse(self.path)
                query = parse_qs(parsed.query)

                code = (query.get("code") or [None])[0]
                error = (query.get("error") or [None])[0]
                error_description = (query.get("error_description") or [None])[0]

                log(
                    "[OAuth Callback] "
                    f"port={callback_state.port} "
                    f"path={parsed.path or '/'} "
                    f"has_code={bool(code)} "
                    f"has_error={bool(error)}"
                )

                callback_state.update(code, error, error_description)

                self.send_response(200 if code or error else 400)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()

                if code:
                    html = (
                        "<html><body><h1>Authorization Success!</h1>"
                        "<p>You can close this window now.</p></body></html>"
                    )
                elif error:
                    html = (
                        "<html><body><h1>Authorization Failed</h1><p>"
                        + (error_description or error)
                        + "</p></body></html>"
                    )
                else:
                    html = "<html><body><h1>No code found</h1></body></html>"

                try:
                    self.wfile.write(html.encode("utf-8"))
                except Exception as exc:
                    log(
                        f"[OAuth Callback] port={callback_state.port} "
                        f"response write exception: {exc}"
                    )

            def log_message(self, format, *args):
                pass

        return Handler


_CALLBACK_SERVERS: dict[int, OAuthCallbackServer] = {}
_CALLBACK_SERVERS_LOCK = threading.Lock()


def get_or_start_callback_server(port: int) -> OAuthCallbackServer:
    with _CALLBACK_SERVERS_LOCK:
        server = _CALLBACK_SERVERS.get(port)
        if server is None:
            log(f"[OAuth] 启动常驻本地回调服务器... port={port}")
            server = OAuthCallbackServer(port=port)
            _CALLBACK_SERVERS[port] = server
        return server


def handle_oauth2_form(page, email, email_domain="outlook.com"):
    try:
        page.locator("[name=\"loginfmt\"]").fill(f"{email}@{email_domain}", timeout=20000)
        page.locator("#idSIButton9").click(timeout=7000)
        page.locator("[data-testid=\"appConsentPrimaryButton\"]").click(timeout=120000)
    except Exception:
        pass


def _resolve_oauth_config(app_config: AppConfig | None, oauth_config: OAuthConfig | None):
    if oauth_config is not None:
        return oauth_config
    if app_config is not None:
        return app_config.oauth
    return load_app_config().oauth


def _resolve_proxy_settings(proxy_url: str | None):
    if not proxy_url:
        return None
    return build_requests_proxies(proxy_url)


def _safe_page_url(page):
    try:
        return page.url or "<empty>"
    except Exception as exc:
        return f"<unavailable: {exc}>"


def _extract_callback_result_from_page(page, redirect_url: str):
    try:
        current_url = page.url
    except Exception:
        return None

    if not current_url:
        return None

    redirect = urlparse(redirect_url)
    current = urlparse(current_url)

    if current.scheme != redirect.scheme:
        return None
    if current.hostname != redirect.hostname:
        return None
    if (current.port or 80) != (redirect.port or 80):
        return None

    query = parse_qs(current.query)
    code = (query.get("code") or [None])[0]
    error = (query.get("error") or [None])[0]
    error_description = (query.get("error_description") or [None])[0]

    if not code and not error:
        return None

    log(
        "[OAuth] 从页面 URL 捕获回调 "
        f"port={redirect.port or 80} "
        f"has_code={bool(code)} "
        f"has_error={bool(error)}"
    )
    return {
        "code": code,
        "error": error,
        "error_description": error_description,
    }


def _extract_callback_result_from_url(current_url: str, redirect_url: str):
    if not current_url:
        return None

    redirect = urlparse(redirect_url)
    current = urlparse(current_url)

    if current.scheme != redirect.scheme:
        return None
    if current.hostname != redirect.hostname:
        return None
    if (current.port or 80) != (redirect.port or 80):
        return None

    query = parse_qs(current.query)
    code = (query.get("code") or [None])[0]
    error = (query.get("error") or [None])[0]
    error_description = (query.get("error_description") or [None])[0]

    if not code and not error:
        return None

    return {
        "code": code,
        "error": error,
        "error_description": error_description,
    }


def get_access_token(
    page,
    email,
    email_domain="outlook.com",
    proxy_url: str | None = None,
    app_config: AppConfig | None = None,
    oauth_config: OAuthConfig | None = None,
):
    oauth = _resolve_oauth_config(app_config=app_config, oauth_config=oauth_config)
    parsed_redirect = urlparse(oauth.redirect_url)
    callback_port = parsed_redirect.port or 8001
    callback_server = get_or_start_callback_server(callback_port)
    callback_server.state.reset()
    callback_capture = {
        "url": None,
        "result": None,
        "request_failed": None,
    }

    code_verifier = generate_code_verifier()
    code_challenge = generate_code_challenge(code_verifier)
    scope = " ".join(oauth.scopes)

    params = {
        "client_id": oauth.client_id,
        "response_type": "code",
        "redirect_uri": oauth.redirect_url,
        "scope": scope,
        "response_mode": "query",
        "prompt": "select_account",
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }

    def on_frame_navigated(frame):
        try:
            url = frame.url
        except Exception:
            return
        result = _extract_callback_result_from_url(url, oauth.redirect_url)
        if result is not None:
            callback_capture["url"] = url
            callback_capture["result"] = result
            log(f"[OAuth] 导航事件捕获回调 URL: {url}")

    def on_request(request):
        try:
            url = request.url
        except Exception:
            return
        result = _extract_callback_result_from_url(url, oauth.redirect_url)
        if result is not None:
            callback_capture["url"] = url
            callback_capture["result"] = result
            log(f"[OAuth] 请求事件捕获回调 URL: {url}")

    def on_request_failed(request):
        try:
            url = request.url
        except Exception:
            return
        redirect = urlparse(oauth.redirect_url)
        current = urlparse(url)
        if (
            current.scheme == redirect.scheme
            and current.hostname == redirect.hostname
            and (current.port or 80) == (redirect.port or 80)
        ):
            failure = request.failure
            callback_capture["request_failed"] = failure
            log(f"[OAuth] localhost 请求失败: {url} | {failure}")

    page.on("framenavigated", on_frame_navigated)
    page.on("request", on_request)
    page.on("requestfailed", on_request_failed)

    try:
        log(f"[OAuth] 使用独立回调端口 {callback_port}")
        log("[OAuth] 准备发起授权页面...")
        auth_url = (
            "https://login.microsoftonline.com/common/oauth2/v2.0/authorize?"
            + "&".join(f"{k}={quote(v)}" for k, v in params.items())
        )

        max_retry = 2
        for current_try in range(max_retry):
            try:
                page.wait_for_timeout(250)
                page.goto(auth_url)
                break
            except Exception:
                if current_try == max_retry - 1:
                    return False, False, False

        handle_oauth2_form(page, email, email_domain)

        log("[OAuth] 正在等待本地回调或页面跳转...")
        auth_code = None
        auth_error = None
        auth_error_description = None

        for waited_seconds in range(1, 121):
            if callback_capture["result"] is not None:
                auth_code = callback_capture["result"]["code"]
                auth_error = callback_capture["result"]["error"]
                auth_error_description = callback_capture["result"]["error_description"]
                log(
                    "[OAuth] 事件监听已捕获回调 "
                    f"has_code={bool(auth_code)} "
                    f"has_error={bool(auth_error)}"
                )
                break

            auth_code, auth_error, auth_error_description = callback_server.state.snapshot()
            if auth_code or auth_error:
                log(
                    "[OAuth] 本地回调已返回 "
                    f"port={callback_port} "
                    f"has_code={bool(auth_code)} "
                    f"has_error={bool(auth_error)}"
                )
                break

            page_result = _extract_callback_result_from_page(page, oauth.redirect_url)
            if page_result is not None:
                auth_code = page_result["code"]
                auth_error = page_result["error"]
                auth_error_description = page_result["error_description"]
                break

            if waited_seconds % 5 == 0:
                log(f"[OAuth] 当前页面 URL: {_safe_page_url(page)}")

            time.sleep(1)

        if not auth_code and not auth_error:
            log("[OAuth Error] 等待授权回调超时")
            return False, False, False

        if auth_error:
            log(f"[OAuth Error] 授权失败: {auth_error}")
            if auth_error_description:
                log(f"[OAuth Error] {auth_error_description}")
            return False, False, False

        if not auth_code:
            log("[OAuth Error] 未收到 authorization code")
            return False, False, False

        log("[OAuth] 已收到授权码，开始交换 token...")

    except Exception as exc:
        log(f"[OAuth Error] OAuth 流程异常: {exc}")
        return False, False, False
    finally:
        try:
            page.remove_listener("framenavigated", on_frame_navigated)
            page.remove_listener("request", on_request)
            page.remove_listener("requestfailed", on_request_failed)
        except Exception:
            pass

    token_data = {
        "client_id": oauth.client_id,
        "code": auth_code,
        "redirect_uri": oauth.redirect_url,
        "grant_type": "authorization_code",
        "code_verifier": code_verifier,
        "scope": scope,
    }

    response = requests.post(
        "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        data=token_data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        proxies=_resolve_proxy_settings(proxy_url),
        timeout=30,
    )

    resp_json = response.json()

    if "refresh_token" in resp_json:
        refresh_token = resp_json["refresh_token"]
        access_token = resp_json.get("access_token", "")
        expire_at = datetime.now().timestamp() + resp_json.get("expires_in", 0)
        return refresh_token, access_token, expire_at

    log("[OAuth Error] Token exchange failed")
    log(f"[OAuth Error] Status: {response.status_code}")
    log(f"[OAuth Error] Response: {resp_json}")
    if "error_description" in resp_json:
        log(f"[OAuth Error] Description: {resp_json['error_description']}")
    return False, False, False
