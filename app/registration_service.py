from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

from airport import AirportManager, ensure_requests_socks_support, format_exception
from app_config import AppConfig, MAX_OAUTH_WORKERS
from runtime_log import log
from utils import generate_strong_password, random_email


class TaskCoordinator:
    def __init__(self, max_tasks: int) -> None:
        self.max_tasks = max_tasks
        self.infinite_mode = max_tasks == 0
        self._lock = threading.Lock()
        self._next_task_id = 1
        self.success_count = 0
        self.failure_count = 0

    def claim_task(self) -> int | None:
        with self._lock:
            if not self.infinite_mode and self._next_task_id > self.max_tasks:
                return None
            task_id = self._next_task_id
            self._next_task_id += 1
            return task_id

    def record_result(self, success: bool) -> tuple[int, int]:
        with self._lock:
            if success:
                self.success_count += 1
            else:
                self.failure_count += 1
            return self.success_count, self.failure_count


class RegistrationService:
    def __init__(self, app_config: AppConfig) -> None:
        self.app_config = app_config
        self.airport_manager = AirportManager(app_config.airport)
        self.coordinator = TaskCoordinator(app_config.max_tasks)
        self.stop_event = threading.Event()

    def run(self) -> None:
        if self.app_config.concurrent_flows > MAX_OAUTH_WORKERS:
            raise ValueError(
                f"concurrent_flows={self.app_config.concurrent_flows} 超过支持上限 "
                f"{MAX_OAUTH_WORKERS}。请设置为 1-{MAX_OAUTH_WORKERS}。"
            )

        log("[启动] 检查 SOCKS 依赖...")
        ensure_requests_socks_support()

        log("[启动] 正在加载机场节点...")
        nodes = self.airport_manager.load_nodes()
        obfs_count = sum(1 for node in nodes if node.plugin == "obfs")
        singapore_count = sum(1 for node in nodes if "新加坡" in node.name)
        japan_count = sum(1 for node in nodes if "日本" in node.name)
        taiwan_hk_count = sum(
            1 for node in nodes if ("台湾" in node.name or "香港" in node.name)
        )
        log(
            f"[机场] 已加载 {len(nodes)} 个节点"
            + (f"，其中 {obfs_count} 个带 obfs(http)" if obfs_count else "")
        )
        log(
            "[机场] 地区池: "
            f"新加坡={singapore_count} 日本={japan_count} 台湾香港={taiwan_hk_count}"
        )
        task_mode = "无限循环" if self.coordinator.infinite_mode else str(self.app_config.max_tasks)
        log(
            f"[启动] 并发线程: {self.app_config.concurrent_flows} | "
            f"任务模式: {task_mode}"
        )

        try:
            with ThreadPoolExecutor(
                max_workers=self.app_config.concurrent_flows,
                thread_name_prefix="register-worker",
            ) as executor:
                futures = [
                    executor.submit(self._worker_loop, worker_id)
                    for worker_id in range(1, self.app_config.concurrent_flows + 1)
                ]
                for future in futures:
                    future.result()
        except KeyboardInterrupt:
            log("\n[停止] 收到中断信号，等待当前任务完成清理...")
            self.stop()
            raise
        finally:
            log(
                f"[总结] 成功={self.coordinator.success_count} | "
                f"失败={self.coordinator.failure_count}"
            )

    def stop(self) -> None:
        self.stop_event.set()

    def _worker_loop(self, worker_id: int) -> None:
        while not self.stop_event.is_set():
            task_id = self.coordinator.claim_task()
            if task_id is None:
                return
            self._run_single_task(worker_id=worker_id, task_id=task_id)

    def _run_single_task(self, worker_id: int, task_id: int) -> None:
        prefix = f"[Worker {worker_id}][Task {task_id}]"
        log(f"\n{prefix} 开始分配机场节点...")

        session = None
        controller = None
        page = None
        success = False
        penalize_proxy = False

        try:
            session = self.airport_manager.acquire_session(owner=prefix)
            log(
                f"{prefix} 代理已启动: {session.proxy_url} -> {session.node.name} "
                f"| {session.exit_ip} {session.country} {session.region} "
                f"| {session.latency_ms}ms"
            )

            log(f"{prefix} 正在创建浏览器控制器...")
            controller = self._create_controller(session.proxy_url)
            log(f"{prefix} 正在打开浏览器页面...")
            page = controller.get_thread_page()
            if not page:
                penalize_proxy = True
                raise RuntimeError("浏览器页面创建失败")

            email = random_email()
            password = generate_strong_password()
            full_email = f"{email}@{self.app_config.email_domain}"
            log(f"{prefix} 注册邮箱: {full_email}")

            register_ok = controller.outlook_register(page, email, password)
            if not register_ok:
                penalize_proxy = True
                log(f"{prefix} 注册流程失败")
                return

            log(f"{prefix} 开始获取 OAuth token...")
            from get_token import get_access_token

            token_result = get_access_token(
                page=page,
                email=email,
                email_domain=self.app_config.email_domain,
                proxy_url=session.requests_proxy_url,
                app_config=self.app_config,
                oauth_config=self.app_config.oauth.for_worker(worker_id),
            )
            if not token_result[0]:
                penalize_proxy = True
                log(f"{prefix} OAuth token 获取失败")
                return

            refresh_token, _, _ = token_result
            log(f"{prefix} 正在保存账号到 Supabase...")
            from supabase_db import save_email

            save_email(
                full_email,
                password,
                refresh_token,
                self.app_config.oauth.client_id,
            )
            success = True
            log(f"{prefix} 成功保存账号: {full_email}")

        except Exception as exc:
            log(f"{prefix} 异常: {format_exception(exc)}")

        finally:
            if controller and page:
                controller.clean_up(page, "done_browser")
            if controller:
                controller.clean_up(type="all_browser")

            self.airport_manager.release_session(
                session,
                penalize=penalize_proxy and not success,
            )

            success_count, failure_count = self.coordinator.record_result(success)
            log(
                f"{prefix} 完成 | success={success} | "
                f"累计成功={success_count} | 累计失败={failure_count}"
            )

    def _create_controller(self, proxy_url: str):
        browser_name = self.app_config.choose_browser.lower()
        if browser_name == "patchright":
            from controllers.patchright_controller import PatchrightController

            return PatchrightController(self.app_config, proxy_url=proxy_url)
        if browser_name == "playwright":
            from controllers.playwright_controller import PlaywrightController

            return PlaywrightController(self.app_config, proxy_url=proxy_url)
        raise ValueError(f"不支持的浏览器类型: {self.app_config.choose_browser}")
