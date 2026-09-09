"""Tests for update_check helpers that still exist after cutting PyPI."""

from __future__ import annotations

from openswap.update_check import (
    _checkout_root,
    _detect_install_method,
    _package_is_git_checkout,
    check_for_update,
)


class TestGitCheckoutGuard:
    def test_package_from_git_checkout_is_detected(self, tmp_path):
        (tmp_path / ".git").mkdir()
        package_file = tmp_path / "src" / "openswap" / "__init__.py"
        package_file.parent.mkdir(parents=True)
        package_file.write_text("")

        assert _package_is_git_checkout(package_file) is True
        assert _checkout_root(package_file) == tmp_path

    def test_package_inside_uv_tools_without_git_is_not_a_checkout(self, tmp_path):
        package_file = (
            tmp_path
            / "uv"
            / "tools"
            / "openswap"
            / "lib"
            / "python3.12"
            / "site-packages"
            / "openswap"
            / "__init__.py"
        )
        package_file.parent.mkdir(parents=True)
        package_file.write_text("")

        assert _package_is_git_checkout(package_file) is False

    def test_venv_inside_another_git_repo_is_not_a_checkout(self, tmp_path):
        (tmp_path / ".git").mkdir()
        package_file = (
            tmp_path
            / ".venv"
            / "lib"
            / "python3.12"
            / "site-packages"
            / "openswap"
            / "__init__.py"
        )
        package_file.parent.mkdir(parents=True)
        package_file.write_text("")

        assert _checkout_root(package_file) is None
        assert _package_is_git_checkout(package_file) is False

    def test_direct_url_editable_checkout(self, tmp_path):
        repo = tmp_path / "openswap"
        repo.mkdir()
        (repo / ".git").mkdir()
        (repo / "src" / "openswap").mkdir(parents=True)
        (repo / "src" / "openswap" / "__init__.py").write_text("")
        dist = (
            tmp_path
            / "uv"
            / "tools"
            / "openswap"
            / "lib"
            / "python3.12"
            / "site-packages"
            / "openswap-0.1.0.dist-info"
        )
        dist.mkdir(parents=True)
        (dist / "direct_url.json").write_text(
            '{"url":"' + repo.as_uri() + '","dir_info":{"editable":true}}'
        )
        package_file = dist.parent / "openswap" / "__init__.py"
        package_file.parent.mkdir(parents=True)
        package_file.write_text("")

        assert _checkout_root(package_file) == repo

    def test_direct_url_nested_in_another_git_repo_is_rejected(self, tmp_path):
        vendor = tmp_path / "vendor" / "openswap"
        (vendor / "src" / "openswap").mkdir(parents=True)
        (vendor / "src" / "openswap" / "__init__.py").write_text("")
        (tmp_path / ".git").mkdir()
        dist = (
            tmp_path
            / ".venv"
            / "lib"
            / "python3.12"
            / "site-packages"
            / "openswap-0.1.0.dist-info"
        )
        dist.mkdir(parents=True)
        (dist / "direct_url.json").write_text(
            '{"url":"' + vendor.as_uri() + '","dir_info":{}}'
        )
        package_file = dist.parent / "openswap" / "__init__.py"
        package_file.parent.mkdir(parents=True)
        package_file.write_text("")

        assert _checkout_root(package_file) is None


class TestDetectInstallMethod:
    def _set_prefix(self, monkeypatch, prefix: str) -> None:
        monkeypatch.setattr("openswap.update_check.sys.prefix", prefix)
        monkeypatch.delenv("UV_TOOL_DIR", raising=False)
        monkeypatch.delenv("PIPX_HOME", raising=False)

    def test_uv_tool_default_path(self, monkeypatch):
        self._set_prefix(monkeypatch, "/home/me/.local/share/uv/tools/openswap")
        assert _detect_install_method() == "uv"

    def test_pipx_default_path(self, monkeypatch):
        self._set_prefix(monkeypatch, "/home/me/.local/pipx/venvs/openswap")
        assert _detect_install_method() == "pipx"

    def test_source_checkout_returns_none(self, monkeypatch):
        self._set_prefix(monkeypatch, "/home/me/code/openswap/.venv")
        assert _detect_install_method() is None


class TestCheckForUpdate:
    def test_never_nags(self):
        assert check_for_update("0.3.2") is None
        assert check_for_update("9.9.9") is None
