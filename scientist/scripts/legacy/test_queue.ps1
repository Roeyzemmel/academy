<#
.SYNOPSIS
  End-to-end test of queue.ps1 + fsq.sh with WSL standing in for lingo. Touches no
  remote host and runs no experiment: the jobs are `sleep`.

.DESCRIPTION
  scripts\test_queue.ps1 -Work <empty scratch dir>

  Builds, under -Work: a stand-in laptop repo (copies of queue.ps1 and fsq.sh, a
  stub run.sh, a sleep job), a stand-in ~/FlatSurfLab, and a spool, with
  queue/config.json pointing at "wsl:Ubuntu". Then, with maxJobs 1:
    1. -Deploy -NoCron, -Resume
    2. -Add three jobs; the first -Tick's ssh drops BEFORE the remote acts
       (FSQ_FAULT=presubmit): all three must stay pending here
    3. the next -Tick's ssh drops AFTER the remote acts (FSQ_FAULT=submit), the
       2026-09-20 failure: all three must move to running here, not stay pending
    4. plain -Ticks until all are done: each job started exactly once, never two
       at a time, in queue-id order, results fetched, worktrees gone
#>
param([Parameter(Mandatory = $true)] [string] $Work, [string] $Distro = "Ubuntu")

$ErrorActionPreference = "Stop"
$src = $PSScriptRoot
if (Test-Path $Work) { Remove-Item -Recurse -Force $Work }
New-Item -ItemType Directory -Force $Work | Out-Null
$Work = (Resolve-Path $Work).Path
$lf = New-Object System.Text.UTF8Encoding $false
function WriteLF($path, $text) {
  New-Item -ItemType Directory -Force (Split-Path $path) | Out-Null
  [IO.File]::WriteAllText($path, ($text -replace "`r`n", "`n"), $lf)
}
function W2L($p) { (& wsl.exe -d $Distro -e wslpath -a ($p -replace '\\', '/')).Trim() }
function G { & git.exe @args; if ($LASTEXITCODE) { throw "git $args failed" } }
$pass = 0; $fail = 0
function Check($cond, $what) {
  if ($cond) { Write-Host "  PASS $what"; $script:pass++ } else { Write-Host "  FAIL $what"; $script:fail++ }
}

$laptop = Join-Path $Work "laptop"
$remote = Join-Path $Work "remote"
$spool = Join-Path $Work "fsq"
$trace = Join-Path $Work "trace.log"
$lRemote = W2L $remote; $lSpool = W2L $spool; $lTrace = W2L $trace

# --- the stand-in laptop repo ----------------------------------------------
New-Item -ItemType Directory -Force "$laptop\scripts", "$laptop\results", "$laptop\queue" | Out-Null
Copy-Item "$src\queue.ps1", "$src\fsq.sh" "$laptop\scripts\"
WriteLF "$laptop\.gitattributes" "*.sh text eol=lf`n"
WriteLF "$laptop\.gitignore" "queue/pending/`nqueue/running/`nqueue/done/`n"
WriteLF "$laptop\scripts\run.sh" "#!/usr/bin/env bash`ncd `"`$(dirname `"`${BASH_SOURCE[0]}`")/..`" && exec bash `"`$@`"`n"
$jobText = @'
#!/usr/bin/env bash
name=$1; secs=$2; stem=$(basename "$0" .sh)
echo "start $name $(date +%s.%N) head=$(git rev-parse --short HEAD)" >> "$FSQ_TEST_TRACE"
sleep "$secs"
mkdir -p results; echo "{\"name\":\"$name\"}" > "results/$stem.json"
echo "end $name $(date +%s.%N)" >> "$FSQ_TEST_TRACE"
'@
foreach ($n in "a", "b", "c") { WriteLF "$laptop\experiments\job_$n.sh" $jobText }
WriteLF "$laptop\results\.gitkeep" ""
Push-Location $laptop
try {
  G init -q .
  G config user.email test@example.invalid; G config user.name test; G config core.autocrlf false
  G add -A; G commit -qm "laptop c1"
} finally { Pop-Location }

# --- the stand-in ~/FlatSurfLab ---------------------------------------------
& wsl.exe -d $Distro -e bash -c "git init -q '$lRemote' && git -C '$lRemote' config receive.denyCurrentBranch ignore"
Push-Location $laptop
try { G push -q $remote "HEAD:refs/heads/laptop" } finally { Pop-Location }
& wsl.exe -d $Distro -e bash -c "git -C '$lRemote' checkout -q --detach laptop"

$cfg = [ordered]@{
  target = "wsl:$Distro"; remoteRepo = $lRemote; fsqHome = $lSpool; maxJobs = 1
  pushUrl = $remote; remoteEnv = "FSQ_LOCKDIR=/dev/shm/fsq-qtest FSQ_TEST_TRACE=$lTrace"
}
function SaveCfg($extraEnv) {
  $c = [pscustomobject]$cfg
  if ($extraEnv) { $c.remoteEnv = "$($cfg.remoteEnv) $extraEnv" }
  [IO.File]::WriteAllText("$laptop\queue\config.json", ($c | ConvertTo-Json) + "`n", $lf)
}
SaveCfg $null
& wsl.exe -d $Distro -e bash -c "rm -rf /dev/shm/fsq-qtest"

