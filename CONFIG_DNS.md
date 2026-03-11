# DNS Configuration — SolaX Pocket WiFi local MQTT interception

By design the SolaX Pocket WiFi dongle (ESP32-S2) resolves and connects to:

| Hostname | Role |
|----------|------|
| `mqtt001.solaxcloud.com` | Primary endpoint |
| `mqtt002.solaxcloud.com` | Fallback endpoint |
| `www.eu.solaxcloud.com` | Cloud portal (optional to redirect) |

The goal is to answer those DNS queries with the IP of your **local MQTT broker**, so the
dongle publishes to your own infrastructure instead of the SolaX cloud.

> **Tip:** Assign a **static IP** (or a DHCP reservation) to the inverter's WiFi dongle before
> setting up any per-client DNS rules. This ensures the rules continue to match after a reboot
> or a DHCP lease renewal.

In the examples below:

| Placeholder | Meaning |
|-------------|---------|
| `192.168.10.10` | IP of your local MQTT broker |
| `192.168.0.123` | Static/reserved IP of the SolaX Pocket WiFi dongle |
| `192.168.7.0/24` | VLAN subnet that contains the inverter (alternative) |

---

## Option 1 — Technitium DNS Server

[Technitium DNS Server](https://technitium.com/dns/) supports a **Split Horizon** application
that returns different A records depending on the source IP of the DNS query, giving you precise
per-client or per-VLAN control.

### 1.1 Install the Split Horizon app

1. Open the Technitium web UI and go to **Apps**.
2. Click **App Store** and install **Split Horizon**.

### 1.2 Create the zone

1. Go to **Zones** → **Add Zone**.
2. **Zone name:** `solaxcloud.com`
3. **Type:** `Conditional Forwarder Zone`
4. If this DNS server is the primary DNS server for your network, check
   **Forwarder — Use this server**.
5. Click **Add**.

### 1.3 Add DNS records

For each hostname to intercept (`mqtt001`, `mqtt002`, optionally `www.eu`):

1. Inside the `solaxcloud.com` zone, click **Add Record**.
2. Set the fields as follows:

   | Field | Value |
   |-------|-------|
   | **Name** | `mqtt001` (repeat for `mqtt002`, `www.eu`) |
   | **Type** | `APP` |
   | **App Name** | `Split Horizon` |
   | **Class Path** | `SplitHorizon.SimpleAddress` |
   | **Record Data** | *(see below)* |

3. **Record Data** — match by inverter IP:

   ```json
   {
     "192.168.0.123/32": [
       "192.168.10.10"
     ]
   }
   ```

   Or, if the inverter is isolated in its own VLAN, match by subnet instead:

   ```json
   {
     "192.168.7.0/24": [
       "192.168.10.10"
     ]
   }
   ```

With this configuration Technitium will respond with `192.168.10.10` only to DNS queries
originating from `192.168.0.123` (or from the `192.168.7.0/24` VLAN). All other clients will
receive the real upstream answer for `solaxcloud.com`.

---

## Option 2 — BIND9

Two approaches are described: a **simple zone override** (all DNS clients are redirected) and a
**split-horizon view** (only the inverter's IP or VLAN is redirected).

### 2.1 Simple zone override (all clients)

This is the easiest setup. Every DNS client that uses this BIND9 server will resolve
`mqtt001.solaxcloud.com` and `mqtt002.solaxcloud.com` to the local broker.

#### Zone declaration — `/etc/bind/named.conf.local`

```
zone "solaxcloud.com" {
    type master;
    file "/etc/bind/zones/db.solaxcloud.com";
};
```

#### Zone file — `/etc/bind/zones/db.solaxcloud.com`

```dns-zone
$TTL 60
@   IN  SOA  ns1.solaxcloud.com. hostmaster.solaxcloud.com. (
                2026031101  ; Serial (YYYYMMDDnn)
                3600        ; Refresh
                1800        ; Retry
                604800      ; Expire
                60 )        ; Negative Cache TTL

@       IN  NS   ns1.solaxcloud.com.
ns1     IN  A    192.168.1.1        ; IP of this BIND9 server

; Redirect inverter hostnames to the local MQTT broker
mqtt001 IN  A    192.168.10.10
mqtt002 IN  A    192.168.10.10

; Optional: redirect the cloud portal as well
; www.eu  IN  A  192.168.10.10
```

> Increment the **Serial** number every time you modify this file so that secondary nameservers
> (if any) pick up the change.

After editing, reload the zone:

```bash
sudo rndc reload solaxcloud.com
# or restart the service
sudo systemctl reload bind9
```

---

### 2.2 Split-horizon views (inverter-only redirection)

With BIND9 **views** you can serve different answers based on the client's source IP, exactly
like Technitium's Split Horizon app. Clients outside the ACL continue to receive the real
upstream responses.

#### ACL and view declarations — `/etc/bind/named.conf.local`

```
# Declare the ACL that matches the inverter
acl "solax_inverter" {
    192.168.0.123/32;   # static IP of the Pocket WiFi dongle
    # 192.168.7.0/24;   # alternatively: the whole inverter VLAN
};

# View served to the inverter: return the local broker IP
view "inverter" {
    match-clients { solax_inverter; };
    recursion yes;

    zone "solaxcloud.com" {
        type master;
        file "/etc/bind/zones/db.solaxcloud.com.local";
    };

    # Include any other zones needed for normal LAN resolution
    include "/etc/bind/named.conf.default-zones";
};

# View served to all other clients: forward to upstream
view "external" {
    match-clients { any; };
    recursion yes;

    zone "solaxcloud.com" {
        type forward;
        forwarders { 8.8.8.8; 1.1.1.1; };
        forward only;
    };

    include "/etc/bind/named.conf.default-zones";
};
```

> **Important:** when views are used, **every** zone (including `named.conf.default-zones`) must
> be declared inside a view. BIND9 will refuse to start if any zone is defined both inside and
> outside a view.

#### Zone file — `/etc/bind/zones/db.solaxcloud.com.local`

Identical to the simple-override zone file above:

```dns-zone
$TTL 60
@   IN  SOA  ns1.solaxcloud.com. hostmaster.solaxcloud.com. (
                2026031101
                3600
                1800
                604800
                60 )

@       IN  NS   ns1.solaxcloud.com.
ns1     IN  A    192.168.1.1

mqtt001 IN  A    192.168.10.10
mqtt002 IN  A    192.168.10.10
```

After editing, check the configuration syntax and reload:

```bash
sudo named-checkconf
sudo named-checkzone solaxcloud.com /etc/bind/zones/db.solaxcloud.com.local
sudo systemctl reload bind9
```

#### Verify

From a machine on the inverter's subnet (or using `dig`'s `+subnet` option):

```bash
# Should return 192.168.10.10 when queried from the inverter IP
dig @<bind9-server-ip> mqtt001.solaxcloud.com

# From another host — should return the real upstream answer
dig @<bind9-server-ip> mqtt001.solaxcloud.com
```

---

## Option 3 — Pi-hole

[Pi-hole](https://pi-hole.net/) is a popular network-wide DNS sinkhole, widely used as a LAN
DNS server. It is built on top of **dnsmasq** (via its FTL engine) and supports custom local DNS
records both through its web UI and through raw dnsmasq configuration files.

> **Per-client filtering note:** Pi-hole does not expose a built-in per-client DNS override
> feature equivalent to Technitium's Split Horizon or BIND9 views. In practice this is rarely a
> problem: `mqtt001.solaxcloud.com` and `mqtt002.solaxcloud.com` are SolaX-specific hostnames
> that no other device on a typical home network will ever query. An all-client override
> is therefore effectively equivalent to a per-inverter override.

---

### 3.1 Via the Pi-hole web UI (simplest)

1. Open the Pi-hole admin panel (`http://<pihole-ip>/admin`).
2. Go to **Local DNS → DNS Records**.
3. Add the following entries one by one:

   | Domain | IP |
   |--------|----|
   | `mqtt001.solaxcloud.com` | `192.168.10.10` |
   | `mqtt002.solaxcloud.com` | `192.168.10.10` |
   | `www.eu.solaxcloud.com` *(optional)* | `192.168.10.10` |

4. Each entry takes effect immediately — no restart is required.

> Pi-hole's Local DNS Records only support exact hostnames (no wildcards). Each hostname must
> be added individually.

---

### 3.2 Via a custom dnsmasq configuration file

This approach is useful if you manage Pi-hole via configuration management (Ansible, Docker
environment files, etc.) or if you want the records to survive a Pi-hole reinstall by keeping
them in a versioned file.

Create the file `/etc/dnsmasq.d/99-solax-local.conf`:

```
# Redirect SolaX cloud MQTT endpoints to the local broker (192.168.10.10)
address=/mqtt001.solaxcloud.com/192.168.10.10
address=/mqtt002.solaxcloud.com/192.168.10.10
# address=/www.eu.solaxcloud.com/192.168.10.10
```

Then restart the DNS resolver:

```bash
pihole restartdns
# or, on a systemd host:
sudo systemctl restart pihole-FTL
```

> Files in `/etc/dnsmasq.d/` take precedence over Pi-hole's own `custom.list`. Using a prefix
> like `99-` ensures the file is loaded last and wins over any conflicting entry.

---

### 3.3 Verify

```bash
# Query directly against the Pi-hole server
dig @<pihole-ip> mqtt001.solaxcloud.com

# Expected answer section:
# mqtt001.solaxcloud.com. 0 IN A 192.168.10.10
```

You can also confirm via the Pi-hole **Query Log** (`/admin/queries`): once the inverter is
powered and connected, DNS queries for `mqtt001.solaxcloud.com` should appear and show the
local broker address.
