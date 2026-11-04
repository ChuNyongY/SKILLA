from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType

import pytest
from pydantic import SecretStr

from javis_core.credential_store import CredentialStatus
from javis_core.product_host import (
    ProductPreflightItem,
    ProductPreflightReport,
    ProductPreflightStatus,
)
from javis_core.product_startup import (
    CredentialSetupResult,
    ProductStartupExitCode,
    run_tk_nim_credential_setup,
    run_windowed_product_startup,
    save_nim_credential_for_startup,
)


def _report(*failed: str) -> ProductPreflightReport:
    items = tuple(
        ProductPreflightItem(
            component=component,
            status=(
                ProductPreflightStatus.FAIL
                if component in failed
                else ProductPreflightStatus.PASS
            ),
            code="FAILED" if component in failed else "OK",
        )
        for component in ("config", "secret.nim", "doctor")
    )
    return ProductPreflightReport(ready=not failed, items=items)


def _installed_executable(tmp_path: Path) -> Path:
    executable = tmp_path / "SKILLA-Tray.exe"
    config = tmp_path / "config" / "product_host.json"
    config.parent.mkdir()
    executable.write_bytes(b"fixture")
    config.write_text("{}", encoding="utf-8")
    return executable


def test_missing_credential_shows_fixed_message_without_running_preflight(
    tmp_path: Path,
) -> None:
    executable = _installed_executable(tmp_path)
    dialogs: list[tuple[str, str]] = []
    calls: list[str] = []

    result = run_windowed_product_startup(
        executable,
        credential_status_loader=lambda: CredentialStatus.ABSENT,
        preflight_runner=lambda *_args: calls.append("preflight") or _report(),
        product_runner=lambda *_args: calls.append("product") or 0,
        show_dialog=lambda title, message: dialogs.append((title, message)),
    )

    assert result == ProductStartupExitCode.CREDENTIAL_MISSING
    assert calls == []
    assert dialogs == [
        (
            "SKILLA 시작 오류",
            "NVIDIA NIM API 키가 등록되어 있지 않습니다. 설치 폴더의 사용 설명서에 따라 "
            "API 키를 등록한 뒤 다시 실행해 주세요.",
        )
    ]


def test_credential_exception_never_reaches_dialog(tmp_path: Path) -> None:
    executable = _installed_executable(tmp_path)
    dialogs: list[str] = []

    def fail_with_private_data() -> CredentialStatus:
        raise RuntimeError("nvapi-private C:\\Users\\private")

    result = run_windowed_product_startup(
        executable,
        credential_status_loader=fail_with_private_data,
        preflight_runner=lambda *_args: _report(),
        product_runner=lambda *_args: 0,
        show_dialog=lambda _title, message: dialogs.append(message),
    )

    assert result == ProductStartupExitCode.CREDENTIAL_INVALID
    rendered = " ".join(dialogs)
    assert "private" not in rendered
    assert "Users" not in rendered
    assert "nvapi-" not in rendered


def test_first_run_setup_saves_rechecks_and_continues(tmp_path: Path) -> None:
    executable = _installed_executable(tmp_path)
    statuses = iter((CredentialStatus.ABSENT, CredentialStatus.PRESENT))
    calls: list[str] = []

    result = run_windowed_product_startup(
        executable,
        credential_status_loader=lambda: next(statuses),
        credential_setup=lambda: calls.append("setup") or CredentialSetupResult.SAVED,
        preflight_runner=lambda *_args: calls.append("preflight") or _report(),
        product_runner=lambda *_args: calls.append("product") or 0,
        show_dialog=lambda *_args: (_ for _ in ()).throw(AssertionError("unexpected dialog")),
    )

    assert result == ProductStartupExitCode.OK
    assert calls == ["setup", "preflight", "product"]


def test_first_run_setup_cancel_is_quiet_and_stops(tmp_path: Path) -> None:
    executable = _installed_executable(tmp_path)
    calls: list[str] = []
    dialogs: list[str] = []

    result = run_windowed_product_startup(
        executable,
        credential_status_loader=lambda: CredentialStatus.ABSENT,
        credential_setup=lambda: CredentialSetupResult.CANCELLED,
        preflight_runner=lambda *_args: calls.append("preflight") or _report(),
        product_runner=lambda *_args: calls.append("product") or 0,
        show_dialog=lambda _title, message: dialogs.append(message),
    )

    assert result == ProductStartupExitCode.CREDENTIAL_MISSING
    assert calls == []
    assert dialogs == []


