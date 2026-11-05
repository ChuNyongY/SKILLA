from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .audit import AuditRetentionPolicy, JsonlAuditSink
from .display_target import DisplayTargetController, build_windows_display_controller
from .local_approval import LocalApprovalPresenter, OsBackedStrongAuthenticator, TkApprovalDialog
from .natural_tts import FallbackSpeechSink
from .planner import NimChatTransport
from .product_composition import (
    ProductCapabilityStack,
    ProductLanguageStack,
    ProductRuntimeStack,
    ProductVoiceStack,
    build_product_language_stack,
    build_product_runtime_stack_from_capabilities,
    build_product_voice_stack,
)
from .product_context import build_windows_planner_context_provider
from .product_host import (
    LoadedProductHostConfig,
    ProductHostError,
    ProductHostLifecycle,
    ProductPreflightReport,
    SecretLoader,
    load_nim_api_key,
    load_product_host_config,
    run_product_preflight,
    run_product_preflight_with_secret_loader,
)
from .product_policy import build_windows_policy_context_provider
from .product_state import prepare_product_state_directory
from .product_windows import build_windows_product_capabilities
from .skill_authoring import SkillDraftAuthor
from .skill_draft_workflow import InitialSkillDraftWorkflow
from .skill_runtime import LocalSkillCatalog, SkillAwarePlanner
from .skill_session import SkillSession
from .skill_trace_store import LocalSkillTraceStore
from .skill_use_recording import (
    CatalogSkillUseRecorder,
    product_model_configuration_sha256,
    product_tool_surface_sha256,
)
from .supertonic_tts import SupertonicTtsRunner
from .tts_ipc import TtsWorkerRunner
from .voice_feedback import VoiceFeedbackPresenter
from .windows_hello import load_windows_hello_verifier


@dataclass(frozen=True)
class WindowsProductService:
    configuration: LoadedProductHostConfig
    preflight: ProductPreflightReport
    capabilities: ProductCapabilityStack
    skills: LocalSkillCatalog
    skill_traces: LocalSkillTraceStore
    skill_draft_workflow: InitialSkillDraftWorkflow
    display: DisplayTargetController
    voice: ProductVoiceStack
    language: ProductLanguageStack
    runtime: ProductRuntimeStack
    audit: JsonlAuditSink
    lifecycle: ProductHostLifecycle


def build_windows_product_service(
    project_root: Path,
    config_path: Path,
    secret_path: Path,
) -> WindowsProductService:
    """Build the complete local service after preflight, without opening the microphone."""
    preflight = run_product_preflight(project_root, config_path, secret_path)
    return _build_windows_product_service(
        project_root,
        config_path,
        lambda: load_nim_api_key(secret_path),
        preflight,
    )


def build_windows_product_service_with_secret_loader(
    project_root: Path,
    config_path: Path,
    secret_loader: SecretLoader,
) -> WindowsProductService:
    """Build the complete local service using a non-file secret provider."""
    preflight = run_product_preflight_with_secret_loader(
        project_root,
        config_path,
        secret_loader,
    )
    return _build_windows_product_service(
        project_root,
        config_path,
        secret_loader,
        preflight,
    )


def _build_windows_product_service(
    project_root: Path,
    config_path: Path,
    secret_loader: SecretLoader,
    preflight: ProductPreflightReport,
) -> WindowsProductService:
    if not preflight.ready:
        raise ProductHostError("product service preflight failed")
    root = project_root.resolve(strict=True)
    configuration = load_product_host_config(config_path, root)
    api_key = secret_loader()
    state_directory = prepare_product_state_directory(root)
    display = build_windows_display_controller(state_directory)
    display.ensure_selection()
    capabilities = build_windows_product_capabilities(
        configuration,
        root,
        state_directory=state_directory,
    )
    skills = LocalSkillCatalog(state_directory / "skills.sqlite3", capabilities.registry)
    skill_traces = LocalSkillTraceStore(state_directory / "skill-traces.sqlite3")
    skill_draft_workflow = InitialSkillDraftWorkflow(
        trace_store=skill_traces,
        author=SkillDraftAuthor(
            NimChatTransport(api_key, model=configuration.settings.nim_model),
            skills,
        ),
        catalog=skills,
    )
    language = build_product_language_stack(
        configuration,
        api_key,
        registry=capabilities.registry,
        skill_catalog=skills,
    )
    language_planner = getattr(language, "planner", None)
    skill_use_recorder = (
        CatalogSkillUseRecorder(
            skills,
            language_planner,
            model_configuration_sha256=product_model_configuration_sha256(
                configuration.settings.nim_model
            ),
            tool_surface_sha256=product_tool_surface_sha256(capabilities.registry),
        )
        if isinstance(language_planner, SkillAwarePlanner)
        else None
    )
    voice = build_product_voice_stack(configuration)
    audit = JsonlAuditSink(
        state_directory / "audit.jsonl",
        AuditRetentionPolicy(),
    )
    approval_presenter = LocalApprovalPresenter(TkApprovalDialog())
    strong_authenticator = OsBackedStrongAuthenticator(
        load_windows_hello_verifier(configuration.hello_manifest, root)
    )
    policy_context_provider = build_windows_policy_context_provider(
        (root,),
        {"workspace": root},
        configuration.settings.browser_allowed_hosts,
        ("personal",),
    )
    planner_context_provider = build_windows_planner_context_provider(configuration)
    feedback = VoiceFeedbackPresenter(
        FallbackSpeechSink(
            SupertonicTtsRunner(root, state_directory),
            TtsWorkerRunner(state_directory),
        )
    )
    runtime = build_product_runtime_stack_from_capabilities(
        voice,
        language,
        capabilities,
        audit=audit,
        approval_presenter=approval_presenter,
        strong_authenticator=strong_authenticator,
        policy_context_provider=policy_context_provider,
        planner_context_provider=planner_context_provider,
        feedback=feedback,
        skill_trace_observer=skill_traces,
        skill_use_observer=skill_use_recorder,
        skill_session=SkillSession(
            skills, language_planner, capabilities.registry,
            SkillDraftAuthor(
                NimChatTransport(api_key, model=configuration.settings.nim_model), skills,
            ).propose_from_plan,
        ) if isinstance(language_planner, SkillAwarePlanner) else None,
    )
    lifecycle = ProductHostLifecycle(
        preflight=lambda: preflight,
        run_capture=runtime.capture_pump.run,
        request_capture_stop=runtime.capture_pump.request_stop,
        request_runtime_stop=runtime.runtime.close,
    )
    return WindowsProductService(
        configuration=configuration,
        preflight=preflight,
        capabilities=capabilities,
        skills=skills,
        skill_traces=skill_traces,
        skill_draft_workflow=skill_draft_workflow,
        display=display,
        voice=voice,
        language=language,
        runtime=runtime,
        audit=audit,
        lifecycle=lifecycle,
    )
