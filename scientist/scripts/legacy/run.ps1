<#
.SYNOPSIS
  Run an experiment in the `flatsurf` conda environment (SageMath + sage-flatsurf
  + surface_dynamics) from Windows, on WSL or on a remote Linux machine.

.DESCRIPTION
  Targets:
    wsl          (default) the WSL Ubuntu distro on this laptop. The repo is
                 reached through /mnt/c, so scripts read and write the same
                 files Windows sees.
    ssh:<host>   a remote Linux machine reachable by `ssh <host>` (key-based
                 login must already work). The script runs inside a checkout of
                 this repo on the remote (-RemoteRepo, default ~/FlatSurfLab).

  Getting code to a remote. The laptop is the source of truth and the remote is
  a place to compute, so the usual route is -Push: the current commit goes
  straight from here to the remote over ssh (no GitHub credentials on a shared
  machine) and is checked out there detached. The remote runs HEAD, never the
  working tree -- commit first; the script warns when the tree is dirty and
  refuses when the script itself is not in HEAD. -Pull (`git pull --ff-only` on
  the remote) is kept for a remote that clones from somewhere it can read.

    -Setup    one-time: create the remote checkout, push, run setup_env.sh there.
    -Push     push HEAD and check it out on the remote before running.
    -Detach   start the script under nohup and return; output goes to
              scratch/remote_logs/ on the remote. Survives a dropped VPN.
    -Fetch    afterwards (or alone, once a detached run is done) copy new and
              changed files under results/ back here and clear them from the
              remote, so that the next -Push finds a clean tree there. A local
              file with uncommitted changes is never overwritten; it is skipped
              and the remote copy is left in place.

  The environment is the one created by scripts/setup_env.sh on the target:
  Miniforge at ~/miniforge3, env name `flatsurf`. Override with -Prefix/-EnvName.
  PYTHONPATH is set to the repo root so `import fslab` works everywhere.

.EXAMPLE
  scripts\run.ps1 experiments\smoke_sage.py
  scripts\run.ps1 experiments\foo.py -- --bound 40
  scripts\run.ps1 tests\run_all.py
  scripts\run.ps1 -u fslab\vh_viewer.py --squares 8 --subdivision 2
  scripts\run.ps1 -Code "from flatsurf import *; print(translation_surfaces.veech_double_n_gon(5).stratum())"
  scripts\run.ps1 -Sage -Code "print(factor(2^64-1))"
  scripts\run.ps1 -Target ssh:lingo -Setup
  scripts\run.ps1 experiments\foo.py -Target ssh:lingo -Push -Fetch
  scripts\run.ps1 experiments\foo.py -Target ssh:lingo -Push -Detach
  scripts\run.ps1 -Target ssh:lingo -Fetch
#>
param(
  [Parameter(Position = 0)] [string] $Script,
  [string] $Code,
  [string] $Target = "wsl",
  [string] $Distro = "Ubuntu",
  [string] $Prefix = '~/miniforge3',
  [string] $EnvName = "flatsurf",
  [string] $RemoteRepo = '~/FlatSurfLab',
  [switch] $Sage,
  # So that `run.ps1 -u script.py ...`, mirroring `run.sh -u script.py ...`,
  # binds here: -u is a unique prefix of -Unbuffered. Without a parameter to
  # match, PowerShell takes the script path as the value of -u and binds the
  # next token (e.g. --squares) as the script.
  [switch] $Unbuffered,
  [switch] $Pull,
  [switch] $Push,
  [switch] $Fetch,
  [switch] $Detach,
  [switch] $Setup,
  [Parameter(ValueFromRemainingArguments = $true)] [string[]] $ScriptArgs
)

$ErrorActionPreference = "Stop"
$remoteOnly = $Push -or $Pull -or $Fetch -or $Detach -or $Setup
if ($remoteOnly -and $Target -notlike "ssh:*") { throw "-Push, -Pull, -Fetch, -Detach and -Setup need -Target ssh:<host>." }
if ($Script -and $Code) { throw "Give either a script path or -Code, not both." }
if (-not $Script -and -not $Code -and -not $Fetch -and -not $Setup) { throw "Give a script path or -Code." }
if ($Detach -and -not $Script) { throw "-Detach needs a script path." }
if ($Detach -and $Fetch) { throw "-Detach returns before there is anything to fetch; run -Fetch alone once the job is done." }

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

function Q($s) { "'" + ($s -replace "'", "'\''") + "'" }

# Delegate to scripts/run.sh rather than building an activation command here.
# One implementation of "which interpreter, with what on PATH" is enough, and
# the bash side is the one that can quote reliably: PowerShell rewrites quotes
# when it hands arguments to a native command, which mangles anything more
# elaborate than single-quoted words.
$envAssign = ""
if ($Sage) { $envAssign += "SAGE=1 " }
if ($Unbuffered) { $envAssign += "PYTHONUNBUFFERED=1 " }
if ($PSBoundParameters.ContainsKey('Prefix')) { $envAssign += "MINIFORGE_PREFIX=$(Q $Prefix) " }
if ($PSBoundParameters.ContainsKey('EnvName')) { $envAssign += "FLATSURF_ENV=$(Q $EnvName) " }
$runner = "${envAssign}bash scripts/run.sh"

$argStr = ""
if ($ScriptArgs) {
  $argStr = " " + (($ScriptArgs | Where-Object { $_ -ne "--" } | ForEach-Object { Q $_ }) -join " ")
}

