<#
.SYNOPSIS
  Job queue for experiment runs on the remote server (default ssh:lingo), which is
  reachable only behind the TAU VPN. Jobs wait in queue/pending until the host
  answers. Nothing here ever runs an experiment on the laptop.

.DESCRIPTION
  The laptop submits and fetches; the remote schedules. On the remote side the
  runner is scripts/fsq.sh, deployed to <fsqHome>/bin/fsq. It keeps its own spool,
  runs at most `maxJobs` jobs at once (1..3, enforced there), starts each queue id
  at most once, gives every job its own git worktree at the job's commit, and
  starts the next pending job (FIFO by queue id) when one finishes, with or
  without a laptop around.

  scripts\queue.ps1 -Add experiments\foo.py [-Label prop:x] [-Note "..."] [-ScriptArgs "--bound 40"]
      Script arguments go through -ScriptArgs, as one quoted string or as a list
      ("--bound","40"). The bare `-- --bound 40` form loses tokens when this script
      is invoked by path from PowerShell 5.1, so it is not supported here.
  scripts\queue.ps1 -List             local job files (no network)
  scripts\queue.ps1 -Check            reachability of the target; exit 0 reachable / 1 not
  scripts\queue.ps1 -Tick             if reachable: submit pending jobs, reconcile with the
                                      remote spool, fetch and settle finished ones
  scripts\queue.ps1 -Fetch            the same without submitting anything
  scripts\queue.ps1 -Status           the remote spool as the runner sees it
  scripts\queue.ps1 -Log <id-prefix>  tail the remote log of a submitted job
  scripts\queue.ps1 -Setup            one-time conda environment install on the target
  scripts\queue.ps1 -Preflight        check every assumption the runner makes on the target
  scripts\queue.ps1 -Deploy [-NoCron] preflight, then install the runner (starts paused)
  scripts\queue.ps1 -Pause / -Resume  stop or allow new starts on the remote

  queue/config.json:
    { "target": "ssh:lingo", "prefix": "/data/roeyzemmel/miniforge3",
      "remoteRepo": "~/FlatSurfLab", "fsqHome": "~/fsq", "maxJobs": 1 }
  Job files move queue/pending/<id>.json -> queue/running/<id>.json -> queue/done/<id>.json.
  Local "running" means "accepted by the remote" (queued there or running); the
  remote state is in the job's remoteState field after each -Tick.

  A job runs the commit that was HEAD when it was submitted: -Tick skips a job whose
  script is uncommitted or not in HEAD and says so. The commit is pushed to
  refs/fsq/<id> on the remote so it stays reachable until the job is collected.

  Submitting is idempotent. -Tick never trusts an ssh exit code to decide whether a
  job started: after submitting it reads the remote spool and moves each job to the
  state the remote reports. A job the remote already knows is never submitted again.

  For the local test only, the target may be "wsl:<distro>", with "pushUrl" (a
  Windows path to the stand-in repo) and "remoteEnv" (assignments prefixed to every
  runner call, e.g. "FSQ_FAULT=submit") in the config. See scripts/test_queue.ps1.
