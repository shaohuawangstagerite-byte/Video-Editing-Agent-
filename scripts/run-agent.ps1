param(
    [Parameter(Mandatory=$true)][string]$PromptFile,
    [string[]]$Files = @(),
    [string]$ModelConfig = (Join-Path ([Environment]::GetFolderPath('Desktop')) 'CAD/opencode.deepseek.json')
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$connection = Get-Content -LiteralPath $ModelConfig -Raw | ConvertFrom-Json
$gitBash = Join-Path (Split-Path -Parent (Split-Path -Parent (Get-Command git).Source)) 'bin/bash.exe'
$runtime = @{model=$connection.model; enabled_providers=$connection.enabled_providers; provider=$connection.provider; shell=$gitBash}
$previousConfig, $previousPath = $env:OPENCODE_CONFIG_CONTENT, $env:Path
try {
    $env:OPENCODE_CONFIG_CONTENT = $runtime | ConvertTo-Json -Depth 40 -Compress
    $env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')
    $prompt = Get-Content -LiteralPath $PromptFile -Raw
    $arguments = @('run', $prompt, '--agent', 'video-editor', '--dir', $projectRoot, '--format', 'json')
    foreach ($attachment in $Files) { $arguments += @('--file', [IO.Path]::GetFullPath($attachment)) }
    & opencode @arguments
    $runExitCode = $LASTEXITCODE
} finally {
    $env:OPENCODE_CONFIG_CONTENT, $env:Path = $previousConfig, $previousPath
}
exit $runExitCode