if ($Script) {
  $abs = (Resolve-Path $Script).Path
  if (-not $abs.StartsWith($repoRoot)) { throw "Script must live inside the repo ($repoRoot) so the remote/WSL side can find it." }
  $rel = $abs.Substring($repoRoot.Length).TrimStart('\') -replace '\\', '/'
}

$code_ = 0
if ($Target -eq "wsl") {
  $repoWsl = (& wsl.exe -d $Distro -- wslpath -a ($repoRoot -replace '\\', '/')).Trim()
  if ($Code) {
    $cmd = "cd $(Q $repoWsl) && $runner -c $(Q $Code)"
  } else {
    $cmd = "cd $(Q $repoWsl) && $runner $(Q $rel)$argStr"
  }
  & wsl.exe -d $Distro -- bash -lc $cmd
  $code_ = $LASTEXITCODE
}
elseif ($Target -like "ssh:*") {
  $host_ = $Target.Substring(4)
  # scp and git's scp-like URLs take paths relative to the remote home; neither
  # can be relied on to expand a leading ~/ .
  $remoteRel = $RemoteRepo -replace '^~/', ''
  $pre = "cd $RemoteRepo"

  if ($Setup) {
    & ssh $host_ "git init -q $RemoteRepo"
    if ($LASTEXITCODE) { throw "Could not create $RemoteRepo on $host_." }
  }
  if ($Push -or $Setup) {
    $head = (& git -C $repoRoot rev-parse HEAD).Trim()
    if ($Script) {
      # No 2>$null: under "Stop", PowerShell 5.1 turns redirected native stderr
      # into a terminating error.
      & git -C $repoRoot cat-file -e "HEAD:$rel"
      if ($LASTEXITCODE) { throw "$rel is not in HEAD, so $host_ would not have it. Commit it first." }
    }
    if (& git -C $repoRoot status --porcelain --untracked-files=no) {
      Write-Warning "Uncommitted changes here: $host_ will run commit $($head.Substring(0, 7)), not what is on disk."
    }
    # A ref of its own, never the one checked out there, so the remote needs no
    # receive.denyCurrentBranch setting. Forced: local history may be amended.
    #
    # ErrorActionPreference is dropped to Continue for this one call: git pushes
    # over ssh, ssh writes its banner (currently a post-quantum-key-exchange
    # warning) to stderr, and under "Stop" PowerShell 5.1 turns any native
    # stderr line into a terminating NativeCommandError even when the command
    # succeeds. The exit code is the thing to trust.
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
      & git -C $repoRoot push --quiet "${host_}:$remoteRel" "+HEAD:refs/heads/laptop"
      $pushCode = $LASTEXITCODE
    } finally {
      $ErrorActionPreference = $prevEap
    }
    if ($pushCode) { throw "git push to $host_ failed (exit $pushCode)." }
    # Not -f: if uncollected results are in the way this fails loudly, which is
    # the cue to run -Fetch.
    $pre += " && git checkout -q --detach $head"
  }
  if ($Pull) { $pre += " && git pull --ff-only" }

  if ($Setup) {
    $setupEnv = ""
    if ($PSBoundParameters.ContainsKey('Prefix')) { $setupEnv += "MINIFORGE_PREFIX=$(Q $Prefix) " }
    if ($PSBoundParameters.ContainsKey('EnvName')) { $setupEnv += "FLATSURF_ENV=$(Q $EnvName) " }
    & ssh $host_ "$pre && ${setupEnv}bash scripts/setup_env.sh"
    $code_ = $LASTEXITCODE
  }
  elseif ($Detach) {
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $log = "scratch/remote_logs/${stamp}_$([IO.Path]::GetFileNameWithoutExtension($rel)).log"
    # Braces, so that only the job is backgrounded and not the cd/checkout
    # before it. Assignments go before nohup; after it they would be the command.
    $job = "PYTHONUNBUFFERED=1 ${envAssign}nohup bash scripts/run.sh $(Q $rel)$argStr > $(Q $log) 2>&1 < /dev/null"
    & ssh $host_ "$pre && mkdir -p scratch/remote_logs && { $job & echo started: pid `$! on `$(hostname), log $remoteRel/$log; }"
    $code_ = $LASTEXITCODE
    if (-not $code_) { Write-Host "follow with:  ssh $host_ tail -f $remoteRel/$log" }
  }
  elseif ($Script -or $Code) {
    if ($Code) {
      $cmd = "$pre && $runner -c $(Q $Code)"
    } else {
      $cmd = "$pre && $runner $(Q $rel)$argStr"
    }
    & ssh $host_ $cmd
    $code_ = $LASTEXITCODE
  }

  if ($Fetch) {
    $new = @(& ssh $host_ "cd $RemoteRepo && git ls-files -o -m --exclude-standard results" | Where-Object { $_ })
    $done = @()
    foreach ($f in $new) {
      $dest = Join-Path $repoRoot ($f -replace '/', '\')
      if ((Test-Path $dest) -and (& git -C $repoRoot status --porcelain -- $f)) {
        Write-Warning "$f has uncommitted changes here; not overwritten, left on $host_."
        continue
      }
      New-Item -ItemType Directory -Force (Split-Path $dest) | Out-Null
      & scp -q "${host_}:$remoteRel/$f" $dest
      if ($LASTEXITCODE) { throw "scp failed for $f. Nothing was removed on $host_." }
      Write-Host "fetched $f"
      $done += $f
    }
    if ($done) {
      # Exactly the files copied, not `git clean`: a detached job may have
      # written another result since the listing.
      $clear = ($done | ForEach-Object { "{ git checkout -q -- $(Q $_) 2>/dev/null || rm -f -- $(Q $_); }" }) -join "; "
      & ssh $host_ "cd $RemoteRepo && $clear"
    } elseif (-not $new) {
      Write-Host "nothing new under results/ on $host_."
    }
  }
}
else { throw "Unknown target '$Target'. Use 'wsl' or 'ssh:<host>'." }

exit $code_