#>
param(
  [string] $Add,
  [string] $Label,
  [string] $Note,
  [switch] $List,
  [switch] $Check,
  [switch] $Tick,
  [switch] $Fetch,
  [switch] $Status,
  [string] $Log,
  [switch] $Setup,
  [switch] $Preflight,
  [switch] $Deploy,
  [switch] $NoCron,
  [switch] $Pause,
  [switch] $Resume,
  [Parameter(ValueFromRemainingArguments = $true)] [string[]] $ScriptArgs
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$qdir = Join-Path $repoRoot "queue"
foreach ($d in "pending", "running", "done") {
  New-Item -ItemType Directory -Force (Join-Path $qdir $d) | Out-Null
}
$cfgPath = Join-Path $qdir "config.json"
if (Test-Path $cfgPath) {
  $cfg = Get-Content $cfgPath -Raw | ConvertFrom-Json
} else {
  $cfg = [pscustomobject]@{ target = "ssh:lingo"; prefix = $null; remoteRepo = '~/FlatSurfLab' }
}
function Cfg($name, $default) {
  $p = $cfg.PSObject.Properties[$name]
  if ($p -and $null -ne $p.Value -and "$($p.Value)" -ne "") { return $p.Value }
  return $default
}
$target = $cfg.target
$remoteRepo = Cfg "remoteRepo" '~/FlatSurfLab'
$remoteRel = $remoteRepo -replace '^~/', ''
$fsqHome = Cfg "fsqHome" '~/fsq'
$maxJobs = [int](Cfg "maxJobs" 1)
$prefix = Cfg "prefix" $null
$remoteEnv = Cfg "remoteEnv" ""
if ($target -like "ssh:*") {
  $transport = "ssh"; $hostName = $target.Substring(4)
} elseif ($target -like "wsl:*") {
  $transport = "wsl"; $hostName = $target.Substring(4)   # test stand-in: a WSL distro
} else {
  throw "queue/config.json target must be ssh:<host> (or wsl:<distro> for the local test)."
}
$pushUrl = Cfg "pushUrl" "${hostName}:$remoteRel"
$fsqBin = "$fsqHome/bin/fsq"
$localRunner = Join-Path $PSScriptRoot "fsq.sh"
$runner = Join-Path $PSScriptRoot "run.ps1"
$utf8 = New-Object System.Text.UTF8Encoding $false
$script:rc = 0

function Q($s) { "'" + ($s -replace "'", "'\''") + "'" }

# Run one command line on the target and return its output lines (stdout and
# stderr, minus ssh's post-quantum banner). $script:rc holds the exit code.
# ErrorActionPreference drops to Continue for the call: PowerShell 5.1 turns a
# native command's stderr into a terminating error under "Stop" even when the
# command succeeds.
function Remote([string] $cmd) {
  $prev = $ErrorActionPreference; $ErrorActionPreference = "Continue"
  try {
    if ($transport -eq "ssh") {
      $out = & ssh -o BatchMode=yes $hostName $cmd 2>&1
    } else {
      $out = & wsl.exe -d $hostName -e bash -c $cmd 2>&1
    }
    $script:rc = $LASTEXITCODE
  } finally { $ErrorActionPreference = $prev }
  @($out | ForEach-Object { "$_" } | Where-Object { $_ -notmatch '^\*\* ' })
}

function Fsq([string] $argLine) {
  $envp = if ($remoteEnv) { "$remoteEnv " } else { "" }
  Remote "$envp$fsqBin $argLine"
}

function WslPath([string] $winPath) {
  (& wsl.exe -d $hostName -e wslpath -a ($winPath -replace '\\', '/')).Trim()
}

function CopyFromRemote([string] $remotePath, [string] $dest) {
  New-Item -ItemType Directory -Force (Split-Path $dest) | Out-Null
  if ($transport -eq "ssh") {
    & scp -q "${hostName}:$($remotePath -replace '^~/', '')" $dest
  } else {
    & wsl.exe -d $hostName -e cp $remotePath (WslPath $dest)
  }
  return ($LASTEXITCODE -eq 0)
}

function CopyToRemote([string] $src, [string] $remotePath) {
  if ($transport -eq "ssh") {
    & scp -q $src "${hostName}:$($remotePath -replace '^~/', '')"
  } else {
    & wsl.exe -d $hostName -e cp (WslPath $src) $remotePath
  }
  return ($LASTEXITCODE -eq 0)
}

function Reachable {
  if ($transport -ne "ssh") { return $true }
  # Cheap local check first: with the VPN down, ssh would sit through an
  # eight-second TCP timeout to learn what the adapter status already says.
  # Exit 2 means "cannot tell" (no VPN adapter), in which case fall through
  # to the real probe rather than guessing.
  & (Join-Path $PSScriptRoot "vpn.ps1") -Quiet
  if ($LASTEXITCODE -eq 1) { return $false }

  # cmd.exe swallows ssh's stderr banner; under "Stop" a PowerShell 2>$null on a
  # native command would itself throw.
  & cmd /c "ssh -o ConnectTimeout=8 -o BatchMode=yes $hostName true 2>nul"
  return ($LASTEXITCODE -eq 0)
}

function RequireReachable {
  if (-not (Reachable)) {
    $n = @(LoadJobs "pending").Count
    Write-Host "unreachable: $hostName (VPN?) -- $n pending job(s) wait."
    exit 1
  }
}

# The deployed runner must be byte-identical to scripts/fsq.sh.
function RequireDeployed {
  $want = (Get-FileHash -Algorithm SHA256 $localRunner).Hash.ToLower()
  $got = (Fsq "version" | Select-Object -Last 1)
  if ($script:rc -ne 0 -or "$got".Trim() -ne $want) {
    Write-Host "the runner on $hostName is missing or differs from scripts/fsq.sh (remote: $got). Run scripts\queue.ps1 -Deploy."
    exit 1
  }
}

function LoadJobs($dir) {
  Get-ChildItem (Join-Path $qdir $dir) -Filter *.json | Sort-Object Name | ForEach-Object {
    $j = Get-Content $_.FullName -Raw | ConvertFrom-Json
    $j | Add-Member -NotePropertyName _path -NotePropertyValue $_.FullName -Force
    $j
  }
}

function SaveJob($job, $dir) {
  $old = $job._path
  $job.PSObject.Properties.Remove('_path')
  $path = Join-Path (Join-Path $qdir $dir) "$($job.id).json"
  [IO.File]::WriteAllText($path, (($job | ConvertTo-Json -Depth 4) + "`n"), $utf8)
  if ($old -and ($old -ne $path) -and (Test-Path $old)) { Remove-Item $old }
  $job | Add-Member -NotePropertyName _path -NotePropertyValue $path -Force
}

# Not "Set": that name is an alias of Set-Variable, and aliases win over functions.
function SetField($job, $name, $value) { $job | Add-Member -NotePropertyName $name -NotePropertyValue $value -Force }

function JobArgs($job) { @($job.args | Where-Object { $_ -ne $null -and $_ -ne "" }) }

# The remote spool: id -> record. Also sets $script:remotePaused, $script:remoteMax.
function RemoteStatus {
  $lines = Fsq "status"
  if ($script:rc -ne 0) { throw "fsq status failed on ${hostName}:`n$($lines -join "`n")" }
  $map = @{}
  $script:remotePaused = $false; $script:remoteMax = $null
  foreach ($l in $lines) {
    if ($l -eq "#paused") { $script:remotePaused = $true; continue }
    if ($l -like "#max*") { $script:remoteMax = ($l -split "`t")[1]; continue }
    $f = $l -split "`t"
    if ($f.Count -lt 9) { continue }
    $map[$f[0]] = [pscustomobject]@{
      id = $f[0]; state = $f[1]; status = $f[2]; exit = $f[3]; commit = $f[4]
      submitted = $f[5]; started = $f[6]; finished = $f[7]
      files = @($f[8] -split ',' | Where-Object { $_ })
    }
  }
  $map
}

function Submit($j) {
  if (& git -C $repoRoot status --porcelain -- $j.script) { Write-Host "skip (uncommitted): $($j.id)"; return }
  & git -C $repoRoot cat-file -e "HEAD:$($j.script)"
  if ($LASTEXITCODE) { Write-Host "skip (not in HEAD): $($j.id)"; return }
  $head = (& git -C $repoRoot rev-parse HEAD).Trim()
  $prev = $ErrorActionPreference; $ErrorActionPreference = "Continue"
  try {
    & git -C $repoRoot push --quiet $pushUrl "+${head}:refs/fsq/$($j.id)"
    $pushCode = $LASTEXITCODE
  } finally { $ErrorActionPreference = $prev }
  if ($pushCode) { Write-Warning "push of $($j.id) failed (exit $pushCode); it stays pending."; return }
  $words = @($j.id, $head, $j.script) + (JobArgs $j) | ForEach-Object { Q $_ }
  $out = Fsq ("submit " + ($words -join " "))
  if ($script:rc -ne 0) {
    # Not a verdict: the remote may have accepted it before the connection
    # dropped. The reconcile step reads what actually happened.
    Write-Warning "submit of $($j.id) returned exit $($script:rc); reconciling with the remote spool. $($out -join ' ')"
  } else {
    Write-Host ($out -join "`n")
  }
}

# Move every local job to the state the remote reports; fetch and settle the
# finished ones, then acknowledge them so the remote can drop their worktrees.
function Reconcile($map) {
  foreach ($j in @(LoadJobs "pending") + @(LoadJobs "running")) {
    $r = $map[$j.id]
    $wasRunning = $j._path -like "*\running\*"
    if (-not $r) {
      if ($wasRunning) {
        if ($j.PSObject.Properties['remoteState']) {
          Write-Warning "$($j.id) is running here but unknown on ${hostName} (spool lost?). Not resubmitted; move it back to queue/pending by hand if it should run again."
        } else {
          Write-Warning "$($j.id) was started by the old run.ps1 -Detach path and is not in the runner's spool; settle it by hand."
        }
      }
      continue
    }
    SetField $j "remoteState" $r.state
    SetField $j "commit" $r.commit.Substring(0, [Math]::Min(7, $r.commit.Length))
    SetField $j "submitted" $r.submitted
    if ($r.started) { SetField $j "started" $r.started }
    if ($r.state -in "pending", "running", "incomplete") {
      SetField $j "status" $(if ($r.state -eq "running") { "running" } else { "queued" })
      SaveJob $j "running"
      Write-Host ("{0,-8} {1}" -f $r.state, $j.id)
      continue
    }
    if ($r.state -eq "done") { Collect $j $r; continue }
    if ($r.state -eq "collected") {
      Write-Warning "$($j.id) is already collected on ${hostName} but not done here; its files are in $fsqHome/collected/$($j.id)/files."
    }
  }
  # A job settled here whose ack did not reach the remote.
  foreach ($j in @(LoadJobs "done")) {
    $r = $map[$j.id]
    if ($r -and $r.state -eq "done") { $null = Fsq "ack $(Q $j.id)" }
  }
}

function Collect($j, $r) {
  $blocked = $false
  foreach ($f in $r.files) {
    $dest = Join-Path $repoRoot ($f -replace '/', '\')
    if ((Test-Path $dest) -and (& git -C $repoRoot status --porcelain -- $f)) {
      Write-Warning "$f has uncommitted changes here; not overwritten. $($j.id) stays unsettled until that is resolved."
      $blocked = $true
    }
  }
  if ($blocked) { return }
  foreach ($f in $r.files) {
    $dest = Join-Path $repoRoot ($f -replace '/', '\')
    if (-not (CopyFromRemote "$fsqHome/done/$($j.id)/files/$f" $dest)) {
      Write-Warning "copy of $f failed; $($j.id) stays unsettled."
      return
    }
    Write-Host "fetched $f"
  }
  $stem = [IO.Path]::GetFileNameWithoutExtension($j.script)
  # A result is results/<stem>.json, or a per-run file under results/<stem>/
  # (save_result(..., subdir=<stem>)), which keeps runs over different ranges apart.
  $main = if ($r.files -contains "results/$stem.json") { "results/$stem.json" } else {
    @($r.files | Where-Object { $_ -like "results/$stem/*.json" }) | Select-Object -First 1 }
  SetField $j "files" $r.files
  SetField $j "exit" $r.exit
  SetField $j "finished" $r.finished
  SetField $j "result" $(if ($main) { $main } else { $null })
  SetField $j "status" $(if ($r.status -eq "ok" -and -not $main) { "exited-without-result" } else { $r.status })
  SetField $j "log" "$fsqHome/collected/$($j.id)/log"
  SaveJob $j "done"
  $null = Fsq "ack $(Q $j.id)"
  $what = if ($j.result) { "-> $($j.result)" } else { "($($j.status), exit $($r.exit)); log: scripts\queue.ps1 -Log $($j.id)" }
  Write-Host "done: $($j.id) $what"
}

# ------------------------------------------------------------------------------

if ($Add) {
  $abs = (Resolve-Path $Add).Path
  if (-not $abs.StartsWith($repoRoot)) { throw "Script must live inside the repo ($repoRoot)." }
  $rel = $abs.Substring($repoRoot.Length).TrimStart('\') -replace '\\', '/'
  $args_ = @($ScriptArgs | Where-Object { $_ -ne "--" })
  if ($args_.Count -eq 1 -and $args_[0] -match '\s') { $args_ = @($args_[0] -split '\s+' | Where-Object { $_ }) }
  $id = (Get-Date -Format "yyyyMMdd-HHmmss") + "_" + [IO.Path]::GetFileNameWithoutExtension($rel)
  if (Test-Path (Join-Path $qdir "*\$id.json")) { throw "A job with id $id exists already; wait a second and add again." }
  $job = [pscustomobject]@{
    id = $id; script = $rel; args = $args_; label = $Label; note = $Note
    created = (Get-Date -Format s); status = "pending"
    started = $null; commit = $null; log = $null; finished = $null; result = $null
  }
  SaveJob $job "pending"
  Write-Host "queued $id  ($rel $($args_ -join ' '))"
  $dirty = & git -C $repoRoot status --porcelain -- $rel
  $tracked = & git -C $repoRoot ls-files -- $rel
  if ($dirty -or -not $tracked) {
    Write-Warning "$rel is uncommitted; -Tick skips it until it is committed (the remote runs HEAD)."
  }
  exit 0
}

if ($List) {
  foreach ($d in "pending", "running", "done") {
    foreach ($j in LoadJobs $d) {
      $st = if ($d -eq "running" -and $j.PSObject.Properties['remoteState']) { $j.remoteState } elseif ($d -eq "done") { $j.status } else { $d }
      "{0,-8} {1,-10} {2}  {3} {4}  [{5}]  {6}" -f $d, $st, $j.id, $j.script, ((JobArgs $j) -join ' '), $j.label, $j.note
    }
  }
  exit 0
}

if ($Check) {
  if (Reachable) { Write-Host "reachable: $hostName"; exit 0 }
  Write-Host "unreachable: $hostName (VPN?)"; exit 1
}

if ($Log) {
  $j = @(LoadJobs "running") + @(LoadJobs "done") | Where-Object { $_.id -like "$Log*" } | Select-Object -First 1
  if (-not $j) { throw "No submitted job matching '$Log'." }
  RequireReachable
  if (-not $j.PSObject.Properties['remoteState'] -and $j.log) {
    # A job from the old run.ps1 -Detach path.
    Remote "tail -n 40 $($j.log)" | ForEach-Object { $_ }
  } else {
    Fsq "log $(Q $j.id) 40" | ForEach-Object { $_ }
  }
  exit $script:rc
}

if ($Setup) {
  $runArgs = @{ Target = $target; RemoteRepo = $remoteRepo }
  if ($prefix) { $runArgs.Prefix = $prefix }
  & $runner @runArgs -Setup
  exit $LASTEXITCODE
}

if ($Preflight -or $Deploy) {
  RequireReachable
  $cronFlag = if ($Deploy -and -not $NoCron) { " --cron" } else { "" }
  $pfx = if ($prefix) { " --prefix $(Q $prefix)" } else { "" }
  $null = Remote "mkdir -p $fsqHome/bin"
  if (-not (CopyToRemote $localRunner "$fsqHome/bin/fsq.new")) { throw "could not copy the runner to $hostName." }
  $out = Remote "chmod +x $fsqHome/bin/fsq.new && $fsqHome/bin/fsq.new preflight --repo $remoteRepo$pfx$cronFlag"
  $pfCode = $script:rc
  $out | ForEach-Object { $_ }
  if ($pfCode -ne 0 -or -not $Deploy) {
    $null = Remote "rm -f $fsqHome/bin/fsq.new"
    if ($pfCode -ne 0) { Write-Host "preflight failed on ${hostName}; nothing deployed."; exit 1 }
    exit 0
  }
  Remote "mv -f $fsqHome/bin/fsq.new $fsqBin && $fsqBin init --repo $remoteRepo --max $maxJobs$pfx" | ForEach-Object { $_ }
  if ($script:rc -ne 0) { throw "fsq init failed on $hostName." }
  if (-not $NoCron) {
    Fsq "cron-install" | ForEach-Object { $_ }
    if ($script:rc -ne 0) { throw "cron-install failed on $hostName." }
  }
  Write-Host "deployed $fsqBin ($(Fsq 'version' | Select-Object -Last 1))."
  Write-Host "A fresh spool starts paused: scripts\queue.ps1 -Resume lets jobs start."
  exit 0
}

if ($Pause -or $Resume) {
  RequireReachable
  RequireDeployed
  Fsq $(if ($Pause) { "pause" } else { "resume" }) | ForEach-Object { $_ }
  exit $script:rc
}

if ($Status) {
  RequireReachable
  RequireDeployed
  Fsq "status --all" | ForEach-Object { $_ }
  exit $script:rc
}

if ($Tick -or $Fetch) {
  RequireReachable
  RequireDeployed
  $map = RemoteStatus
  if ($Tick) {
    $submitted = $false
    foreach ($j in @(LoadJobs "pending")) {
      if ($map.ContainsKey($j.id)) { continue }   # already accepted there; never again
      Submit $j
      $submitted = $true
    }
    if ($submitted) { $map = RemoteStatus }
  }
  Reconcile $map
  if ($script:remotePaused) { Write-Host "note: the remote spool is paused (scripts\queue.ps1 -Resume)." }
  if ($null -ne $script:remoteMax -and "$($script:remoteMax)" -ne "$maxJobs") {
    Write-Host "note: remote max is $($script:remoteMax), config.json says $maxJobs (redeploy, or fsq set-max on the host)."
  }
  exit 0
}

Write-Host "Nothing to do. See: Get-Help $PSCommandPath"
exit 2
