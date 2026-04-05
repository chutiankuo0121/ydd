from __future__ import annotations

import argparse
import os

from app_config import load_app_config
from runtime_log import configure_stdout, log


def parse_args() -> argparse.Namespace:
    # 获取脚本所在目录，用于默认路径
    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_config = os.path.join(script_dir, "config.json")
    
    parser = argparse.ArgumentParser(description="Run the Outlook registration app.")
    parser.add_argument(
        "--config",
        default=os.getenv("APP_CONFIG_PATH", default_config),
        help="Path to the JSON config file.",
    )
    parser.add_argument(
        "--skip-xray-check",
        action="store_true",
        help="Skip Xray verification and auto-download during startup.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    configure_stdout()

    log(f"[main] loading config: {args.config}")
    app_config = load_app_config(args.config)
    xray_path = app_config.airport.xray_path

    if args.skip_xray_check:
        log("[main] skipping Xray startup checks")
    else:
        from download_xray import check_xray, ensure_xray_available, get_xray_version

        log(f"[main] preparing Xray: {xray_path}")
        xray_ready = check_xray(xray_path)
        if not xray_ready:
            log("[main] Xray missing, downloading and installing")
            xray_ready = ensure_xray_available(
                xray_path=xray_path,
                force_download=False,
                log_func=log,
            )

        if not xray_ready:
            raise FileNotFoundError(
                f"Xray is missing or unusable: {xray_path}. "
                "Run download_xray.py or check your network and permissions."
            )

        version = get_xray_version(xray_path)
        if version:
            log(f"[main] Xray ready: {version}")

    log("[main] initializing registration service")
    from registration_service import RegistrationService

    service = RegistrationService(app_config)
    log("[main] starting service")
    service.run()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("\n[stop] received keyboard interrupt, exiting")
