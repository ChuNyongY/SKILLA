from __future__ import annotations

import json
from enum import StrEnum
from typing import Protocol

from .approval_broker import ApprovalChannel, ApprovalRequest, ApprovalResponse
from .models import FrozenModel


class ApprovalView(FrozenModel):
    title: str
    capability: str
    purpose: str
    target: str
    risk: str
    arguments_json: str
    strong_auth_notice: str
    request_reference: str


class ApprovalDialogBackend(Protocol):
    def show(self, view: ApprovalView, timeout_seconds: int) -> bool: ...


class LocalApprovalPresenter:
    """Turn a local modal dialog result into a request-bound approval response."""

    def __init__(self, backend: ApprovalDialogBackend, *, timeout_seconds: int = 60) -> None:
        if timeout_seconds <= 0:
            raise ValueError("approval timeout must be positive")
        self._backend = backend
        self._timeout_seconds = timeout_seconds

    def request(self, approval: ApprovalRequest) -> ApprovalResponse:
        view = self._build_view(approval)
        try:
            approved = self._backend.show(view, self._timeout_seconds)
        except Exception:
            approved = False
        return ApprovalResponse(
            request_id=approval.request_id,
            approved=approved,
            channel=ApprovalChannel.LOCAL_UI,
        )

    @staticmethod
    def _build_view(approval: ApprovalRequest) -> ApprovalView:
        return ApprovalView(
            title="SKILLA 작업 승인",
            capability=approval.capability_id,
            purpose=approval.purpose,
            target=approval.target_identity or "(지정되지 않음)",
            risk=approval.risk.name,
            arguments_json=json.dumps(
                approval.arguments,
                sort_keys=True,
                indent=2,
                ensure_ascii=False,
            ),
            strong_auth_notice=(
                "승인 후 Windows 보안 인증이 추가로 필요합니다."
                if approval.strong_auth_required
                else "추가 Windows 보안 인증은 필요하지 않습니다."
            ),
            request_reference=str(approval.request_id),
        )


class TkApprovalDialog:
    """A stdlib-only local dialog. It never collects a password or PIN."""

    def show(self, view: ApprovalView, timeout_seconds: int) -> bool:
        import tkinter as tk
        from tkinter import scrolledtext

        from . import control_theme as theme

        approved = False
        root = tk.Tk()
        root.title(view.title)
        root.geometry("740x620")
        root.minsize(680, 560)
        root.configure(bg=theme.BACKGROUND)
        root.attributes("-topmost", True)
        timeout_id: str | None = None

        def finish(value: bool) -> None:
            nonlocal approved
            approved = value
            if timeout_id is not None:
                root.after_cancel(timeout_id)
            root.destroy()

        root.protocol("WM_DELETE_WINDOW", lambda: finish(False))
        root.bind("<Escape>", lambda _event: finish(False))
        frame = tk.Frame(root, bg=theme.BACKGROUND, padx=22, pady=18)
        frame.pack(fill="both", expand=True)
        theme.heading(frame, "작업 승인", "대상과 실행 내용을 확인한 뒤 승인하거나 취소하세요.")
        buttons = tk.Frame(frame, bg=theme.BACKGROUND)
        buttons.pack(fill="x", side="bottom", pady=(12, 0))
        cancel = theme.button(buttons, "취소", lambda: finish(False))
        cancel.pack(side="right")
        theme.button(buttons, "승인하고 계속", lambda: finish(True), primary=True).pack(
            side="right", padx=(0, 8),
        )
        tk.Label(
            buttons, text=f"{timeout_seconds}초 안에 선택하지 않으면 자동 취소",
            bg=theme.BACKGROUND, fg=theme.MUTED, font=theme.FONT,
        ).pack(side="left")
        tk.Label(
            frame, text=view.strong_auth_notice, bg=theme.BACKGROUND,
            fg=theme.WARNING, font=theme.FONT, anchor="w",
        ).pack(fill="x", side="bottom", pady=(10, 0))
        card = tk.Frame(frame, bg=theme.PANEL, padx=14, pady=12)
        card.pack(fill="both", expand=True)
        tk.Label(card, text="실행 내용", bg=theme.PANEL, fg=theme.ACCENT,
                 font=("맑은 고딕", 14, "bold")).pack(anchor="w", pady=(0, 8))
        arguments = scrolledtext.ScrolledText(
            card, height=8, wrap="word", bg=theme.FIELD, fg=theme.TEXT,
            font=theme.FONT, relief="flat", padx=10, pady=8,
        )
        arguments.pack(fill="both", expand=True)
        arguments.insert("1.0", (
            f"작업 목적\n{view.purpose}\n\n작업 대상\n{view.target}\n\n"
            f"위험도  {view.risk}\n기능  {view.capability}\n\n"
            f"실행 설정\n{view.arguments_json}\n\n요청 번호  {view.request_reference}"
        ))
        arguments.configure(state="disabled")
        root.lift()
        root.focus_force()
        cancel.focus_set()
        root.grab_set()
        timeout_id = root.after(timeout_seconds * 1000, lambda: finish(False))
        root.mainloop()
        return approved


class ConsentResult(StrEnum):
    VERIFIED = "VERIFIED"
    CANCELED = "CANCELED"
    UNAVAILABLE = "UNAVAILABLE"
    FAILED = "FAILED"


class OsConsentVerifier(Protocol):
    """Adapter boundary for an OS-owned authentication prompt."""

    def request_verification(self, message: str) -> ConsentResult: ...


class OsBackedStrongAuthenticator:
    """Fail-closed R4 authenticator that never receives user credentials."""

    def __init__(self, verifier: OsConsentVerifier) -> None:
        self._verifier = verifier

    def verify(self, approval: ApprovalRequest, response: ApprovalResponse) -> bool:
        if (
            response.request_id != approval.request_id
            or not response.approved
            or response.channel is not ApprovalChannel.LOCAL_UI
        ):
            return False
        message = (
            f"SKILLA {approval.capability_id} 승인 | "
            f"대상: {approval.target_identity or '(없음)'} | "
            f"요청: {approval.request_id} | 인자 해시: {approval.arguments_hash}"
        )
        try:
            return self._verifier.request_verification(message) is ConsentResult.VERIFIED
        except Exception:
            return False
