<#
.SYNOPSIS
  Run a Python/Sage script in the `flatsurf` conda environment, from Windows.

.DESCRIPTION
  Targets:
    wsl          (default) the WSL Ubuntu distro on this machine
    ssh:<host>   a remote Linux machine reachable by `ssh <host>` (key-based
                 login must already work; the script is piped over stdin)

  The environment is the one created by scripts/setup_env.sh on the target:
  Miniforge at ~/miniforge3, env name `flatsurf`. Override with -Prefix/-EnvName.

.EXAMPLE
  .\flatsurf-run.ps1 .\experiment.py
  .\flatsurf-run.ps1 .\experiment.py -Target ssh:mathserver
  .\flatsurf-run.ps1 -Code "from flatsurf import *; print(translation_surfaces.veech_double_n_gon(5).stratum())"
  .\flatsurf-run.ps1 -Sage -Code "print(factor(2^64-1))"
#>
param(
  [Parameter(Position = 0)] [string] $Script,
  [string] $Code,
  [string] $Target = "wsl",
  [string] $Distro = "Ubuntu",
  [string] $Prefix = '~/miniforge3',
  [string] $EnvName = "flatsurf",
  [switch] $Sage,
  [Parameter(ValueFromRemainingArguments = $true)] [string[]] $ScriptArgs
)

$ErrorActionPreference = "Stop"
if (-not $Script -and -not $Code) { throw "Give a script path or -Code." }
if ($Script -and $Code) { throw "Give either a script path or -Code, not both." }

$interp = if ($Sage) { "sage" } else { "python" }
# A sourced `conda activate`, not `mamba run` (which holds stdout until exit) and not
# PATH alone (which skips the activate.d scripts, and cling under pyflatsurf segfaults).
$runner = "set +u; . $Prefix/etc/profile.d/conda.sh && conda activate $EnvName && $interp"

if ($Target -eq "wsl") {
  if ($Code) {
    $cmd = "$runner -c " + "'" + ($Code -replace "'", "'\''") + "'"
    & wsl.exe -d $Distro -- bash -lc $cmd
  } else {
    $abs = (Resolve-Path $Script).Path
    $wslPath = & wsl.exe -d $Distro -- wslpath -a ($abs -replace '\\', '/')
    $argStr = ($ScriptArgs | ForEach-Object { "'" + ($_ -replace "'", "'\''") + "'" }) -join " "
    & wsl.exe -d $Distro -- bash -lc "$runner '$wslPath' $argStr"
  }
}
elseif ($Target -like "ssh:*") {
  $host_ = $Target.Substring(4)
  if ($Code) {
    $Code | & ssh $host_ "$runner -"
  } else {
    $argStr = ($ScriptArgs | ForEach-Object { "'" + ($_ -replace "'", "'\''") + "'" }) -join " "
    Get-Content -Raw $Script | & ssh $host_ "$runner - $argStr"
  }
}
else { throw "Unknown target '$Target'. Use 'wsl' or 'ssh:<host>'." }

exit $LASTEXITCODE