# WSL may stop a distro with no session attached; keep one open for the test.
$keep = Start-Process wsl.exe -ArgumentList "-d", $Distro, "-e", "sleep", "600" -WindowStyle Hidden -PassThru

$q = "$laptop\scripts\queue.ps1"
function QueueCmd {
  # Continue: the child's warnings arrive on stderr, which "Stop" would turn into a throw.
  $ErrorActionPreference = "Continue"
  & powershell -NoProfile -ExecutionPolicy Bypass -File $q @args 2>&1 | ForEach-Object { "    $_" } }
function Local($dir) { @(Get-ChildItem "$laptop\queue\$dir" -Filter *.json -ErrorAction SilentlyContinue).Count }

try {
  Push-Location $laptop
  Write-Host "== deploy"
  QueueCmd -Deploy -NoCron
  & wsl.exe -d $Distro -e test -x "$lSpool/bin/fsq"
  if ($LASTEXITCODE -ne 0) { throw "deploy failed; stopping" }
  QueueCmd -Resume

  Write-Host "== add three jobs (ids one second apart)"
  foreach ($n in "a", "b", "c") {
    QueueCmd -Add experiments\job_$n.sh -Label "test" -Note "sleep $n" -ScriptArgs "$n 3"
    Start-Sleep -Milliseconds 1100
  }

  Write-Host "== tick 1: the connection drops before the remote acts (FSQ_FAULT=presubmit)"
  SaveCfg "FSQ_FAULT=presubmit"
  QueueCmd -Tick
  Check ((Local pending) -eq 3 -and (Local running) -eq 0) "all three still pending here (pending=$(Local pending))"
  Check (-not (Test-Path $trace)) "nothing started on the remote"

  Write-Host "== tick 2: the connection drops after the remote acts (FSQ_FAULT=submit)"
  SaveCfg "FSQ_FAULT=submit"
  QueueCmd -Tick
  Check ((Local pending) -eq 0 -and (Local running) -eq 3) "all three moved to running here despite exit 255 (running=$(Local running))"

  Write-Host "== tick 3 onward: plain ticks until done"
  SaveCfg $null
  $deadline = (Get-Date).AddSeconds(90)
  while ((Local done) -lt 3 -and (Get-Date) -lt $deadline) {
    QueueCmd -Tick
    Start-Sleep -Seconds 2
  }
  Write-Host "== -List"
  QueueCmd -List
  Write-Host "== -Log (first job)"
  $first = (Get-ChildItem "$laptop\queue\done" -Filter *.json | Sort-Object Name | Select-Object -First 1).BaseName
  QueueCmd -Log $first
  Write-Host "== -Status"
  QueueCmd -Status
  Write-Host "== -Fetch (nothing left)"
  QueueCmd -Fetch

  Write-Host "== trace"
  $t = @(Get-Content $trace)
  $t | ForEach-Object { "    $_" }
  $starts = @($t | Where-Object { $_ -like "start *" })
  foreach ($n in "a", "b", "c") {
    Check (@($starts | Where-Object { $_ -like "start $n *" }).Count -eq 1) "job $n started exactly once"
  }
  $ev = $t | ForEach-Object { $p = $_ -split ' '; [pscustomobject]@{ t = [double]$p[2]; d = $(if ($p[0] -eq 'start') { 1 } else { -1 }) } } | Sort-Object t, d
  $c = 0; $m = 0; foreach ($e in $ev) { $c += $e.d; if ($c -gt $m) { $m = $c } }
  Check ($m -eq 1) "never more than one at a time (max overlap $m)"
  Check ((($starts | ForEach-Object { ($_ -split ' ')[1] }) -join ' ') -eq "a b c") "started in queue order"
  Check ((Local done) -eq 3) "three jobs done here"
  $doneJobs = Get-ChildItem "$laptop\queue\done" -Filter *.json | ForEach-Object { Get-Content $_.FullName -Raw | ConvertFrom-Json }
  Check (@($doneJobs | Where-Object { $_.status -eq "ok" -and $_.result -eq ("results/" + [IO.Path]::GetFileNameWithoutExtension($_.script) + ".json") }).Count -eq 3) "each settled ok with its results/<stem>.json"
  Check ((Test-Path "$laptop\results\job_a.json") -and (Test-Path "$laptop\results\job_c.json")) "result files fetched into results/"
  $wt = & wsl.exe -d $Distro -e bash -c "ls '$lSpool/wt' | wc -l; ls '$lSpool/collected' | wc -l; git -C '$lRemote' worktree list | wc -l"
  Check (($wt -join ',') -eq "0,3,1") "remote: no worktrees left, three collected (got $($wt -join ','))"
  $procs = & wsl.exe -d $Distro -e bash -c "pgrep -af '$lSpool/bin/fsq' | grep -v pgrep | wc -l"
  Check ("$procs".Trim() -eq "0") "no runner process left on the stand-in remote"
} finally {
  Pop-Location
  if ($keep -and -not $keep.HasExited) { Stop-Process -Id $keep.Id -Force }
  & wsl.exe -d $Distro -e bash -c "rm -rf /dev/shm/fsq-qtest"
}
Write-Host ""
Write-Host "passed $pass, failed $fail"
if ($fail) { exit 1 }
