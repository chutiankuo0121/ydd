from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

import requests


LATEST_RELEASE_API = "https://api.github.com/repos/XTLS/Xray-core/releases/latest"
DEFAULT_ASSET_NAME = "Xray-windows-64.zip"
DEFAULT_TIMEOUT_SECONDS = 180
DEFAULT_RETRIES = 3
COPY_OPTIONAL_FILES = ("geoip.dat", "geosite.dat")


def _default_log(message: str) -> None:
    print(message, flush=True)


def get_xray_version(xray_path: str | Path = "xray.exe") -> str | None:
    path = Path(xray_path).resolve()
    if not path.exists():
        return None

    try:
        result = subprocess.run(
            [str(path), "version"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(path.parent),
        )
    except Exception:
        return None

    if result.returncode != 0:
        return None

    output = (result.stdout or result.stderr).strip()
    if not output:
        return None
    return output.splitlines()[0]


def check_xray(xray_path: str | Path = "xray.exe") -> bool:
    return get_xray_version(xray_path) is not None


def resolve_latest_download_url(
    asset_name: str = DEFAULT_ASSET_NAME,
    *,
    timeout: int = 30,
) -> tuple[str, str | None]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "ydd-outlook-xray-downloader",
    }

    try:
        response = requests.get(LATEST_RELEASE_API, headers=headers, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
        for asset in payload.get("assets", []):
            if asset.get("name") == asset_name and asset.get("browser_download_url"):
                return asset["browser_download_url"], payload.get("tag_name")
    except Exception:
        pass

    fallback_url = (
        "https://github.com/XTLS/Xray-core/releases/latest/download/" + asset_name
    )
    return fallback_url, None


def _download_file(
    url: str,
    destination: Path,
    *,
    timeout: int,
    log_func,
) -> None:
    headers = {"User-Agent": "ydd-outlook-xray-downloader"}
    with requests.get(
        url,
        stream=True,
        timeout=(30, timeout),
        headers=headers,
        allow_redirects=True,
    ) as response:
        response.raise_for_status()
        with destination.open("wb") as file_handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    file_handle.write(chunk)
    log_func(f"[xray] downloaded archive: {destination}")


def _find_file(root: Path, file_name: str) -> Path | None:
    for candidate in root.rglob(file_name):
        if candidate.is_file():
            return candidate
    return None


def install_xray_zip(archive_path: str | Path, output_path: str | Path) -> Path:
    archive = Path(archive_path).resolve()
    binary_path = Path(output_path).resolve()
    output_dir = binary_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="xray_extract_") as temp_dir:
        extract_dir = Path(temp_dir)
        with zipfile.ZipFile(archive, "r") as zip_file:
            zip_file.extractall(extract_dir)

        extracted_binary = _find_file(extract_dir, "xray.exe")
        if extracted_binary is None:
            raise FileNotFoundError("xray.exe was not found inside the downloaded zip")

        shutil.copy2(extracted_binary, binary_path)
        for optional_name in COPY_OPTIONAL_FILES:
            optional_source = _find_file(extract_dir, optional_name)
            if optional_source is not None:
                shutil.copy2(optional_source, output_dir / optional_name)

    return binary_path


def ensure_xray_available(
    *,
    xray_path: str | Path = "xray.exe",
    asset_name: str = DEFAULT_ASSET_NAME,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    retries: int = DEFAULT_RETRIES,
    force_download: bool = False,
    log_func=_default_log,
) -> bool:
    binary_path = Path(xray_path).resolve()
    if not force_download and check_xray(binary_path):
        log_func(f"[xray] existing binary is ready: {binary_path}")
        return True

    download_url, tag_name = resolve_latest_download_url(asset_name, timeout=30)
    if tag_name:
        log_func(f"[xray] latest release detected: {tag_name}")
    log_func(f"[xray] download source: {download_url}")

    last_error: Exception | None = None
    for attempt in range(1, max(1, retries) + 1):
        try:
            with tempfile.TemporaryDirectory(prefix="xray_download_") as temp_dir:
                archive_path = Path(temp_dir) / asset_name
                log_func(f"[xray] download attempt {attempt}/{retries}")
                _download_file(
                    download_url,
                    archive_path,
                    timeout=timeout,
                    log_func=log_func,
                )
                install_xray_zip(archive_path, binary_path)

            version = get_xray_version(binary_path)
            if version:
                log_func(f"[xray] installed successfully: {version}")
                return True
            last_error = RuntimeError("installed Xray binary failed version check")
        except Exception as exc:
            last_error = exc
            log_func(f"[xray] attempt {attempt} failed: {exc}")

    if last_error is not None:
        log_func(f"[xray] failed after {retries} attempts: {last_error}")
    return False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download or verify Xray.")
    parser.add_argument(
        "--output",
        default="xray.exe",
        help="Path where xray.exe should be stored.",
    )
    parser.add_argument(
        "--asset-name",
        default=DEFAULT_ASSET_NAME,
        help="Release asset name to download from XTLS/Xray-core.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="Read timeout in seconds for the download stream.",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=DEFAULT_RETRIES,
        help="Number of download retries before giving up.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-download even when the current binary passes the version check.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ready = ensure_xray_available(
        xray_path=args.output,
        asset_name=args.asset_name,
        timeout=args.timeout,
        retries=args.retries,
        force_download=args.force,
    )
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
