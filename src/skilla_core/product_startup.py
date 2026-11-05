from __future__ import annotations

import ctypes
from collections.abc import Callable
from contextlib import suppress
from enum import IntEnum, StrEnum
from pathlib import Path

from pydantic import SecretStr

from .credential_store import (
    CredentialStatus,
    provision_nim_credential,
)
from .product_host import ProductPreflightReport, ProductPreflightStatus


class ProductStartupExitCode(IntEnum):
    OK = 0
    CREDENTIAL_MISSING = 10
    CREDENTIAL_INVALID = 11
    CONFIGURATION_INVALID = 20
    COMPONENTS_INVALID = 21
    STARTUP_FAILED = 30


class CredentialSetupResult(StrEnum):
    SAVED = "SAVED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


_MESSAGES = {
    ProductStartupExitCode.CREDENTIAL_MISSING: (
        "NVIDIA NIM API 키가 등록되어 있지 않습니다. 설치 폴더의 사용 설명서에 따라 "
        "API 키를 등록한 뒤 다시 실행해 주세요."
    ),
    ProductStartupExitCode.CREDENTIAL_INVALID: (
        "저장된 NVIDIA NIM API 키를 읽거나 확인할 수 없습니다. 설치 폴더의 사용 설명서에 "
        "따라 API 키를 다시 등록해 주세요."
    ),
    ProductStartupExitCode.CONFIGURATION_INVALID: (
        "프로그램 구성 파일이 없거나 손상되었습니다. SKILLA를 다시 설치해 주세요."
    ),
    ProductStartupExitCode.COMPONENTS_INVALID: (
        "필수 구성 요소 확인에 실패했습니다. SKILLA를 다시 설치하거나 사용 설명서의 "
        "진단 절차를 실행해 주세요."
    ),
    ProductStartupExitCode.STARTUP_FAILED: (
        "SKILLA를 시작하지 못했습니다. 프로그램을 다시 실행하고, 문제가 계속되면 "
        "사용 설명서의 진단 절차를 실행해 주세요."
    ),
}

CredentialStatusLoader = Callable[[], CredentialStatus]
CredentialSetup = Callable[[], CredentialSetupResult]
CredentialProvisioner = Callable[[SecretStr], None]
PreflightRunner = Callable[[Path, Path], ProductPreflightReport]
ProductRunner = Callable[[Path, Path], int]
StartupDialog = Callable[[str, str], None]


def run_windowed_product_startup(
    executable: Path,
    *,
    credential_status_loader: CredentialStatusLoader,
    preflight_runner: PreflightRunner,
    product_runner: ProductRunner,
    show_dialog: StartupDialog | None = None,
    credential_setup: CredentialSetup | None = None,
) -> int:
    """Start the installed windowed product or show only a fixed, non-sensitive error."""
    dialog = show_dialog or show_native_startup_error
    try:
        root = executable.resolve(strict=True).parent
        config = (root / "config" / "product_host.json").resolve(strict=True)
    except (OSError, RuntimeError):
        return _fail(ProductStartupExitCode.CONFIGURATION_INVALID, dialog)

    try:
        credential_status = credential_status_loader()
    except Exception:
        return _fail(ProductStartupExitCode.CREDENTIAL_INVALID, dialog)
    if credential_status is not CredentialStatus.PRESENT:
        if credential_setup is None:
            return _fail(ProductStartupExitCode.CREDENTIAL_MISSING, dialog)
        try:
            setup_result = credential_setup()
        except Exception:
            return _fail(ProductStartupExitCode.CREDENTIAL_INVALID, dialog)
        if setup_result is CredentialSetupResult.CANCELLED:
            return int(ProductStartupExitCode.CREDENTIAL_MISSING)
        if setup_result is not CredentialSetupResult.SAVED:
            return int(ProductStartupExitCode.CREDENTIAL_INVALID)
        try:
            credential_status = credential_status_loader()
        except Exception:
            return _fail(ProductStartupExitCode.CREDENTIAL_INVALID, dialog)
        if credential_status is not CredentialStatus.PRESENT:
            return _fail(ProductStartupExitCode.CREDENTIAL_INVALID, dialog)

    try:
        preflight = preflight_runner(root, config)
    except Exception:
        return _fail(ProductStartupExitCode.STARTUP_FAILED, dialog)
    if not preflight.ready:
        failed_components = {
            item.component
            for item in preflight.items
            if item.status is ProductPreflightStatus.FAIL
        }
        if "secret.nim" in failed_components:
            return _fail(ProductStartupExitCode.CREDENTIAL_INVALID, dialog)
        if "config" in failed_components:
            return _fail(ProductStartupExitCode.CONFIGURATION_INVALID, dialog)
        return _fail(ProductStartupExitCode.COMPONENTS_INVALID, dialog)

    try:
        result = product_runner(root, config)
    except Exception:
        return _fail(ProductStartupExitCode.STARTUP_FAILED, dialog)
    if isinstance(result, bool) or not isinstance(result, int) or result != 0:
        return _fail(ProductStartupExitCode.STARTUP_FAILED, dialog)
    return int(ProductStartupExitCode.OK)


