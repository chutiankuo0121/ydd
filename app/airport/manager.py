from __future__ import annotations

import random
import threading
import time

from app_config import AirportConfig
from runtime_log import log

from .models import AirportNode, AirportSession
from .ports import PortAllocator
from .subscription import load_airport_nodes_from_multiple
from .xray import XrayRunner, format_exception


class AirportManager:
    def __init__(self, config: AirportConfig) -> None:
        self.config = config
        self.port_allocator = PortAllocator(config.base_port, config.port_search_limit)
        self.xray_runner = XrayRunner(
            xray_path=config.xray_path,
            startup_wait_seconds=config.startup_wait_seconds,
            connectivity_test_url=config.connectivity_test_url,
            connectivity_timeout=config.connectivity_timeout,
        )

        self._lock = threading.Lock()
        self._nodes: list[AirportNode] = []
        self._cooldowns: dict[str, float] = {}
        self._active_node_names: set[str] = set()
        self._node_latency: dict[str, int] = {}  # 记录节点延迟，延迟越低权重越高

    def load_nodes(self) -> list[AirportNode]:
        raw_nodes = load_airport_nodes_from_multiple(self.config.subscription_urls)
        with self._lock:
            self._nodes = raw_nodes
            self._cooldowns.clear()
            self._active_node_names.clear()
            self._node_latency.clear()
        return raw_nodes

    def ensure_nodes_loaded(self) -> list[AirportNode]:
        with self._lock:
            if self._nodes:
                return list(self._nodes)
        return self.load_nodes()

    def acquire_session(self, owner: str) -> AirportSession:
        nodes = self.ensure_nodes_loaded()
        if not nodes:
            raise RuntimeError("没有从机场订阅中加载到可用节点")

        failures: list[str] = []

        for _ in range(max(1, self.config.max_acquire_attempts)):
            node = self._reserve_next_node()
            if node is None:
                break

            port = None
            session = None
            try:
                port = self.port_allocator.acquire()
                log(f"[机场] 预留本地端口 {port}，尝试节点: {node.name}")
                session = self.xray_runner.start_session(node, port)
                session = self.xray_runner.probe_session(session)
                return session
            except Exception as exc:
                failures.append(f"{node.name}: {format_exception(exc)}")
                log(f"[机场] 节点失败: {node.name} -> {format_exception(exc)}")
                if session is not None:
                    self.xray_runner.stop_session(session)
                if port is not None:
                    self.port_allocator.release(port)
                self._release_failed_node(node, exc)

        detail = failures[-3:]
        if detail:
            raise RuntimeError(
                f"{owner} 无法找到可用机场节点。最近错误: {' | '.join(detail)}"
            )
        raise RuntimeError(f"{owner} 无法找到可用机场节点")

    def release_session(
        self,
        session: AirportSession | None,
        penalize: bool = False,
    ) -> None:
        if session is None:
            return

        self.xray_runner.stop_session(session)
        self.port_allocator.release(session.local_port)

        with self._lock:
            self._active_node_names.discard(session.node.name)
            # 记录延迟，延迟越低权重越高
            if session.latency_ms > 0:
                self._node_latency[session.node.name] = session.latency_ms
            if penalize:
                self._cooldowns[session.node.name] = (
                    time.monotonic() + self.config.node_failure_cooldown_seconds
                )

    def _reserve_next_node(self) -> AirportNode | None:
        """按延迟权重选择节点，延迟越低权重越高"""
        with self._lock:
            if not self._nodes:
                return None

            now = time.monotonic()
            candidates: list[AirportNode] = []

            for node in self._nodes:
                cooldown_until = self._cooldowns.get(node.name, 0)
                if cooldown_until > now:
                    continue
                if node.name in self._active_node_names:
                    continue
                candidates.append(node)

            if not candidates:
                return None

            # 计算延迟权重：延迟越低，权重越高
            # 使用反比权重：weight = 1 / latency，延迟未知时默认 200ms
            weights = []
            for node in candidates:
                latency = self._node_latency.get(node.name, 200)
                # 最小延迟 10ms 避免除以 0，权重为延迟的倒数
                weight = 1000.0 / max(latency, 10)
                weights.append(weight)

            selected_node = random.choices(candidates, weights=weights, k=1)[0]
            self._active_node_names.add(selected_node.name)
            return selected_node

        return None

    def _release_failed_node(self, node: AirportNode, exc: Exception) -> None:
        with self._lock:
            self._active_node_names.discard(node.name)
            self._cooldowns[node.name] = (
                time.monotonic() + self.config.node_failure_cooldown_seconds
            )
