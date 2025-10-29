# Create RDP user without password. Avoid password policy by using New-LocalUser.
$existing = Get-LocalUser -Name "runneradmin" -ErrorAction SilentlyContinue
if (-not $existing) {
  New-LocalUser -Name "runneradmin" -NoPassword -AccountNeverExpires
}
Set-LocalUser -Name "runneradmin" -PasswordNeverExpires $true
Add-LocalGroupMember -Group "Administrators" -Member "runneradmin" -ErrorAction SilentlyContinue
Add-LocalGroupMember -Group "Remote Desktop Users" -Member "runneradmin" -ErrorAction SilentlyContinue
if (-not (Get-LocalUser -Name "runneradmin")) { throw "User creation failed" }
