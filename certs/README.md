# SSL Certificates for SafetyCare

This directory contains self-signed SSL certificates for local HTTPS development.

## Quick Start

```bash
# Generate certificates
./generate-certs.sh

# The script will create:
# - ca.crt     : Root CA certificate (install on clients)
# - ca.key     : Root CA private key (keep secure!)
# - server.crt : Server certificate (used by nginx)
# - server.key : Server private key (used by nginx)
```

## Installing the CA Certificate

To avoid browser security warnings, install the CA certificate (`ca.crt`) as a trusted root certificate on your system.

### macOS

**Option 1: Command Line (Recommended)**
```bash
# Install for all users (requires sudo)
sudo security add-trusted-cert -d -r trustRoot \
    -k /Library/Keychains/System.keychain ca.crt

# Or install for current user only
security add-trusted-cert -r trustRoot \
    -k ~/Library/Keychains/login.keychain-db ca.crt
```

**Option 2: Keychain Access GUI**
1. Double-click `ca.crt`
2. Keychain Access will open
3. Select "System" keychain (or "login" for current user only)
4. Click "Add"
5. Find the certificate "SafetyCare Root CA"
6. Double-click it → Trust → "When using this certificate" → "Always Trust"
7. Close and enter password when prompted

**Verification:**
```bash
security find-certificate -c "SafetyCare Root CA" /Library/Keychains/System.keychain
```

### Linux (Debian/Ubuntu)

```bash
# Copy CA certificate
sudo cp ca.crt /usr/local/share/ca-certificates/safetycare-ca.crt

# Update CA store
sudo update-ca-certificates

# Verification
openssl verify -CApath /etc/ssl/certs server.crt
```

**For Firefox on Linux:**
Firefox uses its own certificate store. Either:
1. Go to Settings → Privacy & Security → Certificates → View Certificates → Import
2. Or use `certutil`:
```bash
# Find Firefox profile
PROFILE=$(find ~/.mozilla/firefox -name "*.default-release" -type d)

# Add certificate
certutil -A -n "SafetyCare Root CA" -t "TC,," -i ca.crt -d sql:$PROFILE
```

### Linux (Fedora/RHEL/CentOS)

```bash
# Copy CA certificate
sudo cp ca.crt /etc/pki/ca-trust/source/anchors/safetycare-ca.crt

# Update CA store
sudo update-ca-trust extract

# Verification
trust list | grep -i safetycare
```

### Windows

**Option 1: Command Line (Run as Administrator)**
```cmd
certutil -addstore -f "ROOT" ca.crt
```

**Option 2: GUI**
1. Double-click `ca.crt`
2. Click "Install Certificate..."
3. Select "Local Machine" → Next
4. Select "Place all certificates in the following store"
5. Click "Browse" → Select "Trusted Root Certification Authorities"
6. Click Next → Finish
7. Confirm the security warning

**PowerShell (Run as Administrator):**
```powershell
Import-Certificate -FilePath .\ca.crt -CertStoreLocation Cert:\LocalMachine\Root
```

### iOS/iPadOS

1. Transfer `ca.crt` to your device (AirDrop, email, etc.)
2. Tap to install → Install Profile
3. Go to Settings → General → About → Certificate Trust Settings
4. Enable "SafetyCare Root CA" under "Enable Full Trust for Root Certificates"

### Android

1. Transfer `ca.crt` to your device
2. Go to Settings → Security → Encryption & credentials
3. Tap "Install from storage" or "Install a certificate"
4. Select "CA certificate"
5. Find and select `ca.crt`
6. Confirm installation

## Hosts File Configuration

Add the following entry to your hosts file:

```
127.0.0.1 safetycare.local
```

**File locations:**
- macOS/Linux: `/etc/hosts`
- Windows: `C:\Windows\System32\drivers\etc\hosts`

```bash
# macOS/Linux
echo "127.0.0.1 safetycare.local" | sudo tee -a /etc/hosts

# Windows (PowerShell as Administrator)
Add-Content -Path C:\Windows\System32\drivers\etc\hosts -Value "127.0.0.1 safetycare.local"
```

## Certificate Details

| File | Description | Validity | Permissions |
|------|-------------|----------|-------------|
| `ca.crt` | Root CA public certificate | 10 years | 644 (readable) |
| `ca.key` | Root CA private key | - | 600 (owner only) |
| `server.crt` | Server public certificate | ~2 years | 644 (readable) |
| `server.key` | Server private key | - | 600 (owner only) |

The server certificate includes the following Subject Alternative Names (SANs):
- `safetycare.local`
- `*.safetycare.local`
- `localhost`
- `*.localhost`
- `127.0.0.1`
- `::1`

## Regenerating Certificates

If certificates expire or you need to regenerate them:

```bash
# Remove old certificates
rm -f ca.crt ca.key server.crt server.key

# Regenerate
./generate-certs.sh

# Reinstall CA on clients
# (follow installation instructions above)

# Restart services
cd .. && docker-compose restart nginx
```

## Custom Domain

To use a different domain:

```bash
DOMAIN=myapp.local ./generate-certs.sh
```

## Troubleshooting

### Browser shows "Not Secure" or certificate error
1. Verify CA is installed: check your system's certificate store
2. Verify hosts file entry exists
3. Clear browser cache and restart browser
4. For Chrome: go to `chrome://settings/certificates` to verify

### Certificate verification fails
```bash
# Check certificate chain
openssl verify -CAfile ca.crt server.crt

# Check certificate details
openssl x509 -in server.crt -text -noout

# Test HTTPS connection
curl -v --cacert ca.crt https://safetycare.local/
```

### Connection refused
```bash
# Check if services are running
docker-compose ps

# Check nginx logs
docker-compose logs nginx

# Verify ports
netstat -tlnp | grep -E '80|443'
```

## Security Notes

⚠️ **Important Security Considerations:**

1. **Keep `ca.key` secure!** Anyone with this file can create trusted certificates
2. These certificates are for **local development only**
3. Never use self-signed certificates in production
4. The CA private key should never be committed to version control
5. Consider adding `*.key` to `.gitignore`

```bash
# Add to .gitignore
echo "certs/*.key" >> ../.gitignore
```
