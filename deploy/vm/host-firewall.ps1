# Backstop on the Windows host: the VirtualBox VM processes may not open connections to private networks
# (home router, other devices, link-local, carrier NAT), even if the guest's own firewall is switched off.
# Run once in an elevated PowerShell (Run as administrator). Remove with: Get-NetFirewallRule -DisplayName "Raqib VM:*" | Remove-NetFirewallRule
$ErrorActionPreference = "Stop"
$private = "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "169.254.0.0/16", "100.64.0.0/10", "fc00::/7", "fe80::/10"
foreach ($exe in "VirtualBoxVM.exe", "VBoxHeadless.exe") {
  $prog = "C:\Program Files\Oracle\VirtualBox\$exe"
  Get-NetFirewallRule -DisplayName "Raqib VM: $exe*" -ErrorAction SilentlyContinue | Remove-NetFirewallRule
  New-NetFirewallRule -DisplayName "Raqib VM: $exe may not reach private networks" -Direction Outbound -Action Block -Profile Any `
    -Program $prog -RemoteAddress $private | Out-Null
  "Blocked $exe -> " + ($private -join ", ")
}
