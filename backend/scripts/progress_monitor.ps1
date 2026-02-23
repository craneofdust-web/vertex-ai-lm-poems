param(
    [string]$ProjectRoot = "",
    [string]$RunId = "",
    [int]$IntervalSec = 300,
    [switch]$Once,
    [switch]$ShowRawTail,
    [switch]$NoAutoStop,
    [int]$MaxLoops = 0
)

if (-not $ProjectRoot) {
    $ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
}

$runtimeRoot = Join-Path $ProjectRoot "runtime_workspaces"

function Get-RunPath {
    param([string]$Root, [string]$TargetRunId)
    if ($TargetRunId) {
        $candidate = Join-Path $Root $TargetRunId
        if (Test-Path $candidate) { return (Resolve-Path $candidate).Path }
        return $null
    }

    $dirs = Get-ChildItem -Path $Root -Directory -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending
    if (-not $dirs -or $dirs.Count -eq 0) { return $null }
    return $dirs[0].FullName
}

function Read-JsonFile {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return $null }
    try {
        return (Get-Content -Raw -Path $Path -ErrorAction Stop | ConvertFrom-Json)
    } catch {
        return $null
    }
}

function Tail-Lines {
    param([string]$Path, [int]$Count = 4)
    if (-not (Test-Path $Path)) { return @() }
    try {
        return @(Get-Content -Path $Path -Tail $Count -ErrorAction Stop)
    } catch {
        return @()
    }
}

function Detect-Phase {
    param([string]$RunName)
    $rows = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue
    if (-not $rows) { return @{ phase = "idle"; pid = ""; cmd = "" } }

    $matched = $rows | Where-Object { $_.CommandLine -and $_.CommandLine -like "*$RunName*" }
    if (-not $matched) {
        # Fallback for commands where run_id is not present in argv.
        $matched = $rows | Where-Object {
            $_.CommandLine -and (
                $_.CommandLine -like "*brainstorm_skill_webs.py*" -or
                $_.CommandLine -like "*build_master_and_fill_mounting.py*" -or
                $_.CommandLine -like "*generate_skill_tree_visualizations.py*"
            )
        }
    }
    if (-not $matched) { return @{ phase = "idle"; pid = ""; cmd = "" } }

    foreach ($row in $matched) {
        if ($row.CommandLine -like "*brainstorm_skill_webs.py*") {
            return @{ phase = "brainstorm"; pid = $row.ProcessId; cmd = $row.CommandLine }
        }
        if ($row.CommandLine -like "*build_master_and_fill_mounting.py*") {
            return @{ phase = "merge_fill"; pid = $row.ProcessId; cmd = $row.CommandLine }
        }
        if ($row.CommandLine -like "*generate_skill_tree_visualizations.py*") {
            return @{ phase = "visualize"; pid = $row.ProcessId; cmd = $row.CommandLine }
        }
    }

    $first = $matched | Select-Object -First 1
    return @{ phase = "python_other"; pid = $first.ProcessId; cmd = $first.CommandLine }
}

function Parse-FillProgress {
    param([string]$LogPath)
    if (-not (Test-Path $LogPath)) { return $null }
    try {
        $tail = Get-Content -Path $LogPath -Tail 400 -ErrorAction Stop
    } catch {
        return $null
    }
    $regex = [regex]"fill batch\s+(\d+)\/(\d+)"
    $best = $null
    foreach ($line in $tail) {
        $m = $regex.Match($line)
        if ($m.Success) {
            $best = @{
                current = [int]$m.Groups[1].Value
                total = [int]$m.Groups[2].Value
                raw = $line
            }
        }
    }
    return $best
}

