from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse, urlunparse


DEFAULT_AIRPORT_SUBSCRIPTION_URL = "https://VBO1gePtey83TY0D.yuji.homes?clash=1"
DEFAULT_XRAY_PATH = "xray.exe"
DEFAULT_CONNECTIVITY_TEST_URL = "https://ipinfo.io/json"
MAX_OAUTH_WORKERS = 10


@dataclass(frozen=True)
class OAuthConfig:
    client_id: str
    redirect_url: str
    scopes: tuple[str, ...]
    redirect_port_start: int
    redirect_port_end: int

    @property
    def redirect_port(self) -> int:
        parsed = urlparse(self.redirect_url)
        return parsed.port or 80

    def for_worker(self, worker_id: int) -> "OAuthConfig":
        if worker_id < 1:
            raise ValueError("worker_id must start from 1")

        port = self.redirect_port_start + worker_id - 1
        if port > self.redirect_port_end:
            raise ValueError(
                "worker_id exceeds the configured OAuth callback port range: "
                f"{self.redirect_port_start}-{self.redirect_port_end}"
            )

        parsed = urlparse(self.redirect_url)
        hostname = parsed.hostname or "localhost"
        if ":" in hostname and not hostname.startswith("["):
            netloc = f"[{hostname}]:{port}"
        else:
            netloc = f"{hostname}:{port}"

        worker_redirect_url = urlunparse(
            (
                parsed.scheme or "http",
                netloc,
                parsed.path or "",
                parsed.params or "",
                parsed.query or "",
                parsed.fragment or "",
            )
        )

        return OAuthConfig(
            client_id=self.client_id,
            redirect_url=worker_redirect_url,
            scopes=self.scopes,
            redirect_port_start=self.redirect_port_start,
            redirect_port_end=self.redirect_port_end,
        )


@dataclass(frozen=True)
class AirportConfig:
    subscription_url: str
    xray_path: Path
    base_port: int
    port_search_limit: int
    connectivity_test_url: str
    connectivity_timeout: int
    startup_wait_seconds: float
    max_acquire_attempts: int
    node_failure_cooldown_seconds: int
    duplicate_ip_cooldown_seconds: int


@dataclass(frozen=True)
class AppConfig:
    project_root: Path
    choose_browser: str
    proxy: str | None
    bot_protection_wait: int
    max_captcha_retries: int
    concurrent_flows: int
    max_tasks: int
    email_domain: str
    playwright_browser_path: str
    oauth: OAuthConfig
    airport: AirportConfig


def _resolve_path(project_root: Path, value: str | None, default_value: str) -> Path:
    raw_value = value or default_value
    path = Path(raw_value)
    if not path.is_absolute():
        path = (project_root / path).resolve()
    return path


def load_app_config(config_path: str | Path = "config.json") -> AppConfig:
    config_file = Path(config_path).resolve()
    project_root = config_file.parent

    with config_file.open("r", encoding="utf-8") as file_handle:
        raw = json.load(file_handle)

    max_tasks = int(raw.get("max_tasks", 1))
    if max_tasks < 0:
        raise ValueError("max_tasks cannot be negative; use 0 for infinite mode")

    oauth_raw = raw.get("oauth2") or {}
    airport_raw = raw.get("airport") or {}

    redirect_url = oauth_raw.get("redirect_url", "http://localhost:8001")
    parsed_redirect = urlparse(redirect_url)
    default_redirect_port = parsed_redirect.port or 8001
    redirect_port_start = int(
        oauth_raw.get("redirect_port_start", default_redirect_port)
    )
    redirect_port_end = int(
        oauth_raw.get(
            "redirect_port_end",
            redirect_port_start + MAX_OAUTH_WORKERS - 1,
        )
    )

    xray_path = _resolve_path(
        project_root=project_root,
        value=airport_raw.get("xray_path"),
        default_value=DEFAULT_XRAY_PATH,
    )

    return AppConfig(
        project_root=project_root,
        choose_browser=raw.get("choose_browser", "patchright"),
        proxy=raw.get("proxy"),
        bot_protection_wait=int(raw.get("bot_protection_wait", 11)),
        max_captcha_retries=int(raw.get("max_captcha_retries", 2)),
        concurrent_flows=max(1, int(raw.get("concurrent_flows", 1))),
        max_tasks=max_tasks,
        email_domain=raw.get("email_domain", "outlook.com"),
        playwright_browser_path=(raw.get("playwright") or {}).get("browser_path", ""),
        oauth=OAuthConfig(
            client_id=oauth_raw.get("client_id", ""),
            redirect_url=redirect_url,
            scopes=tuple(oauth_raw.get("Scopes", ())),
            redirect_port_start=redirect_port_start,
            redirect_port_end=redirect_port_end,
        ),
        airport=AirportConfig(
            subscription_url=airport_raw.get(
                "subscription_url", DEFAULT_AIRPORT_SUBSCRIPTION_URL
            ),
            xray_path=xray_path,
            base_port=int(airport_raw.get("base_port", 10800)),
            port_search_limit=int(airport_raw.get("port_search_limit", 200)),
            connectivity_test_url=airport_raw.get(
                "connectivity_test_url", DEFAULT_CONNECTIVITY_TEST_URL
            ),
            connectivity_timeout=int(airport_raw.get("connectivity_timeout", 12)),
            startup_wait_seconds=float(airport_raw.get("startup_wait_seconds", 1.5)),
            max_acquire_attempts=int(airport_raw.get("max_acquire_attempts", 12)),
            node_failure_cooldown_seconds=int(
                airport_raw.get("node_failure_cooldown_seconds", 180)
            ),
            duplicate_ip_cooldown_seconds=int(
                airport_raw.get("duplicate_ip_cooldown_seconds", 60)
            ),
        ),
    )
