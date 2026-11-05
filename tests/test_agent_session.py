from __future__ import annotations

from collections.abc import Iterable, Mapping

from skilla_core import (
    Action,
    ApprovalTokenService,
    AudioFrame,
    CancellationToken,
    InMemoryAuditSink,
    IntentClass,
    IntentEvidence,
    MockExecutor,
    Orchestrator,
    Plan,
    PolicyContext,
    PolicyEngine,
    Postcondition,
    PredicateVerifier,
    VoiceCommandCoordinator,
    VoicePipeline,
    default_registry,
)
from skilla_core.agent_session import AgentSession, AgentSessionStatus
from skilla_core.intent import InputSource
from skilla_core.voice_feedback import VoiceFeedbackPresenter

FRAME = AudioFrame(pcm_s16le=b"\0\0" * 80)


class FrameSource:
    def __init__(self, frames: tuple[AudioFrame, ...], *, fail: bool = False) -> None:
        self._frames = frames
        self._fail = fail
        self.closed = False

    def frames(
        self,
        cancellation: CancellationToken,
        *,
        max_frames: int,
    ) -> Iterable[AudioFrame]:
        try:
            if self._fail:
                raise RuntimeError("private audio detail")
            yield from self._frames[:max_frames]
        finally:
            self.closed = True


class CloseFailingIterator:
    def __iter__(self) -> CloseFailingIterator:
        return self

    def __next__(self) -> AudioFrame:
        raise StopIteration

    def close(self) -> None:
        raise RuntimeError("private cleanup detail")


class CloseFailingSource:
    def frames(
        self,
        cancellation: CancellationToken,
        *,
        max_frames: int,
    ) -> Iterable[AudioFrame]:
        return CloseFailingIterator()


class Wake:
    def score(self, frame: AudioFrame) -> float:
        return 1.0


class Vad:
    def __init__(self) -> None:
        self.calls = 0

    def is_speech(self, frame: AudioFrame) -> bool:
        self.calls += 1
        return self.calls == 1


class Stt:
    def transcribe(self, frames: tuple[AudioFrame, ...]) -> str:
        return "스킬라 시스템 정보 확인"


class Classifier:
    def classify(
        self,
        transcript: str,
        *,
        wake_confidence: float,
        explicit_wake_word: bool,
        source: InputSource = "MIC",
    ) -> IntentEvidence:
        return IntentEvidence(
            transcript=transcript,
            wake_confidence=wake_confidence,
            addressed_confidence=0.99,
            intent_confidence=0.99,
            target_confidence=0.99,
            intent_class=IntentClass.COMMAND,
            explicit_wake_word=explicit_wake_word,
            source=source,
        )


class Planner:
    def __init__(self) -> None:
        self.contexts: list[Mapping[str, object] | None] = []

    def plan(
        self,
        goal: str,
        *,
        trusted_context: Mapping[str, object] | None = None,
        untrusted_context: str | None = None,
    ) -> Plan:
        self.contexts.append(trusted_context)
        return Plan(
            goal=goal,
            steps=(
                Action(
                    capability_id="system.info.read",
                    purpose="read system info",
                    expected_postconditions=(
                        Postcondition(predicate="execution.success"),
                    ),
                ),
            ),
        )


class SpeechSink:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.messages: list[str] = []

    def speak(
        self,
        text: str,
        *,
        rate: int = 0,
        volume: int = 100,
        cancellation: CancellationToken | None = None,
    ) -> None:
        if self.fail:
            raise RuntimeError("private speaker detail")
        self.messages.append(text)


class TraceObserver:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.observed: list[tuple[Plan, object]] = []

    def observe(self, plan: Plan, outcome: object) -> None:
        if self.fail:
            raise RuntimeError("private trace detail")
        self.observed.append((plan, outcome))


class UseObserver:
    def __init__(self, *, selected: bool = True, fail: bool = False) -> None:
        self.selected = selected
        self.fail = fail
        self.elapsed: list[int] = []

    def observe(self, plan: Plan, outcome: object, *, elapsed_ms: int) -> bool:
        del plan, outcome
        self.elapsed.append(elapsed_ms)
        if self.fail:
            raise RuntimeError("private skill use detail")
        return self.selected


