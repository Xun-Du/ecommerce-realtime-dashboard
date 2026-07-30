"""Tests for the M0 dashboard placeholder."""

from unittest.mock import Mock

import frontend.app as dashboard


def test_dashboard_renders_pending_backend_message(monkeypatch) -> None:
    title = Mock()
    info = Mock()
    monkeypatch.setattr(dashboard.st, "set_page_config", Mock())
    monkeypatch.setattr(dashboard.st, "title", title)
    monkeypatch.setattr(dashboard.st, "info", info)

    dashboard.render_dashboard()

    title.assert_called_once_with("实时电商 A/B 测试与归因分析看板")
    info.assert_called_once()
    assert "后端未连接／待接入" in info.call_args.args[0]
