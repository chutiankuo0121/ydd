# Configure an autostart task to open a URL when user 'vum' logs on
# Hardcoded target URL per user request
$url = 'https://pplx.ai/chutiankuo64723'

try {
  $taskName = 'OpenUrlOnVumLogon'
  # Use SYSTEM to run the task so we don't need user's password
  $action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-WindowStyle Hidden -Command Start-Process '$url'"
  $trigger = New-ScheduledTaskTrigger -AtLogOn -User 'vum'
  $principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest

  # Replace if exists
  if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
  }

  Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal | Out-Null
  Write-Host "Autostart task created: $taskName -> $url"
} catch {
  Write-Error $_
  exit 1
}

