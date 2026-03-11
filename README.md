# SolaX X1-Micro — Home Assistant Integration

[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

A Home Assistant custom integration for the **SolaX X1-Micro 2 in 1** photovoltaic inverter,
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

> **TODO** — A detailed guide will be added in a future release.

The SolaX Pocket WiFi dongle connects to `mqtt001.solaxcloud.com:8883` (MQTTS).
To intercept its traffic locally you need to redirect this hostname to your local broker via a
custom DNS entry on the network the inverter is connected to.

**Quick summary:**
- On your local DNS server (e.g. Pi-hole, AdGuard Home, pfSense, or router custom hosts),
  create an **A record**: `mqtt001.solaxcloud.com → <your broker IP>`
- The dongle will then publish to your local broker instead of the SolaX cloud.

### 3. MQTT broker configuration

> **TODO** — A detailed broker configuration guide will be added in a future release.

The broker must accept plain MQTT (port 1883 or as configured) from the dongle.
Additional TLS / authentication configuration guidance will follow.

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

## Configuration

After installation, add the integration via **Settings → Devices & Services → Add Integration**
and search for **SolaX X1-Micro**.

You will be asked for:

| Field | Description | Example |
|-------|-------------|---------|
| **Serial Number** | Serial number printed on the SolaX Pocket WiFi dongle label | `30M341010L0619` |

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

## Versioning & Releases

Releases are published as [GitHub Releases](https://github.com/remiserriere/hacs-solax-x1micro/releases).
HACS compares the `version` field in `manifest.json` against the latest GitHub Release tag to detect whether an update is available.

> **Important:** Individual commits to the main branch are **not** tracked by HACS as separate versions.
> Only explicit GitHub Releases (tagged `v*`) are visible to HACS as installable versions.

### Creating a new release

**Option 1 — GitHub Actions UI (no git client needed):**

1. Go to **Actions → Release → Run workflow** in the repository.
2. Enter the version number (e.g. `1.2.0`).
3. Click **Run workflow** — the workflow will create the tag and the GitHub Release automatically.
4. Update the `version` field in `custom_components/solax_x1micro/manifest.json` to match.

**Option 2 — Tag push from the command line:**

```bash
# 1. Update the version field in custom_components/solax_x1micro/manifest.json, commit, and push.
# 2. Then tag and push:
git tag v1.2.0
git push origin v1.2.0
```

Both methods trigger the release workflow and publish a GitHub Release that HACS will detect.

---

## Contributing

Issues and pull requests are welcome on [GitHub](https://github.com/remiserriere/hacs-solax-x1micro).

---

## License

MIT
