<#
.SYNOPSIS
  Is the TAU VPN up? Local check, no network round trip.

.DESCRIPTION
  Prints one line and sets the exit code: 0 = up, 1 = down, 2 = cannot tell.
  Meant to be called before anything that talks to lingo, so a poll costs a
  millisecond instead of an eight-second TCP timeout.

  The VPN is Palo Alto GlobalProtect, which installs a virtual adapter
  ("PANGP Virtual Ethernet Adapter Secure", usually "Ethernet 4"). The adapter
  exists whether or not the tunnel is up; its Status is what changes, from
  Disabled to Up. Matching on the description rather than the name survives a
  rename. Note that DNS is NOT a discriminator: lingo.tau.ac.il resolves to
  132.66.113.252 from the open internet, and only the connection times out.

  -Probe additionally opens a TCP connection to the host, for the case where
  the tunnel is up but the host is down; it costs the timeout and is off by
  default.

.EXAMPLE
  scripts\vpn.ps1
  scripts\vpn.ps1 -Quiet; if ($LASTEXITCODE -eq 0) { scripts\queue.ps1 -Tick }
  scripts\vpn.ps1 -Probe
#>
param(
  [switch] $Quiet,
  [switch] $Probe,
  [string] $HostName = "lingo.tau.ac.il",
  [int]    $Port = 22,
  [int]    $TimeoutMs = 4000
)

$ErrorActionPreference = "Stop"

function Say($msg) { if (-not $Quiet) { Write-Host $msg } }

$adapter = Get-NetAdapter | Where-Object {
  $_.InterfaceDescription -match 'PANGP|GlobalProtect' -or $_.Name -match 'GlobalProtect'
} | Select-Object -First 1

if (-not $adapter) {
  Say "vpn: cannot tell (no GlobalProtect adapter found)"
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
