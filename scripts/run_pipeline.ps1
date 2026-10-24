$ProjectRoot = "C:\Users\GreatMT\workspace\develope\mail_work"
Set-Location $ProjectRoot

$today = Get-Date -Format "yyyy-MM-dd"
$logFile = Join-Path $ProjectRoot "logs\$today.log"

$promptText = Get-Content -Raw -Encoding utf8 (Join-Path $ProjectRoot "prompts\daily_mail_pipeline.md")

"=== 실행 시작: $(Get-Date -Format o) ===" | Out-File -Append -Encoding utf8 $logFile

try {
    & claude -p $promptText *>> $logFile
} catch {
    "ERROR: $_" | Out-File -Append -Encoding utf8 $logFile
}

"=== 실행 종료: $(Get-Date -Format o) ===" | Out-File -Append -Encoding utf8 $logFile

# 파이프라인 종료 후 5분간 키보드/마우스 입력이 없으면 절전 모드로 복귀
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
    "=== $idleWaitSeconds 초간 사용자 활동 없음 -> 절전 모드 진입 ===" | Out-File -Append -Encoding utf8 $logFile
    Start-Sleep -Seconds 2
    rundll32.exe powrprof.dll,SetSuspendState 0,1,0
} else {
    "=== 대기 중 사용자 활동 감지 -> 절전 모드 보류 ===" | Out-File -Append -Encoding utf8 $logFile
}
