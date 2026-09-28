<#
.SYNOPSIS
  The lab's job queue: a thin frontend to env.py (Scientist plugin, plan section 3.5).

.DESCRIPTION
  Same flags as the lab's old scripts\queue.ps1; everything is done by
  `py env.py queue ...` against the queue target, the profile named by the home's
  policy.run in .claude/academy.json (or queue/config.json in a home that has no
  academy.json yet). Queue state stays in <lab home>/queue/.

  queue.ps1 -Add experiments\foo.py [-Label lab:x] [-Note "..."] [-ScriptArgs "--bound 40"]
  queue.ps1 -List | -Check | -Tick | -Fetch | -Status | -Log <id-prefix>
  queue.ps1 -Setup | -Preflight | -Deploy [-NoCron] | -Pause | -Resume
  queue.ps1 ... -EnvProfile <name>      another queue target than policy.run
  queue.ps1 ... -LabHome <dir>        the lab (set by the lab's shim; default: the cwd's home)

  The semantics are the old ones (py env.py --help): a job runs the commit that was
  HEAD when it was submitted, -Tick skips uncommitted scripts, the remote runner must
  be byte-identical to the plugin's fsq.sh, and a job id runs at most once.
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
  [string] $EnvProfile,
  [string] $LabHome,
  [Parameter(ValueFromRemainingArguments = $true)] [string[]] $ScriptArgs
)

$ErrorActionPreference = "Stop"
$envPy = Join-Path $PSScriptRoot "env.py"
$a = @()
if ($LabHome) { $a += @("--home", (Resolve-Path $LabHome).Path) }
$a += "queue"
if ($EnvProfile) { $a += @("--profile", $EnvProfile) }
if ($Add) { $a += @("-Add", (Resolve-Path $Add).Path) }
# PowerShell 5.1 silently drops an empty-string element when splatting @a to a native
# command, which shifts every argument after it (-Label '' would turn '-Note' into
# the value of -Label, and shove the real note into $ScriptArgs). env.py treats a
# missing -Label/-Note exactly like an explicit empty one (both end up ""), so the
# safe fix is simply never to emit the empty pair, rather than to pass a value that
# would vanish in transit anyway.
if ($PSBoundParameters.ContainsKey('Label') -and $Label -ne '') { $a += @("-Label", $Label) }
if ($PSBoundParameters.ContainsKey('Note') -and $Note -ne '') { $a += @("-Note", $Note) }
foreach ($s in "List", "Check", "Tick", "Fetch", "Status", "Setup", "Preflight", "Deploy", "NoCron", "Pause", "Resume") {
  if ((Get-Variable $s -ValueOnly).IsPresent) { $a += "-$s" }
}
if ($Log) { $a += @("-Log", $Log) }
$rest = @($ScriptArgs | Where-Object { $_ -ne $null -and $_ -ne "--" })
if ($rest.Count -gt 0) { $a += "-ScriptArgs"; $a += $rest }
$prev = $ErrorActionPreference; $ErrorActionPreference = "Continue"
try { & py $envPy @a; $code = $LASTEXITCODE } finally { $ErrorActionPreference = $prev }
exit $code
