# Push the sandbox scripts and the Raqib code (from git: never .env) into the VM over SSH, then run a step.
#   powershell -File deploy\vm\deploy.ps1 -User <vm-admin> -Step harden|app|checks
param(
  [Parameter(Mandatory = $true)][string]$User,
  [ValidateSet("harden", "app", "checks")][string]$Step = "app",
  [int]$Port = 2222
)
$ErrorActionPreference = "Stop"
$root = (git rev-parse --show-toplevel)
$key = "$env:USERPROFILE\.ssh\raqib_vm"
$opts = @("-i", $key, "-o", "IdentitiesOnly=yes", "-o", "StrictHostKeyChecking=accept-new")
$target = "$User@127.0.0.1"
$files = Get-ChildItem "$root\deploy\vm" -File | Where-Object { $_.Extension -in ".sh", ".conf", ".apparmor", ".service", ".py" } | ForEach-Object FullName

& ssh @opts -p $Port $target "mkdir -p ~/raqib-vm"
& scp @opts -P $Port @files "${target}:raqib-vm/"
switch ($Step) {
  "harden" { & ssh @opts -p $Port $target "sudo bash ~/raqib-vm/harden.sh $User" }
  "app" {
    $tmp = Join-Path $env:TEMP "raqib-deploy"; New-Item -ItemType Directory -Force $tmp | Out-Null
    # Tracked and new files that git does not ignore: .env, .venv, node_modules and runtime data are never included.
    git -C $root ls-files -co --exclude-standard | Where-Object { Test-Path (Join-Path $root $_) } | Set-Content -Encoding ascii "$tmp\files.txt"
    tar -czf "$tmp\raqib.tar.gz" -C $root -T "$tmp\files.txt"
    if (tar -tzf "$tmp\raqib.tar.gz" | Select-String -Pattern '(^|/)\.env$') { throw ".env found in the archive: refusing to deploy" }
    tar -czf "$tmp\dist.tar.gz" -C "$root\frontend" dist
    & scp @opts -P $Port "$tmp\raqib.tar.gz" "$tmp\dist.tar.gz" "${target}:/tmp/"
    & ssh @opts -p $Port $target "sudo bash ~/raqib-vm/install-app.sh /tmp/raqib.tar.gz /tmp/dist.tar.gz"
  }
  "checks" { & ssh @opts -p $Port $target "sudo bash ~/raqib-vm/checks.sh" }
}
if ($LASTEXITCODE) { throw "step $Step failed ($LASTEXITCODE)" }
