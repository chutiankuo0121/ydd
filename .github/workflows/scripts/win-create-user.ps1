# Create RDP user without password (no expiry, no change required)
# Use 'net user' flags to ensure Windows不会在首次登录要求修改密码
cmd /c "net user vum \"\" /add /passwordchg:no /passwordreq:no /expires:never"
Add-LocalGroupMember -Group "Administrators" -Member "vum"
Add-LocalGroupMember -Group "Remote Desktop Users" -Member "vum"
if (-not (Get-LocalUser -Name "vum")) { throw "User creation failed" }
