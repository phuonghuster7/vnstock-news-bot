# setup_startup_task.ps1
# Tạo shortcut trong Windows Startup folder.
# KHÔNG cần quyền Administrator.
# Shortcut sẽ chạy khi user đăng nhập Windows.

$taskName   = "QlibVN100_MorningBrief"
$startupDir = [System.IO.Path]::Combine($env:APPDATA, "Microsoft", "Windows", "Start Menu", "Programs", "Startup")
$vbsPath    = [System.IO.Path]::Combine($startupDir, "$taskName.vbs")
$shPath     = "D:\Qlib-Vnstock\paper_trading\run_morning_brief.sh"

# VBScript wrapper de WSL chay an (khong hien cua so CMD)
$vbsContent = @"
' Morning Brief Startup Script
' Chay WSL daily_monitor.py khi dang nhap Windows
Option Explicit
Dim oShell
Set oShell = CreateObject("WScript.Shell")
oShell.Run "wsl.exe -d Ubuntu -e bash /mnt/d/Qlib-Vnstock/paper_trading/run_morning_brief.sh", 0, False
Set oShell = Nothing
"@

# Ghi VBScript vao Startup folder
[System.IO.File]::WriteAllText($vbsPath, $vbsContent, [System.Text.Encoding]::ASCII)

if (Test-Path $vbsPath) {
    Write-Host "OK: Startup script created at:" -ForegroundColor Green
    Write-Host "   $vbsPath"
    Write-Host ""
    Write-Host "Run on: next Windows login"
    Write-Host "Output: $env:USERPROFILE\Desktop\morning_brief.md"
    Write-Host ""
    Write-Host "To test immediately:"
    Write-Host "   cscript.exe `"$vbsPath`""
} else {
    Write-Host "FAILED to create startup script." -ForegroundColor Red
}

Write-Host ""
Write-Host "Startup folder contents:" -ForegroundColor Cyan
Get-ChildItem $startupDir | Select-Object Name, LastWriteTime | Format-Table -AutoSize
