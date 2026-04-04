# Create RDP user with password
$password = 'Abc1234567890+'
$securePassword = ConvertTo-SecureString $password -AsPlainText -Force

$existing = Get-LocalUser -Name "vum" -ErrorAction SilentlyContinue
if (-not $existing) {
  Write-Host "Creating user vum with password..."
  New-LocalUser -Name "vum" -Password $securePassword -AccountNeverExpires -PasswordNeverExpires
} else {
  Write-Host "User vum already exists, setting password..."
  Set-LocalUser -Name "vum" -Password $securePassword
}

Set-LocalUser -Name "vum" -PasswordNeverExpires $true
Add-LocalGroupMember -Group "Administrators" -Member "vum" -ErrorAction SilentlyContinue
Add-LocalGroupMember -Group "Remote Desktop Users" -Member "vum" -ErrorAction SilentlyContinue

if (-not (Get-LocalUser -Name "vum")) { throw "User creation failed" }
Write-Host "User vum configured successfully with password"