def build_session(
    source: FrameSource,
    *,
    sink: SpeechSink | None = None,
    context_provider: object | None = None,
    trace_observer: TraceObserver | None = None,
    use_observer: UseObserver | None = None,
) -> tuple[AgentSession, Planner, MockExecutor]:
    planner = Planner()
    executor = MockExecutor({"system.info.read": lambda _action: {}})

    def coordinator_factory(token: CancellationToken) -> VoiceCommandCoordinator:
        return VoiceCommandCoordinator(Classifier(), planner, token)

    def orchestrator_factory(token: CancellationToken) -> Orchestrator:
        return Orchestrator(
            policy=PolicyEngine(default_registry()),
            executor=executor,
            verifier=PredicateVerifier(),
            audit=InMemoryAuditSink(),
            approvals=ApprovalTokenService(b"s" * 32),
            cancellation=token,
        )

    planner_context = (
        context_provider
        if callable(context_provider)
        else lambda: {"foreground_app_id": "notepad"}
    )
    return (
        AgentSession(
            frame_source=source,
            voice_pipeline=VoicePipeline(
                Wake(), Vad(), Stt(), end_silence_frames=1, max_capture_frames=10
            ),
            coordinator_factory=coordinator_factory,
            orchestrator_factory=orchestrator_factory,
            policy_context_provider=lambda _action: PolicyContext(
                addressed_confidence=0.99,
                intent_confidence=0.99,
                target_confidence=0.99,
                target_matches_plan=True,
            ),
            planner_context_provider=planner_context,
            feedback=VoiceFeedbackPresenter(sink) if sink is not None else None,
            skill_trace_observer=trace_observer,  # type: ignore[arg-type]
            skill_use_observer=use_observer,  # type: ignore[arg-type]
        ),
        planner,
        executor,
    )


def test_run_once_connects_frames_to_verified_task_and_fixed_feedback() -> None:
    source = FrameSource((FRAME, FRAME))
    sink = SpeechSink()
    session, planner, executor = build_session(source, sink=sink)

    result = session.run_once(max_frames=10)

    assert result.status is AgentSessionStatus.COMPLETED
    assert result.reason == "ALL_ACTIONS_VERIFIED"
    assert result.completed_actions == 1
    assert result.feedback_delivered is True
    assert source.closed
    assert planner.contexts == [{"foreground_app_id": "notepad"}]
    assert len(executor.calls) == 1
    assert sink.messages == ["작업을 마쳤고, 결과도 확인했어요."]
    assert "스킬라 시스템 정보 확인" not in result.model_dump_json()


def test_verified_outcome_is_offered_to_optional_skill_trace_observer() -> None:
    observer = TraceObserver()
    session, _planner, _executor = build_session(
        FrameSource((FRAME, FRAME)), trace_observer=observer
    )
    result = session.run_once()
    assert result.skill_trace_recorded is True
    assert len(observer.observed) == 1

    failing = TraceObserver(fail=True)
    session, _planner, _executor = build_session(
        FrameSource((FRAME, FRAME)), trace_observer=failing
    )
    result = session.run_once()
    assert result.status is AgentSessionStatus.COMPLETED
    assert result.skill_trace_recorded is False
    assert "private" not in result.model_dump_json()


def test_verified_outcome_is_offered_to_optional_skill_use_observer() -> None:
    observer = UseObserver()
    session, _planner, _executor = build_session(
        FrameSource((FRAME, FRAME)), use_observer=observer
    )
    result = session.run_once()
    assert result.skill_use_recorded is True
    assert observer.elapsed and observer.elapsed[0] >= 0

    failing = UseObserver(fail=True)
    session, _planner, _executor = build_session(
        FrameSource((FRAME, FRAME)), use_observer=failing
    )
    result = session.run_once()
    assert result.status is AgentSessionStatus.COMPLETED
    assert result.skill_use_recorded is False
    assert "private" not in result.model_dump_json()


def test_no_complete_utterance_and_capture_failure_close_source() -> None:
    empty = FrameSource(())
    session, _planner, _executor = build_session(empty)
    assert session.run_once().status is AgentSessionStatus.NO_UTTERANCE
    assert empty.closed

    failed = FrameSource((), fail=True)
    session, _planner, _executor = build_session(failed)
    result = session.run_once()
    assert result.status is AgentSessionStatus.FAILED
    assert result.reason == "AUDIO_CAPTURE_FAILED"
    assert "private" not in result.model_dump_json()
    assert failed.closed


def test_context_and_feedback_failures_are_redacted_and_fail_safe() -> None:
    source = FrameSource((FRAME, FRAME))

    def fail_context() -> Mapping[str, object]:
        raise RuntimeError("private context detail")

    session, _planner, executor = build_session(source, context_provider=fail_context)
    result = session.run_once()
    assert result.reason == "CONTEXT_COLLECTION_FAILED"
    assert executor.calls == ()

    source = FrameSource((FRAME, FRAME))
    session, _planner, executor = build_session(source, sink=SpeechSink(fail=True))
    result = session.run_once()
    assert result.status is AgentSessionStatus.COMPLETED
    assert result.feedback_delivered is False
    assert len(executor.calls) == 1

    session, _planner, executor = build_session(CloseFailingSource())  # type: ignore[arg-type]
    result = session.run_once()
    assert result.reason == "AUDIO_CAPTURE_CLEANUP_FAILED"
    assert "private" not in result.model_dump_json()
    assert executor.calls == ()


def test_max_frames_is_strict_and_bounded() -> None:
    session, _planner, _executor = build_session(FrameSource(()))
    for invalid in (0, 1_501, True):
        try:
            session.run_once(max_frames=invalid)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid max_frames was accepted")
