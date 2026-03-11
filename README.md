# SolaX X1-Micro — Home Assistant Integration

[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

A Home Assistant custom integration for **SolaX X1-Micro** photovoltaic inverters,
communicating via MQTT through the SolaX Pocket WiFi dongle (ESP32-S2).

Data is received directly from your local MQTT broker — no cloud dependency.

---

## Features

- Automatically creates a HA **device** per inverter (identified by WiFi module serial number)
- **18 sensor entities** covering:
  - AC power, grid voltage, grid current, grid frequency
  - PV voltage / current / power per MPPT channel (MPPT1 & MPPT2)
  - Total DC power
  - Daily energy yield (E_Today) and lifetime energy yield (E_Total)
  - Heatsink temperatures (T1 & T2)
  - Rated power, run mode, inverter serial number (diagnostic)
- Supports **single-MPPT** (one panel) and **dual-MPPT** (two panels) operation;
  per-channel sensors return `unavailable` when only one MPPT is active
- Uses the native **Home Assistant MQTT integration** — no extra broker setup needed
- MQTT push model: data updates every ~5 minutes when the inverter is producing

---

## Prerequisites

### 1. Home Assistant MQTT Integration

The MQTT integration must be configured in Home Assistant and connected to your local broker.
See the [official MQTT documentation](https://www.home-assistant.io/integrations/mqtt/).

### 2. DNS redirect for the SolaX Pocket WiFi module

By design, the SolaX Pocket WiFi dongle communicates to `mqtt001.solaxcloud.com` with `mqtt002.solaxcloud.com` as fallback on two ports:

- **port 8883 (MQTTS)** — encrypted MQTT connection 
- **port 2901 (plain MQTT)** — additional unencrypted connection (maybe for legacy compatibility)

Both hostnames resolve to the same cloud servers; redirecting them to the local broker via DNS
intercepts traffic on both ports simultaneously.

The approach used here is **DNS interception**: rather than blocking cloud traffic at the
firewall level, we respond to the dongle's DNS queries for these hostnames with the IP address
of our own local MQTT broker. The dongle then connects to the local broker transparently,
without any firmware modification.

> It is strongly recommended to assign a **static IP** (or a DHCP reservation) to the
> inverter's WiFi dongle, so that DNS interception rules remain stable.

Several DNS server configurations are documented in [CONFIG_DNS.md](CONFIG_DNS.md):

| Option | DNS software | Notes |
|--------|-------------|-------|
| **1** | [Technitium DNS Server](https://technitium.com/dns/) | Split Horizon app — per-client granularity |
| **2** | [BIND9](https://www.isc.org/bind/) | Zone override or split-horizon views with ACLs |
| **3** | [Pi-hole](https://pi-hole.net/) | Local DNS Records via web UI, or custom dnsmasq config |

Refer to [CONFIG_DNS.md](CONFIG_DNS.md) for step-by-step instructions for each option.

### 3. MQTT broker configuration

The SolaX Pocket WiFi dongle uses two ports:

- **port 8883** — MQTTS (MQTT over TLS)
- **port 2901** — plain MQTT (unencrypted)

The local broker must expose a TLS listener on 8883 and a plain listener on 2901.

A complete Mosquitto configuration, including TLS listener setup and self-signed certificate
generation, is documented in [CONFIG_MQTT.md](CONFIG_MQTT.md).

---

## Installation

### Via HACS (recommended)

1. Open HACS in Home Assistant.
2. Click **Integrations → Custom repositories** (⋮ menu).
3. Add `https://github.com/remiserriere/hacs-solax-x1micro` as an **Integration**.
4. Search for **SolaX X1-Micro** and install it.
5. Restart Home Assistant.

### Manual

1. Copy the `custom_components/solax_x1micro/` directory into your HA
   `config/custom_components/` directory.
2. Restart Home Assistant.

---

## Supported models

| Key | Display name | Tested firmware
|-----|-------------|----------------|
| `x1_micro_2in1` | X1-Micro 2 in 1 | Wifi: 005.03 - DSP: 005.02

More models may be added in future releases.

---

## Configuration

After installation, add the integration via **Settings → Devices & Services → Add Integration**
and search for **SolaX X1-Micro**.

You will be asked for:

| Field | Description | Example |
|-------|-------------|---------|
| **Inverter Model** | Select your inverter model from the list | `X1-Micro 2 in 1` |
| **Serial Number** | Serial number printed on the SolaX Pocket WiFi dongle label | `30M341010L0619` |

> The serial number must be 5–21 alphanumeric characters (as printed on the WiFi dongle label).

The created HA device will be named **SolaX \<model\> (\<serial\>)** (e.g. `SolaX X1-Micro 2 in 1 (30M341010L0619)`).

The integration will subscribe to the following MQTT topics:

| Topic | Direction | Content |
|-------|-----------|---------|
| `loc/tsp/<serial>` | Inverter → HA | Binary real-time data frame (every ~5 min) |
| `loc/sup/<serial>` | Inverter → HA | `hello mqtt!` keepalive (every ~1 min) |

---

## Sensors

| Entity | Unit | Notes |
|--------|------|-------|
| AC Power | W | Total AC output power |
| Grid Voltage | V | |
| Grid Current | A | |
| Grid Frequency | Hz | |
| PV Voltage MPPT1 | V | `unavailable` in single-MPPT mode |
| PV Current MPPT1 | A | `unavailable` in single-MPPT mode |
| PV Power MPPT1 | W | `unavailable` in single-MPPT mode |
| PV Voltage MPPT2 | V | `unavailable` if MPPT2 not active |
| PV Current MPPT2 | A | `unavailable` if MPPT2 not active |
| PV Power MPPT2 | W | `unavailable` if MPPT2 not active |
| Total DC Power | W | Sum of MPPT1 + MPPT2; `unavailable` in single-MPPT mode |
| Energy Today | kWh | Daily yield; `unavailable` in single-MPPT mode |
| Energy Total | kWh | Lifetime yield; `unavailable` in single-MPPT mode |
| Temperature 1 | °C | Heatsink / ambient sensor |
| Temperature 2 | °C | Secondary thermal sensor |
| Rated Power *(diagnostic)* | W | Inverter nominal rating |
| Run Mode *(diagnostic)* | — | 1 = Normal, 0 = Standby |
| Inverter Serial Number *(diagnostic)* | — | Serial number from binary frame |

---

## Contributing

Issues and pull requests are welcome on [GitHub](https://github.com/remiserriere/hacs-solax-x1micro).

---

## License

MIT
