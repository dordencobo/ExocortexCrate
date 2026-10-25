param(
    [Parameter(Mandatory = $true)][string]$Plugin,
    [string]$MayaRoot = 'C:/Program Files/Autodesk/Maya2024'
)
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$pluginPath = (Resolve-Path -LiteralPath $Plugin).Path
$mayapy = Join-Path $MayaRoot 'bin/mayapy.exe'
if (-not (Test-Path -LiteralPath $mayapy)) { throw "Missing mayapy: $mayapy" }
$logRoot = Join-Path $repoRoot 'build/maya2024/test-results'
New-Item -ItemType Directory -Force -Path $logRoot | Out-Null
$previousProfile = $env:MAYA_APP_DIR
Push-Location $repoRoot
try {
    $env:MAYA_APP_DIR = Join-Path $repoRoot 'build/maya2024/test-profile'
    foreach ($test in @('python3_package', 'plugin_load', 'export_duplicate_names',
                        'animated_mesh', 'feature_roundtrip', 'viewport2')) {
        $arguments = @('-B', "tests/maya/test_$test.py")
        if ($test -ne 'python3_package') { $arguments += @('--plugin', $pluginPath) }
        $log = Join-Path $logRoot "$test.log"
        & $mayapy @arguments > $log 2>&1
        if ($LASTEXITCODE -ne 0) { throw "Failed: $test. See $log" }
        Write-Output "$test : PASS"
        Select-String -LiteralPath $log -Pattern '^Ran .* tests? in ' |
            ForEach-Object { Write-Output $_.Line }
    }
} finally {
    $env:MAYA_APP_DIR = $previousProfile
    Pop-Location
}
