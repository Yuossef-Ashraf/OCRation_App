# fix_mobile_access.ps1
# Automates the setup for OCRATION Mobile Access

$PORT = 5000
$RULE_NAME = "OCRATION_Mobile_Access"

write-host "--- OCRATION Mobile Access Fixer ---" -ForegroundColor Cyan

# 1. Check if port is already listening
$listener = Get-NetTCPConnection -LocalPort $PORT -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    write-host "[OK] Server is listening on port $PORT." -ForegroundColor Green
} else {
    write-host "[!] Warning: Server is NOT running or not listening on port $PORT." -ForegroundColor Yellow
    write-host "    Please make sure you have run 'run_server.bat' first."
}

# 2. Add Firewall Rule (Requires Admin)
write-host "[*] Adding Windows Firewall Rule for port $PORT..." -ForegroundColor Cyan
try {
    # Remove existing rule if any
    Remove-NetFirewallRule -DisplayName $RULE_NAME -ErrorAction SilentlyContinue
    
    # Add new rule
    New-NetFirewallRule -DisplayName $RULE_NAME `
                        -Direction Inbound `
                        -Action Allow `
                        -Protocol TCP `
                        -LocalPort $PORT `
                        -Description "Allows mobile access to OCRATION web server" `
                        -ErrorAction Stop
    
    write-host "[SUCCESS] Firewall rule '$RULE_NAME' added successfully! ✅" -ForegroundColor Green
} catch {
    write-host "[ERROR] Failed to add firewall rule. ❌" -ForegroundColor Red
    write-host "        Try running this script as Administrator."
}

# 3. Get Local IP
$ip = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notlike "*Loopback*" -and $_.IPv4Address -notlike "169.254.*" }).IPAddress | Select-Object -First 1

write-host "`n--- Your Mobile URL ---" -ForegroundColor Cyan
write-host "Type this on your phone's browser:"
write-host "http://$($ip):$($PORT)" -ForegroundColor Yellow -BackgroundColor Black
write-host "-----------------------"

write-host "`nPress any key to exit..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
