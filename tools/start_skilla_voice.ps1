param([string]$PackageRoot)

$ErrorActionPreference = 'Stop'
$project = Split-Path -Parent $PSScriptRoot
$gpuRuntime = Join-Path $project 'build\voice-cuda-runtime\nvidia'
$gpuBins = @(
    Join-Path $gpuRuntime 'cublas\bin'
    Join-Path $gpuRuntime 'cudnn\bin'
) | Where-Object { Test-Path -LiteralPath $_ -PathType Container }
$originalPath = $env:Path

try {
    if ($gpuBins) {
        $env:Path = ($gpuBins -join ';') + ';' + $originalPath
    }
    if ($PackageRoot) {
        $runtimeRoot = (Resolve-Path -LiteralPath $PackageRoot).Path
        $entryPoint = Join-Path $runtimeRoot 'SKILLA.exe'
        $prefixArguments = @()
    } else {
        $runtimeRoot = $project
        $entryPoint = Join-Path $project '.venv\Scripts\python.exe'
        $prefixArguments = @('-m', 'skilla_core.cli')
    }
    & $entryPoint @prefixArguments run-product-host-credential $runtimeRoot (Join-Path $runtimeRoot 'config\product_host.json')
    exit $LASTEXITCODE
} finally {
    $env:Path = $originalPath
}
