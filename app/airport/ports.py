from __future__ import annotations

import socket
import threading


class PortAllocator:
    def __init__(self, base_port: int, search_limit: int) -> None:
        self.base_port = base_port
        self.search_limit = search_limit
        self._lock = threading.Lock()
        self._reserved: set[int] = set()
        self._cursor = 0

    def acquire(self) -> int:
        with self._lock:
            for offset in range(self.search_limit):
                port = self.base_port + ((self._cursor + offset) % self.search_limit)
                if port in self._reserved:
                    continue
                if self._is_port_free(port):
                    self._reserved.add(port)
                    self._cursor = (port - self.base_port + 1) % self.search_limit
                    return port

        raise RuntimeError("没有找到可用的本地代理端口")

    def release(self, port: int) -> None:
        with self._lock:
            self._reserved.discard(port)

    @staticmethod
    def _is_port_free(port: int) -> bool:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False
