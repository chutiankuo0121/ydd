# Configure Core RDP Settings and firewall
Set-ItemProperty -Path 'HKLM:\System\CurrentControlSet\Control\Terminal Server' -Name "fDenyTSConnections" -Value 0 -Force
Set-ItemProperty -Path 'HKLM:\System\CurrentControlSet\Control\Terminal Server\WinStations\RDP-Tcp' -Name "UserAuthentication" -Value 0 -Force
Set-ItemProperty -Path 'HKLM:\System\CurrentControlSet\Control\Terminal Server\WinStations\RDP-Tcp' -Name "SecurityLayer" -Value 0 -Force
Set-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Control\Lsa' -Name "LimitBlankPasswordUse" -Value 0 -Force

# Set password for vum user
$password = 'Abc1234567890+'
net user vum $password

# Enable AutoAdminLogon for user 'vum' (attach to already-logged-on session via RDP)
$winlogon = 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon'
Set-ItemProperty -Path $winlogon -Name 'AutoAdminLogon' -Value '1' -Force
Set-ItemProperty -Path $winlogon -Name 'ForceAutoLogon' -Value 1 -Force
Set-ItemProperty -Path $winlogon -Name 'DefaultUserName' -Value 'vum' -Force
Set-ItemProperty -Path $winlogon -Name 'DefaultPassword' -Value $password -Force
Set-ItemProperty -Path $winlogon -Name 'DefaultDomainName' -Value '' -Force
Set-ItemProperty -Path $winlogon -Name 'DisableCAD' -Value 1 -Force

netsh advfirewall firewall delete rule name="RDP-Tailscale"
netsh advfirewall firewall add rule name="RDP-Tailscale" dir=in action=allow protocol=TCP localport=3389

# Add RDP credential for vum user
cmdkey /generic:TERMSRV/* /user:vum /pass:$password

Restart-Service -Name TermService -Force
