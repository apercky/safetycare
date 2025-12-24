#!/bin/bash
# =============================================================================
# SafetyCare SSL Certificate Generator
# =============================================================================
# Generates a self-signed CA and server certificate for local HTTPS development
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Configuration
DOMAIN="${DOMAIN:-safetycare.local}"
CA_DAYS="${CA_DAYS:-3650}"        # 10 years for CA
CERT_DAYS="${CERT_DAYS:-825}"     # ~2.25 years for server cert (Apple limit)
KEY_SIZE="${KEY_SIZE:-4096}"
CA_SUBJECT="${CA_SUBJECT:-/C=IT/ST=Italy/L=Local/O=SafetyCare/OU=Development/CN=SafetyCare Root CA}"
SERVER_SUBJECT="${SERVER_SUBJECT:-/C=IT/ST=Italy/L=Local/O=SafetyCare/OU=Development/CN=${DOMAIN}}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if openssl is installed
if ! command -v openssl &> /dev/null; then
    log_error "OpenSSL is not installed. Please install it first."
    exit 1
fi

log_info "OpenSSL version: $(openssl version)"

# Backup existing certificates
if [[ -f "ca.crt" ]] || [[ -f "server.crt" ]]; then
    BACKUP_DIR="backup_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$BACKUP_DIR"
    log_warn "Existing certificates found. Backing up to $BACKUP_DIR/"
    [[ -f "ca.crt" ]] && mv ca.crt ca.key "$BACKUP_DIR/" 2>/dev/null || true
    [[ -f "server.crt" ]] && mv server.crt server.key server.csr "$BACKUP_DIR/" 2>/dev/null || true
fi

# =============================================================================
# Step 1: Generate CA (Certificate Authority)
# =============================================================================
log_info "Generating CA private key (${KEY_SIZE} bits)..."
openssl genrsa -out ca.key ${KEY_SIZE}

log_info "Generating CA certificate (valid for ${CA_DAYS} days)..."
openssl req -new -x509 \
    -days ${CA_DAYS} \
    -key ca.key \
    -out ca.crt \
    -subj "${CA_SUBJECT}" \
    -addext "basicConstraints=critical,CA:TRUE" \
    -addext "keyUsage=critical,keyCertSign,cRLSign"

log_success "CA certificate generated: ca.crt"

# =============================================================================
# Step 2: Generate Server Certificate
# =============================================================================
log_info "Generating server private key (${KEY_SIZE} bits)..."
openssl genrsa -out server.key ${KEY_SIZE}

log_info "Creating certificate signing request..."
openssl req -new \
    -key server.key \
    -out server.csr \
    -subj "${SERVER_SUBJECT}"

# Create SAN (Subject Alternative Name) config
cat > san.cnf << EOF
[req]
distinguished_name = req_distinguished_name
req_extensions = v3_req
prompt = no

[req_distinguished_name]
CN = ${DOMAIN}

[v3_req]
basicConstraints = CA:FALSE
keyUsage = critical, digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth, clientAuth
subjectAltName = @alt_names

[alt_names]
DNS.1 = ${DOMAIN}
DNS.2 = *.${DOMAIN}
DNS.3 = localhost
DNS.4 = *.localhost
IP.1 = 127.0.0.1
IP.2 = ::1
EOF

log_info "Signing server certificate with CA (valid for ${CERT_DAYS} days)..."
openssl x509 -req \
    -days ${CERT_DAYS} \
    -in server.csr \
    -CA ca.crt \
    -CAkey ca.key \
    -CAcreateserial \
    -out server.crt \
    -extfile san.cnf \
    -extensions v3_req

# Cleanup temporary files
rm -f san.cnf server.csr ca.srl

log_success "Server certificate generated: server.crt"

# =============================================================================
# Step 3: Verify Certificates
# =============================================================================
log_info "Verifying certificate chain..."
if openssl verify -CAfile ca.crt server.crt; then
    log_success "Certificate chain verified successfully!"
else
    log_error "Certificate verification failed!"
    exit 1
fi

# =============================================================================
# Step 4: Set Permissions
# =============================================================================
chmod 644 ca.crt server.crt
chmod 600 ca.key server.key

log_success "Permissions set (private keys: 600, certificates: 644)"

# =============================================================================
# Step 5: Display Certificate Info
# =============================================================================
echo ""
echo "============================================================================="
echo -e "${GREEN}Certificate Generation Complete!${NC}"
echo "============================================================================="
echo ""
echo "Files generated:"
echo "  - ca.crt      : CA certificate (install this on clients)"
echo "  - ca.key      : CA private key (keep this secure!)"
echo "  - server.crt  : Server certificate"
echo "  - server.key  : Server private key"
echo ""
echo "Server certificate details:"
openssl x509 -in server.crt -noout -subject -issuer -dates -ext subjectAltName 2>/dev/null | head -10
echo ""
echo "============================================================================="
echo -e "${YELLOW}NEXT STEPS:${NC}"
echo "============================================================================="
echo ""
echo "1. Install CA certificate on your system (see README.md for instructions)"
echo ""
echo "2. Add to /etc/hosts (or equivalent):"
echo "   127.0.0.1 ${DOMAIN}"
echo ""
echo "3. Start the application:"
echo "   cd .. && docker-compose up -d"
echo ""
echo "4. Access: https://${DOMAIN}"
echo ""
