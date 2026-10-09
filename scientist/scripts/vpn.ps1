<#
.SYNOPSIS
  The "globalprotect" gateway check: is the GlobalProtect tunnel up? Local check,
  no network round trip.

.DESCRIPTION
  Prints one line and sets the exit code: 0 = up, 1 = down, 2 = cannot tell.
  env.py runs it (Windows only) for a workspace gateway whose check is
  globalprotect (workspace.json compute.gateways; docs/config.md), before anything
  is sent to the worker behind it, so a poll costs a millisecond instead of an
  ssh timeout.

  Palo Alto GlobalProtect installs a virtual adapter ("PANGP Virtual Ethernet
  Adapter Secure"). The adapter exists whether or not the tunnel is up; its Status
  is what changes, from Disabled to Up. Matching on the description rather than the
  name survives a rename. DNS is not a discriminator: a host behind such a VPN often
  resolves from the open internet, and only the connection times out.

  -AdapterPattern overrides the adapter match (the gateway's "adapter" key).
  -Probe additionally opens a TCP connection to -HostName:-Port (the gateway's
  probeHost), for the case where the tunnel is up but the host is down; env.py
  does that probe itself, so -Probe is for running this script by hand.

.EXAMPLE
  vpn.ps1
  vpn.ps1 -Quiet; if ($LASTEXITCODE -eq 0) { "up" }
  vpn.ps1 -Probe -HostName server.example.org -Port 22
#>
param(
  [switch] $Quiet,
  [switch] $Probe,
  [string] $AdapterPattern = 'PANGP|GlobalProtect',
  [string] $HostName = "",
  [int]    $Port = 22,
  [int]    $TimeoutMs = 4000
)

$ErrorActionPreference = "Stop"

function Say($msg) { if (-not $Quiet) { Write-Host $msg } }

$adapter = Get-NetAdapter | Where-Object {
  $_.InterfaceDescription -match $AdapterPattern -or $_.Name -match $AdapterPattern
} | Select-Object -First 1

if (-not $adapter) {
  Say "vpn: cannot tell (no adapter matching '$AdapterPattern' found)"
  exit 2
}

if ($adapter.Status -ne 'Up') {
  Say "vpn: down ($($adapter.Name): $($adapter.Status))"
  exit 1
}

if (-not $Probe) {
  Say "vpn: up ($($adapter.Name))"
  exit 0
}
if (-not $HostName) {
  Say "vpn: up ($($adapter.Name)); -Probe needs -HostName"
  exit 2
}

# Tunnel is up; check the host itself. TcpClient with an explicit wait, because
# Test-NetConnection has no usable timeout in PowerShell 5.1.
$client = New-Object System.Net.Sockets.TcpClient
try {
  $async = $client.BeginConnect($HostName, $Port, $null, $null)
  if ($async.AsyncWaitHandle.WaitOne($TimeoutMs) -and $client.Connected) {
    $client.EndConnect($async)
    Say "vpn: up, ${HostName}:${Port} reachable"
    exit 0
  }
  Say "vpn: up but ${HostName}:${Port} did not answer in ${TimeoutMs}ms"
  exit 1
} catch {
  Say "vpn: up but ${HostName}:${Port} refused ($($_.Exception.Message))"
  exit 1
} finally {
  $client.Close()
}
