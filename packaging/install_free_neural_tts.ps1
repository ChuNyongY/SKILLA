param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path -LiteralPath $ProjectRoot).Path
$basePython = Join-Path $root ".venv\Scripts\python.exe"
$voicePython = Join-Path $root ".venv-edge-tts\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $basePython -PathType Leaf)) {
    throw "SKILLA 기본 가상환경이 없습니다: $basePython"
}
if (-not (Test-Path -LiteralPath $voicePython -PathType Leaf)) {
    & $basePython -m venv (Join-Path $root ".venv-edge-tts")
}
& $voicePython -m pip install --disable-pip-version-check "edge-tts==7.3.1"
if ($LASTEXITCODE -ne 0) {
    throw "무료 신경망 음성 설치에 실패했습니다."
}
if (-not (Get-Command ffmpeg.exe -ErrorAction SilentlyContinue)) {
    throw "ffmpeg가 필요합니다. Windows 패키지 관리자에서 Gyan.FFmpeg를 설치한 뒤 다시 실행하세요."
}

Write-Host "무료 한국어 신경망 음성 설치 완료: ko-KR-SunHiNeural"