def test_first_run_setup_failure_is_not_followed_by_duplicate_dialog(tmp_path: Path) -> None:
    executable = _installed_executable(tmp_path)
    dialogs: list[str] = []

    result = run_windowed_product_startup(
        executable,
        credential_status_loader=lambda: CredentialStatus.ABSENT,
        credential_setup=lambda: CredentialSetupResult.FAILED,
        preflight_runner=lambda *_args: _report(),
        product_runner=lambda *_args: 0,
        show_dialog=lambda _title, message: dialogs.append(message),
    )

    assert result == ProductStartupExitCode.CREDENTIAL_INVALID
    assert dialogs == []


def test_first_run_setup_exception_is_redacted(tmp_path: Path) -> None:
    executable = _installed_executable(tmp_path)
    dialogs: list[str] = []

    def fail_setup() -> CredentialSetupResult:
        raise RuntimeError("nvapi-private C:\\Users\\private")

    result = run_windowed_product_startup(
        executable,
        credential_status_loader=lambda: CredentialStatus.ABSENT,
        credential_setup=fail_setup,
        preflight_runner=lambda *_args: _report(),
        product_runner=lambda *_args: 0,
        show_dialog=lambda _title, message: dialogs.append(message),
    )

    assert result == ProductStartupExitCode.CREDENTIAL_INVALID
    assert "private" not in " ".join(dialogs)
    assert "Users" not in " ".join(dialogs)
    assert "nvapi-" not in " ".join(dialogs)


def test_first_run_setup_must_be_verified_before_preflight(tmp_path: Path) -> None:
    executable = _installed_executable(tmp_path)
    calls: list[str] = []
    dialogs: list[str] = []

    result = run_windowed_product_startup(
        executable,
        credential_status_loader=lambda: CredentialStatus.ABSENT,
        credential_setup=lambda: CredentialSetupResult.SAVED,
        preflight_runner=lambda *_args: calls.append("preflight") or _report(),
        product_runner=lambda *_args: calls.append("product") or 0,
        show_dialog=lambda _title, message: dialogs.append(message),
    )

    assert result == ProductStartupExitCode.CREDENTIAL_INVALID
    assert calls == []
    assert len(dialogs) == 1


def test_first_run_saver_wraps_key_as_secret_and_redacts_provision_errors() -> None:
    received: list[SecretStr] = []

    assert (
        save_nim_credential_for_startup(
            "nvapi-1234567890",
            provisioner=lambda secret: received.append(secret),
        )
        is CredentialSetupResult.SAVED
    )
    assert len(received) == 1
    assert isinstance(received[0], SecretStr)
    assert str(received[0]) == "**********"

    def fail(_secret: SecretStr) -> None:
        raise RuntimeError("nvapi-private C:\\Users\\private")

    assert (
        save_nim_credential_for_startup("nvapi-1234567890", provisioner=fail)
        is CredentialSetupResult.FAILED
    )


def test_first_run_tk_setup_masks_clears_and_saves(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_tk = ModuleType("tkinter")
    observed: dict[str, object] = {}

    class FakeRoot:
        def title(self, value: str) -> None:
            observed["title"] = value

        def geometry(self, _value: str) -> None:
            pass

        def resizable(self, _width: bool, _height: bool) -> None:
            pass

        def protocol(self, _name: str, _callback: object) -> None:
            pass

        def bind(self, _sequence: str, _callback: object) -> None:
            pass

        def destroy(self) -> None:
            observed["destroyed"] = True

        def mainloop(self) -> None:
            variable = observed["variable"]
            assert isinstance(variable, FakeStringVar)
            variable.set("nvapi-1234567890")
            callback = observed["save_callback"]
            assert callable(callback)
            callback()

    class FakeStringVar:
        def __init__(self, *, master: object) -> None:
            del master
            self.value = ""
            observed["variable"] = self

        def get(self) -> str:
            return self.value

        def set(self, value: str) -> None:
            self.value = value

    class FakeWidget:
        def __init__(self, _parent: object, **_kwargs: object) -> None:
            pass

        def pack(self, **_kwargs: object) -> FakeWidget:
            return self

    class FakeEntry(FakeWidget):
        def __init__(self, parent: object, **kwargs: object) -> None:
            super().__init__(parent, **kwargs)
            observed["mask"] = kwargs.get("show")

        def delete(self, _start: object, _end: object) -> None:
            observed["entry_cleared"] = True

        def focus_set(self) -> None:
            pass

    class FakeButton(FakeWidget):
        def __init__(self, parent: object, **kwargs: object) -> None:
            super().__init__(parent, **kwargs)
            if kwargs.get("text") == "저장하고 계속":
                observed["save_callback"] = kwargs["command"]

    fake_tk.Tk = FakeRoot  # type: ignore[attr-defined]
    fake_tk.StringVar = FakeStringVar  # type: ignore[attr-defined]
    fake_tk.Frame = FakeWidget  # type: ignore[attr-defined]
    fake_tk.Label = FakeWidget  # type: ignore[attr-defined]
    fake_tk.Entry = FakeEntry  # type: ignore[attr-defined]
    fake_tk.Button = FakeButton  # type: ignore[attr-defined]
    fake_tk.END = "end"  # type: ignore[attr-defined]
    fake_tk.messagebox = ModuleType("tkinter.messagebox")  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "tkinter", fake_tk)
    monkeypatch.setitem(sys.modules, "tkinter.messagebox", fake_tk.messagebox)
    saved: list[str] = []

    result = run_tk_nim_credential_setup(
        saver=lambda raw: saved.append(raw) or CredentialSetupResult.SAVED
    )

    variable = observed["variable"]
    assert isinstance(variable, FakeStringVar)
    assert result is CredentialSetupResult.SAVED
    assert saved == ["nvapi-1234567890"]
    assert observed["mask"] == "*"
    assert variable.get() == ""
    assert observed["entry_cleared"] is True
    assert observed["destroyed"] is True


