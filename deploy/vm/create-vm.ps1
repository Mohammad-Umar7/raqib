# Create the "raqib-sandbox" VirtualBox VM with everything that could bridge guest and host turned off.
# Run on the Windows host after VirtualBox is installed:  powershell -File deploy\vm\create-vm.ps1 -Iso <path to ubuntu server iso>
param(
  [Parameter(Mandatory = $true)][string]$Iso,
  [string]$Name = "raqib-sandbox",
  [int]$MemoryMB = 4096,
  [int]$Cpus = 2,
  [int]$DiskMB = 16384
)
$ErrorActionPreference = "Stop"
$vbox = "C:\Program Files\Oracle\VirtualBox\VBoxManage.exe"
function VB { & $vbox @args; if ($LASTEXITCODE) { throw "VBoxManage $($args -join ' ') failed ($LASTEXITCODE)" } }

if ((& $vbox list vms) -match "`"$Name`"") { throw "A VM called $Name already exists." }
VB createvm --name $Name --ostype Ubuntu_64 --register
$folder = Split-Path ((& $vbox showvminfo $Name --machinereadable | Select-String '^CfgFile=').ToString().Split('"')[1])

# Hardware: enough for headless Chrome, nothing more.
VB modifyvm $Name --memory $MemoryMB --cpus $Cpus --ioapic on --firmware efi --graphicscontroller vmsvga --vram 16 --accelerate-3d off
# Every guest<->host channel off: audio, USB, serial, remote display, clipboard, drag and drop. (No Guest Additions are installed either.)
VB modifyvm $Name --audio-enabled off --usb-ohci off --usb-ehci off --usb-xhci off --uart1 off --vrde off --clipboard-mode disabled --drag-and-drop disabled
# One NAT adapter. The guest cannot reach the host's own loopback services; the host reaches the guest only on 127.0.0.1.
VB modifyvm $Name --nic1 nat --cable-connected1 on --nic2 none --nic3 none --nic4 none
VB modifyvm $Name --nat-localhostreachable1=off  # needs the "=" form: "--nat-localhostreachable1 off" is silently ignored
if ((& $vbox showvminfo $Name --machinereadable | Select-String '^localhostReachable=') -notmatch '"0"') { throw "host loopback is still reachable from the guest" }
VB modifyvm $Name --natpf1 "ssh,tcp,127.0.0.1,2222,,22" --natpf1 "app,tcp,127.0.0.1,8610,,8600"
VB modifyvm $Name --boot1 dvd --boot2 disk --boot3 none --boot4 none

$disk = Join-Path $folder "$Name.vdi"
VB createmedium disk --filename $disk --size $DiskMB --format VDI
VB storagectl $Name --name SATA --add sata --controller IntelAhci --portcount 2
VB storageattach $Name --storagectl SATA --port 0 --device 0 --type hdd --medium $disk
VB storageattach $Name --storagectl SATA --port 1 --device 0 --type dvddrive --medium $Iso

"Created $Name in $folder"
& $vbox showvminfo $Name --machinereadable | Select-String '^(memory|cpus|audio_enabled|usb|clipboard|draganddrop|vrde|nic1|natnet1|Forwarding|uart1|accelerate3d|SharedFolder)' | ForEach-Object { "  $_" }
