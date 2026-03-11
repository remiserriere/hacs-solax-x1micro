# MQTT Broker Configuration — Mosquitto

This page documents the Mosquitto configuration needed to receive data from the SolaX Pocket
WiFi dongle.

## How the dongle communicates

The SolaX Pocket WiFi dongle uses **two separate connections** to the same resolved hostname:

| Port | Protocol | Notes |
|------|----------|-------|
| **8883** | MQTTS (MQTT over TLS) | **May** present a client certificate but does **not** enforce certificate authentication; does **not** verify the server certificate in practice — a self-signed certificate is sufficient |
| **2901** | Plain MQTT (unencrypted) | No TLS, anonymous |

---

## Listener overview

| Port | Protocol | Purpose |
|------|----------|---------|
| `1883` | Plain MQTT | Local clients: Home Assistant, MQTT Explorer, etc. |
| `8883` | MQTTS (TLS) | SolaX Pocket WiFi dongle (encrypted channel) |
| `2901` | Plain MQTT | SolaX Pocket WiFi dongle (unencrypted channel) |

---

## Full `mosquitto.conf`

```conf
# --- General ---
persistence true
persistence_location /mosquitto/data/
log_dest file /mosquitto/log/mosquitto.log
#log_type debug

# Enables per-listener authentication settings
# (instead of one global allow_anonymous / password_file)
per_listener_settings true

# --- Listener 1883: anonymous plain MQTT for local clients ---
listener 1883
allow_anonymous true

# --- Listener 8883: MQTTS for the SolaX dongle ---
listener 8883
certfile /mosquitto/config/certs/server.crt
keyfile  /mosquitto/config/certs/server.key
# cafile is only needed if require_certificate true (client cert auth).
# Since the dongle does not present a certificate, it is NOT required.
#cafile /mosquitto/config/certs/ca.crt
require_certificate false
allow_anonymous true

# --- Listener 2901: plain MQTT for the SolaX dongle (unencrypted channel) ---
listener 2901
allow_anonymous true
```

### `cafile` — is it necessary?

In Mosquitto, `cafile` on a listener serves one purpose: providing the CA chain used to
**verify client certificates**. Since `require_certificate false` is set (the broker does _not_
ask the dongle to prove its identity with a certificate), `cafile` is **not needed** and the
lines can stay commented out.

The only required TLS directives for listener 8883 are `certfile` and `keyfile`.

---

## Generating a self-signed certificate

Because the dongle does not verify the server certificate, a simple self-signed certificate is
enough. The Common Name (`CN`) is set to `mqtt001.solaxcloud.com` both for clarity and in case
a future firmware version enables hostname verification.

```bash
# Create the directory that will hold the certs (adjust path to your setup)
mkdir -p /mosquitto/config/certs
cd /mosquitto/config/certs

# Generate a private key (RSA 2048-bit)
openssl genrsa -out server.key 2048

# Generate a self-signed certificate valid for 10 years
openssl req -new -x509 \
  -key server.key \
  -out server.crt \
  -days 3650 \
  -subj "/CN=mqtt001.solaxcloud.com" \
  -addext "subjectAltName=DNS:mqtt001.solaxcloud.com,DNS:mqtt002.solaxcloud.com"

# Restrict permissions so Mosquitto can read the key but other users cannot
chmod 640 server.key server.crt
```

> The `-addext "subjectAltName=..."` flag requires OpenSSL ≥ 1.1.1. On older systems, replace
> it with a `-extfile` approach (see the [OpenSSL docs](https://www.openssl.org/docs/)).

---

## Optional: using a CA-signed certificate (advanced)

If you prefer the overhead of a local CA (e.g. because you also use the same CA for other
services), here is a three-step approach:

```bash
# 1. Generate the CA key and self-signed CA certificate
openssl genrsa -out ca.key 4096
openssl req -new -x509 -days 3650 -key ca.key -out ca.crt -subj "/CN=Local MQTT CA"

# 2. Generate the server key and a certificate signing request (CSR)
openssl genrsa -out server.key 2048
openssl req -new -key server.key -out server.csr \
  -subj "/CN=mqtt001.solaxcloud.com"

# 3. Sign the server CSR with the CA
openssl x509 -req -days 3650 \
  -in server.csr \
  -CA ca.crt -CAkey ca.key -CAcreateserial \
  -out server.crt \
  -extfile <(printf "subjectAltName=DNS:mqtt001.solaxcloud.com,DNS:mqtt002.solaxcloud.com")

chmod 640 server.key server.crt ca.key
```

With this setup you may uncomment `cafile /mosquitto/config/certs/ca.crt` in `mosquitto.conf`.
It remains optional as long as `require_certificate false`.

---

## Docker / Docker Compose

If Mosquitto runs in a container, mount the config and cert directories as volumes:

```yaml
services:
  mosquitto:
    image: eclipse-mosquitto:latest
    restart: unless-stopped
    ports:
      - "1883:1883"
      - "8883:8883"
      - "2901:2901"
    volumes:
      - ./mosquitto/config:/mosquitto/config:ro
      - ./mosquitto/data:/mosquitto/data
      - ./mosquitto/log:/mosquitto/log
```

Place `mosquitto.conf` in `./mosquitto/config/` and the certificates in
`./mosquitto/config/certs/`.

---

## Verify the TLS listener

From any machine on the network:

```bash
# openssl s_client — check the TLS handshake
openssl s_client -connect <broker-ip>:8883 -servername mqtt001.solaxcloud.com

# mosquitto_pub — smoke test with a publish
mosquitto_pub -h <broker-ip> -p 8883 \
  --insecure \
  -t test/hello -m "world"
```

The `--insecure` flag skips server certificate verification in `mosquitto_pub`, mirroring what
the dongle does. A successful publish confirms port 8883 is working correctly.