def test_preflight_failure_maps_to_fixed_component_message(tmp_path: Path) -> None:
    executable = _installed_executable(tmp_path)
    observed: list[tuple[str, str, int]] = []
    cases = (
        ("config", "구성 파일", ProductStartupExitCode.CONFIGURATION_INVALID),
        ("secret.nim", "API 키", ProductStartupExitCode.CREDENTIAL_INVALID),
        ("doctor", "필수 구성 요소", ProductStartupExitCode.COMPONENTS_INVALID),
    )
    for component, _phrase, _expected in cases:
        messages: list[str] = []
        result = run_windowed_product_startup(
            executable,
            credential_status_loader=lambda: CredentialStatus.PRESENT,
            preflight_runner=lambda *_args, failed=component: _report(failed),
            product_runner=lambda *_args: 0,
            show_dialog=lambda _title, message, sink=messages: sink.append(message),
        )
        observed.append((component, " ".join(messages), result))

    assert [(component, result) for component, _message, result in observed] == [
        ("config", ProductStartupExitCode.CONFIGURATION_INVALID),
        ("secret.nim", ProductStartupExitCode.CREDENTIAL_INVALID),
        ("doctor", ProductStartupExitCode.COMPONENTS_INVALID),
    ]
    assert all(phrase in message for (_component, message, _result), (_c, phrase, _e) in zip(
        observed,
        cases,
        strict=True,
    ))


def test_success_passes_exact_installed_paths_and_shows_no_dialog(tmp_path: Path) -> None:
    executable = _installed_executable(tmp_path)
    observed: list[tuple[Path, Path]] = []

    result = run_windowed_product_startup(
        executable,
        credential_status_loader=lambda: CredentialStatus.PRESENT,
        preflight_runner=lambda *_args: _report(),
        product_runner=lambda root, config: observed.append((root, config)) or 0,
        show_dialog=lambda *_args: (_ for _ in ()).throw(AssertionError("unexpected dialog")),
    )

    assert result == ProductStartupExitCode.OK
    assert observed == [
        (tmp_path.resolve(), (tmp_path / "config" / "product_host.json").resolve())
    ]


def test_product_exception_and_nonzero_result_are_redacted(tmp_path: Path) -> None:
    executable = _installed_executable(tmp_path)
    messages: list[str] = []

    def fail(*_args: Path) -> int:
        raise RuntimeError("private path and key")

    failed = run_windowed_product_startup(
        executable,
        credential_status_loader=lambda: CredentialStatus.PRESENT,
        preflight_runner=lambda *_args: _report(),
        product_runner=fail,
        show_dialog=lambda _title, message: messages.append(message),
    )
    nonzero = run_windowed_product_startup(
        executable,
        credential_status_loader=lambda: CredentialStatus.PRESENT,
        preflight_runner=lambda *_args: _report(),
        product_runner=lambda *_args: 7,
        show_dialog=lambda _title, message: messages.append(message),
    )

    assert failed == ProductStartupExitCode.STARTUP_FAILED
    assert nonzero == ProductStartupExitCode.STARTUP_FAILED
    assert "private" not in " ".join(messages)


def test_missing_installation_and_dialog_failure_still_return_stable_code(
    tmp_path: Path,
) -> None:
    result = run_windowed_product_startup(
        tmp_path / "missing.exe",
        credential_status_loader=lambda: CredentialStatus.PRESENT,
        preflight_runner=lambda *_args: _report(),
        product_runner=lambda *_args: 0,
        show_dialog=lambda *_args: (_ for _ in ()).throw(RuntimeError("dialog failed")),
    )

    assert result == ProductStartupExitCode.CONFIGURATION_INVALID
