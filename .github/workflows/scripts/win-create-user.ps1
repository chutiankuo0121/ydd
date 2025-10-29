# Create RDP user without password. Avoid password policy by using New-LocalUser.
$existing = Get-LocalUser -Name "vum" -ErrorAction SilentlyContinue
if (-not $existing) {
  New-LocalUser -Name "vum" -NoPassword -AccountNeverExpires
}
Set-LocalUser -Name "vum" -PasswordNeverExpires $true
Add-LocalGroupMember -Group "Administrators" -Member "vum" -ErrorAction SilentlyContinue
Add-LocalGroupMember -Group "Remote Desktop Users" -Member "vum" -ErrorAction SilentlyContinue
if (-not (Get-LocalUser -Name "vum")) { throw "User creation failed" }