def save_nim_credential_for_startup(
    raw_key: str,
    *,
    provisioner: CredentialProvisioner = provision_nim_credential,
) -> CredentialSetupResult:
    """Validate and store a first-run key without exposing failure details."""
    try:
        provisioner(SecretStr(raw_key))
    except Exception:
        return CredentialSetupResult.FAILED
    return CredentialSetupResult.SAVED


def run_tk_nim_credential_setup(
    *,
    saver: Callable[[str], CredentialSetupResult] = save_nim_credential_for_startup,
) -> CredentialSetupResult:
    """Collect a NIM key in a masked first-run window and store it locally."""
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
    except Exception:
        with suppress(Exception):
            show_native_startup_error(
                "SKILLA 초기 설정 오류",
                "초기 설정 화면을 열 수 없습니다. SKILLA를 다시 설치하거나 사용 설명서의 "
                "API 키 등록 절차를 이용해 주세요.",
            )
        return CredentialSetupResult.FAILED

    result = CredentialSetupResult.CANCELLED
    value = tk.StringVar(master=root)

    def cancel() -> None:
        nonlocal result
        value.set("")
        result = CredentialSetupResult.CANCELLED
        root.destroy()

    def save() -> None:
        nonlocal result
        raw_key = value.get()
        value.set("")
        entry.delete(0, tk.END)
        saved = saver(raw_key)
        raw_key = ""
        if saved is CredentialSetupResult.SAVED:
            result = saved
            root.destroy()
            return
        messagebox.showerror(
            "SKILLA 초기 설정 오류",
            "API 키 형식을 확인하거나 Windows 자격 증명 관리자 저장 상태를 확인해 주세요.",
            parent=root,
        )
        entry.focus_set()

    try:
        root.title("SKILLA 초기 설정")
        root.geometry("520x230")
        root.resizable(False, False)
        root.protocol("WM_DELETE_WINDOW", cancel)

        frame = tk.Frame(root, padx=24, pady=20)
        frame.pack(fill="both", expand=True)
        tk.Label(
            frame,
            text="NVIDIA NIM API 키 등록",
            font=("Malgun Gothic", 14, "bold"),
        ).pack(anchor="w")
        tk.Label(
            frame,
            text=(
                "API 키는 Windows 자격 증명 관리자에 안전하게 저장되며 "
                "화면이나 로그에 표시되지 않습니다."
            ),
            font=("Malgun Gothic", 9),
            justify="left",
            wraplength=465,
        ).pack(anchor="w", pady=(8, 12))
        entry = tk.Entry(frame, textvariable=value, show="*", font=("Consolas", 11))
        entry.pack(fill="x")
        entry.focus_set()

        buttons = tk.Frame(frame)
        buttons.pack(fill="x", pady=(18, 0))
        tk.Button(buttons, text="취소", width=12, command=cancel).pack(side="right")
        tk.Button(buttons, text="저장하고 계속", width=16, command=save).pack(
            side="right", padx=(0, 8)
        )
        root.bind("<Return>", lambda _event: save())
        root.bind("<Escape>", lambda _event: cancel())
        root.mainloop()
    except Exception:
        value.set("")
        with suppress(Exception):
            root.destroy()
        with suppress(Exception):
            show_native_startup_error(
                "SKILLA 초기 설정 오류",
                "초기 설정을 완료하지 못했습니다. API 키 형식과 Windows 자격 증명 관리자 "
                "상태를 확인해 주세요.",
            )
        return CredentialSetupResult.FAILED
    return result


def show_native_startup_error(title: str, message: str) -> None:
    """Show a Windows error box without importing Tk or interpolating exception data."""
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    message_box = user32.MessageBoxW
    message_box.argtypes = [
        ctypes.c_void_p,
        ctypes.c_wchar_p,
        ctypes.c_wchar_p,
        ctypes.c_uint,
    ]
    message_box.restype = ctypes.c_int
    message_box(None, message, title, 0x00000010 | 0x00000000)


def _fail(code: ProductStartupExitCode, show_dialog: StartupDialog) -> int:
    with suppress(Exception):
        show_dialog("SKILLA 시작 오류", _MESSAGES[code])
    return int(code)
