<#
.SYNOPSIS
  Keep the render gallery running so the phone home-screen icon always works.

.DESCRIPTION
  Registers a scheduled task that starts the gallery at logon, under the current
  user, with no console window. Prefers a Python that has Pillow (ComfyUI's own)
  so the phone gets small thumbnails instead of full PNGs.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File install-autostart.ps1
  powershell -ExecutionPolicy Bypass -File install-autostart.ps1 -Uninstall
#>
[CmdletBinding()]
param(
    [int]$Port = 8777,
    [string]$OutputDir,
    [string]$Python,
    [switch]$Uninstall
)

$ErrorActionPreference = 'Stop'
$TaskName = 'ComfyUI Render Gallery'
$here     = Split-Path -Parent $MyInvocation.MyCommand.Path
$script   = Join-Path $here 'server.py'
$logFile  = Join-Path $here 'gallery.log'

if ($Uninstall) {
    if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
        Stop-ScheduledTask    -TaskName $TaskName -ErrorAction SilentlyContinue
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "Removed scheduled task '$TaskName'." -ForegroundColor Green
    } else {
        Write-Host "No scheduled task named '$TaskName'." -ForegroundColor Yellow
    }
    try {
        Get-NetFirewallRule -DisplayName $TaskName -ErrorAction Stop | Remove-NetFirewallRule
        Write-Host "Removed firewall rule."
    } catch { }
    return
}

if (-not (Test-Path $script)) { throw "server.py not found next to this script ($script)" }

# --- pick an interpreter, preferring one that can import PIL ------------------
function Test-Pillow([string]$exe) {
    if (-not (Test-Path $exe)) { return $false }
    try { & $exe -c 'import PIL' 2>$null | Out-Null; return ($LASTEXITCODE -eq 0) }
    catch { return $false }
}

$candidates = @()
if ($Python) { $candidates += $Python }
$candidates += @(
    "$env:USERPROFILE\Documents\ComfyUI\.venv\Scripts\python.exe",   # ComfyUI Desktop
    "$env:USERPROFILE\Documents\ComfyUI\venv\Scripts\python.exe",
    "$env:USERPROFILE\ComfyUI-Shared\venv\Scripts\python.exe",
    "$env:USERPROFILE\ComfyUI-Installs\ComfyUI\ComfyUI\.venv\Scripts\python.exe",
    "$env:USERPROFILE\ComfyUI\venv\Scripts\python.exe",
    "$env:USERPROFILE\ComfyUI\.venv\Scripts\python.exe",
    "$env:USERPROFILE\ComfyUI_windows_portable\python_embeded\python.exe"
)
$candidates += (Get-Command python.exe -ErrorAction SilentlyContinue | ForEach-Object Source)

$chosen = $null
foreach ($c in $candidates) { if (Test-Pillow $c) { $chosen = $c; break } }
if (-not $chosen) {
    # No Pillow anywhere: fall back to any working Python. Gallery still runs,
    # it just sends full-size images.
    foreach ($c in $candidates) { if ($c -and (Test-Path $c)) { $chosen = $c; break } }
}
if (-not $chosen) { throw "No Python found. Pass one with -Python <path to python.exe>" }

$hasPillow = Test-Pillow $chosen
$pyw = Join-Path (Split-Path -Parent $chosen) 'pythonw.exe'   # windowless
if (-not (Test-Path $pyw)) { $pyw = $chosen }

Write-Host "Python     : $chosen"
Write-Host "Thumbnails : $(if ($hasPillow) {'Pillow (fast)'} else {'off - full images will be sent'})"
if (-not $hasPillow) {
    Write-Host "  For fast thumbnails:  & `"$chosen`" -m pip install pillow" -ForegroundColor Yellow
    Write-Host "  then re-run this script." -ForegroundColor Yellow
}

# --- register the task -------------------------------------------------------
$argLine = "`"$script`" --port $Port --log `"$logFile`""
if ($OutputDir) { $argLine += " --dir `"$OutputDir`"" }

$action = New-ScheduledTaskAction -Execute $pyw -Argument $argLine -WorkingDirectory $here
$trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings -Force | Out-Null
Write-Host "Registered scheduled task '$TaskName' (runs at logon)." -ForegroundColor Green

# --- firewall (needs admin; not fatal if we don't have it) -------------------
try {
    if (-not (Get-NetFirewallRule -DisplayName $TaskName -ErrorAction SilentlyContinue)) {
        New-NetFirewallRule -DisplayName $TaskName -Direction Inbound -Protocol TCP `
            -LocalPort $Port -Action Allow -Profile Private,Domain | Out-Null
        Write-Host "Added firewall rule for TCP $Port."
    }
} catch {
    Write-Host "Could not add a firewall rule (needs an elevated shell)." -ForegroundColor Yellow
    Write-Host "If the phone can't connect, re-run this from an admin PowerShell." -ForegroundColor Yellow
}

# --- start it now and check it actually answers ------------------------------
Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
Start-ScheduledTask -TaskName $TaskName

$ok = $false
foreach ($i in 1..10) {
    Start-Sleep -Milliseconds 700
    try {
        Invoke-WebRequest "http://127.0.0.1:$Port/api/list" -UseBasicParsing -TimeoutSec 3 | Out-Null
        $ok = $true; break
    } catch { }
}

if ($ok) {
    Write-Host "`nGallery is up." -ForegroundColor Green
} else {
    Write-Host "`nTask registered but the server did not answer on port $Port." -ForegroundColor Red
    Write-Host "Check the log: $logFile"
    if (Test-Path $logFile) { Get-Content $logFile -Tail 15 }
    return
}

$tail = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object { $_.IPAddress -like '100.*' } | Select-Object -First 1
if ($tail) {
    Write-Host "`nOn your phone, open:  http://$($tail.IPAddress):$Port" -ForegroundColor Cyan
    Write-Host "then Add to Home Screen. It'll be running after every reboot."
} else {
    Write-Host "`nNo 100.x address found - is Tailscale up? Otherwise use the LAN IP."
}
Write-Host "Log: $logFile"
Write-Host "Undo with: powershell -ExecutionPolicy Bypass -File install-autostart.ps1 -Uninstall"
