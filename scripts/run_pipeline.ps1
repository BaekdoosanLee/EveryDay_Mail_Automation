$ProjectRoot = "C:\Users\GreatMT\workspace\develope\mail_work"
Set-Location $ProjectRoot

# claude 출력(UTF-8)을 깨지지 않게 받기 위함
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$runStart = Get-Date
$today = $runStart.ToString("yyyy-MM-dd")
$logFile = Join-Path $ProjectRoot "logs\$today.log"
$utf8NoBom = New-Object System.Text.UTF8Encoding $false

function Write-Log([string]$text) {
    [System.IO.File]::AppendAllText($logFile, $text + "`r`n", $utf8NoBom)
}

$promptText = Get-Content -Raw -Encoding utf8 (Join-Path $ProjectRoot "prompts\daily_mail_pipeline.md")

Write-Log "=== 실행 시작: $($runStart.ToString('o')) ==="

# 실행 중에는 로그 파일을 열어두지 않는다(파이프라인 10단계가 같은 파일에 기록하므로) - 끝난 뒤 한 번에 덧붙임
try {
    $output = & claude -p $promptText 2>&1 | Out-String
    Write-Log $output
} catch {
    Write-Log "ERROR: $_"
}

Write-Log "=== 실행 종료: $(Get-Date -Format o) ==="

# 예약 깨우기(절전/최대 절전에서 복귀)로 시작된 실행일 때만 다시 재운다.
# 원래 켜져 있던 PC(다운로드, 원격 접속 등 사용 중)를 강제로 재우지 않기 위함.
$wokeFromSleep = $false
try {
    $lastWake = Get-WinEvent -FilterHashtable @{
        LogName = 'System'; ProviderName = 'Microsoft-Windows-Power-Troubleshooter'; Id = 1
    } -MaxEvents 1 -ErrorAction Stop
    $wokeFromSleep = $lastWake.TimeCreated -ge $runStart.AddMinutes(-10)
} catch {
    $wokeFromSleep = $false
}

if (-not $wokeFromSleep) {
    Write-Log "=== 실행 직전 절전 복귀 기록 없음(원래 켜져 있던 PC) -> 절전 진입 안 함 ==="
    exit 0
}

Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class IdleTimeChecker {
    [StructLayout(LayoutKind.Sequential)]
    struct LASTINPUTINFO { public uint cbSize; public uint dwTime; }
    [DllImport("user32.dll")]
    static extern bool GetLastInputInfo(ref LASTINPUTINFO plii);
    public static uint GetIdleMilliseconds() {
        LASTINPUTINFO lii = new LASTINPUTINFO();
        lii.cbSize = (uint)Marshal.SizeOf(lii);
        GetLastInputInfo(ref lii);
        return (uint)Environment.TickCount - lii.dwTime;
    }
}
'@

$idleWaitSeconds = 300
Start-Sleep -Seconds $idleWaitSeconds
$idleMs = [IdleTimeChecker]::GetIdleMilliseconds()

if ($idleMs -ge ($idleWaitSeconds * 1000)) {
    Write-Log "=== 예약 깨우기 후 $idleWaitSeconds 초간 사용자 활동 없음 -> 절전 모드 진입 ==="
    Start-Sleep -Seconds 2
    # rundll32 powrprof.dll,SetSuspendState는 인자가 제대로 전달되지 않아 최대 절전으로 빠질 수 있으므로 정식 API 사용.
    # 세 번째 인자(disableWakeEvent)=false: 다음 예약 실행의 깨우기 타이머를 유지
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.Application]::SetSuspendState([System.Windows.Forms.PowerState]::Suspend, $false, $false) | Out-Null
} else {
    Write-Log "=== 대기 중 사용자 활동 감지 -> 절전 모드 보류 ==="
}