$loopCount = 0
while ($true) {
    $loopCount += 1
    $runPath = Get-RunPath -Root $runtimeRoot -TargetRunId $RunId
    $now = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host ""
    Write-Host "[$now] Pipeline monitor"
    Write-Host ("project_root: " + $ProjectRoot)

    if (-not $runPath) {
        Write-Host "status: no runtime workspace found"
        if ($Once) { break }
        Start-Sleep -Seconds ([Math]::Max(5, $IntervalSec))
        continue
    }

    $runName = Split-Path -Leaf $runPath
    $request = Read-JsonFile -Path (Join-Path $runPath "pipeline_request.json")
    $logsDir = Join-Path $runPath "logs"
    $log1 = Join-Path $logsDir "01_brainstorm.log"
    $log2 = Join-Path $logsDir "02_merge_fill.log"
    $log3 = Join-Path $logsDir "03_visualize.log"
    $runDir = Join-Path $runPath ("runs\" + $runName)

    $phase = Detect-Phase -RunName $runName
    $fragments = @(Get-ChildItem -Path $runPath -Filter "skill_web_fragment_*.json" -File -ErrorAction SilentlyContinue)
    $fragCount = $fragments.Count
    $expectedIters = $null
    if ($request -and $request.iterations) { $expectedIters = [int]$request.iterations }
    $mode = if ($request -and $request.mode) { $request.mode } else { "unknown" }

    Write-Host ("run_id: " + $runName + " (" + $mode + ")")
    $phaseSuffix = ""
    if ($phase.pid) {
        $phaseSuffix = " (pid " + $phase.pid + ")"
    }
    Write-Host ("phase: " + $phase.phase + $phaseSuffix)

    if ($expectedIters) {
        $pct = if ($expectedIters -gt 0) { [Math]::Round(($fragCount * 100.0) / $expectedIters, 1) } else { 0 }
        Write-Host ("progress.fragment: " + $fragCount + "/" + $expectedIters + " (" + $pct + "%)")
    } else {
        Write-Host ("progress.fragment: " + $fragCount + "/?")
    }

    $fillProgress = Parse-FillProgress -LogPath $log2
    if ($fillProgress) {
        $fillPct = if ($fillProgress.total -gt 0) { [Math]::Round(($fillProgress.current * 100.0) / $fillProgress.total, 1) } else { 0 }
        Write-Host ("progress.fill_batch: " + $fillProgress.current + "/" + $fillProgress.total + " (" + $fillPct + "%)")
    } else {
        Write-Host "progress.fill_batch: n/a"
    }

    $hasMaster = Test-Path (Join-Path $runDir "master_skill_web.json")
    $hasFinal = Test-Path (Join-Path $runDir "poem_mounting_full.json")
    $hasViz = Test-Path (Join-Path $runDir "visualizations\\index.html")
    Write-Host ("artifacts.master: " + $hasMaster + ", full: " + $hasFinal + ", viz: " + $hasViz)

    $tailSource = if ($phase.phase -eq "brainstorm") {
        $log1
    } elseif ($phase.phase -eq "merge_fill") {
        $log2
    } elseif ($phase.phase -eq "visualize") {
        $log3
    } elseif (Test-Path $log3) {
        $log3
    } elseif (Test-Path $log2) {
        $log2
    } else {
        $log1
    }

    $tail = Tail-Lines -Path $tailSource -Count 3
    if ($ShowRawTail -and $tail -and $tail.Count -gt 0) {
        Write-Host "log.tail(raw):"
        foreach ($line in $tail) {
            Write-Host ("  " + $line)
        }
    } elseif ($tail -and $tail.Count -gt 0) {
        Write-Host "log.tail: hidden by default (use -ShowRawTail to display)"
    } else {
        Write-Host "log.tail: unavailable"
    }

    Write-Host "------------------------------------------------------------"

    $isDone = ($phase.phase -eq "idle" -and $hasMaster -and $hasFinal -and $hasViz)
    if ($isDone -and (-not $NoAutoStop)) {
        Write-Host "status: completed; auto-stop enabled, exiting monitor."
        break
    }

    if ($MaxLoops -gt 0 -and $loopCount -ge $MaxLoops) {
        Write-Host ("status: reached MaxLoops=" + $MaxLoops + ", exiting monitor.")
        break
    }

    if ($Once) { break }
    Start-Sleep -Seconds ([Math]::Max(5, $IntervalSec))
}
