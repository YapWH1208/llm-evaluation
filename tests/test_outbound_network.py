from __future__ import annotations

import httpcore
import httpx

from app.services.outbound_network import _PinnedNetworkBackend, pinned_outbound_transport


def test_pinned_backend_connects_only_to_validated_addresses(monkeypatch) -> None:
    connected: list[tuple[str, int]] = []
    marker = object()

    def connect(_self, host: str, port: int, **_kwargs: object):
        connected.append((host, port))
        return marker

    monkeypatch.setattr(httpcore.SyncBackend, "connect_tcp", connect)
    backend = _PinnedNetworkBackend(("93.184.216.34", "93.184.216.35"))

    assert backend.connect_tcp("provider.example.test", 443) is marker
    assert backend.connect_tcp("provider.example.test", 443) is marker
    assert connected == [("93.184.216.34", 443), ("93.184.216.35", 443)]


def test_pinned_transport_preserves_an_injected_test_transport() -> None:
    injected = httpx.MockTransport(lambda _request: httpx.Response(200))
    assert pinned_outbound_transport(("93.184.216.34",), injected_transport=injected) is injected
