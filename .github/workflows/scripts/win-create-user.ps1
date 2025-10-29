# Create RDP user without password
New-LocalUser -Name "vum" -NoPassword -AccountNeverExpires
Add-LocalGroupMember -Group "Administrators" -Member "vum"
Add-LocalGroupMember -Group "Remote Desktop Users" -Member "vum"
if (-not (Get-LocalUser -Name "vum")) { throw "User creation failed" }
