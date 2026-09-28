<#
.SYNOPSIS
  Run a lab script in a conda env: a thin frontend to `py env.py run` (Scientist
  plugin, plan section 3.5).

.DESCRIPTION
  Same flags as the lab's old scripts\run.ps1. -Target names a profile the old way:
    wsl          (default) the wsl profile of the home (policy.test if it is one)
    wsl:<distro> the wsl profile with that distro
    ssh:<host>   the ssh profile with that host -- only for -Setup: experiments on a
                 remote host go through the queue (scripts\queue.ps1 -Add), so -Push,
                 -Pull, -Fetch and -Detach are refused with that pointer
    <profile>    any profile name or policy key of .claude/academy.json

.EXAMPLE
  run.ps1 experiments\smoke_sage.py
  run.ps1 tests\run_all.py
  run.ps1 -u fslab\vh_viewer.py --squares 8 --subdivision 2
  run.ps1 -Code "from flatsurf import *; print(translation_surfaces.veech_double_n_gon(5).stratum())"
  run.ps1 -Sage -Code "print(factor(2^64-1))"
  run.ps1 -Target ssh:lingo -Setup
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
  # -u is a unique prefix of -Unbuffered, so `run.ps1 -u script.py ...` binds here.
  [switch] $Unbuffered,
  [switch] $Pull,
  [switch] $Push,
  [switch] $Fetch,
  [switch] $Detach,
  [switch] $Setup,
  [string] $LabHome,
  [Parameter(ValueFromRemainingArguments = $true)] [string[]] $ScriptArgs
)

$ErrorActionPreference = "Stop"
$envPy = Join-Path $PSScriptRoot "env.py"
if ($Target -eq "wsl" -and $PSBoundParameters.ContainsKey('Distro')) { $Target = "wsl:$Distro" }
if ($Push -or $Pull -or $Fetch -or $Detach) {
  Write-Host "run.ps1: -Push, -Pull, -Fetch and -Detach are retired. A run on a remote host goes through the queue: scripts\queue.ps1 -Add <script> [-ScriptArgs ...], then -Tick; results come back with -Tick / -Fetch."
  exit 2
}
if ($Script -and $Code) { throw "Give either a script path or -Code, not both." }
if (-not $Script -and -not $Code -and -not $Setup) { throw "Give a script path or -Code." }

$a = @()
if ($LabHome) { $a += @("--home", (Resolve-Path $LabHome).Path) }
if ($Setup) {
  $a += @("setup", $Target)
} else {
  $a += @("run", $Target)
  if ($Sage) { $a += "--sage" }
  if ($Unbuffered) { $a += "-u" }
  if ($PSBoundParameters.ContainsKey('Prefix')) { $a += @("--prefix", $Prefix) }
  if ($PSBoundParameters.ContainsKey('EnvName')) { $a += @("--conda", $EnvName) }
  if ($Code) {
    $a += @("-c", $Code)
  } else {
    $a += "--"
    $a += (Resolve-Path $Script).Path
    $a += @($ScriptArgs | Where-Object { $_ -ne $null -and $_ -ne "--" })
  }
}
$prev = $ErrorActionPreference; $ErrorActionPreference = "Continue"
try { & py $envPy @a; $code_ = $LASTEXITCODE } finally { $ErrorActionPreference = $prev }
exit $code_
