# SolaX Pocket WiFi — Boot Sequence Frames

This document describes the binary frames sent by the SolaX Pocket WiFi dongle
(ESP32-S2) during the inverter boot/start-up sequence.  These frames all arrive
on the `loc/tsp/<serial>` MQTT topic and share the same `$$` magic prefix, but
differ in length, function code, and content from the standard 107-byte real-time
data frame documented in the main source code.

> ⚠️ **Disclaimer — speculative analysis**
>
> The frame layouts and field mappings described in this document are the result
> of two complementary but imperfect methods:
>
> 1. **Reverse engineering of a legacy SolaX WiFi dongle firmware** (an older
>    firmware version, *not* the firmware currently running on the inverter
>    described here).  That binary was statically analysed to identify the `$$`
>    frame format, field offsets, and the CRC algorithm.
>
> 2. **Cross-validation against real-world values**: the field positions inferred
>    from the legacy firmware were verified by comparing decoded values (voltages,
>    frequencies, energy counters, temperatures) against physically plausible
>    values observed on a live installation.
>
> Neither of these methods constitutes a definitive protocol specification.  In
> particular:
>
> - The boot-sequence frame types (79 B, 64 B, 46 B, 158 B) have **not** been
>   validated against the source code or current firmware of the dongle.
> - Field names, units, and interpretations are **best-effort guesses** and may
>   be incorrect.
> - **No accuracy is guaranteed** until a complete reverse-engineering of the
>   current dongle firmware has been performed.
>
> Contributions, corrections, and captures from other hardware revisions are
> very welcome.

All multi-byte integers in the SolaX `$$` protocol are **little-endian** unless
otherwise noted.  CRC values are **big-endian** and are computed with the
CRC-16/BUYPASS algorithm (also known as CRC-16/VERIFONE, poly `0x8005`, init
`0x0000`, no reflection).

---

## Common Frame Header (bytes `0x00`–`0x24`)

All observed `$$` frames share a 37-byte header with an identical layout:

| Byte(s) | Field | Notes |
|---------|-------|-------|
| `0x00–0x01` | Magic `$$` | Always `24 24` |
| `0x02–0x03` | Total frame length (LE u16) | Equals `len(frame)` |
| `0x04` | Message type | `0x08` = data upload |
| `0x05` | Protocol version | `0x01` in all observed frames |
| `0x06` | Sequence number | Usually `0x01`; `0x02` for the firmware-version frame |
| `0x07` | Function code | `0x1C` = real-time / config; `0x0E` = firmware version |
| `0x08–0x1C` | WiFi module serial number | 21 bytes, ASCII, NUL-padded |
| `0x1D` | Number of inverters | `0x01` |
| `0x1E` | DSP firmware version (raw) | Raw integer — see notes below |
| `0x1F` | ARM firmware version (raw) | Varies by boot stage — see notes below |
| `0x20` | Reserved | `0x00` |
| `0x21` | Hardware version | `0x01` or `0x02` |
| `0x22` | Firmware version major | e.g. `0x02` |
| `0x23` | Firmware version minor | e.g. `0x19` = 25 → "2.25", or `0x07` = 7 → "2.7" |
| `0x24` | Reserved | `0x00` |

> **Note on ARM firmware version (`0x1F`):** This field changes across boot
> frames from the same boot sequence, which suggests the dongle reports the
> partially-initialised firmware context at the time of each message rather than
> a fixed version string.  Example values observed in a single boot sequence:
> `0x2C` (44) in the 79-byte frame, `0x1D` (29) and `0x7B` (123) in the 64-byte
> and 158-byte frames respectively, `0x0B` (11) in the 46-byte frame, `0x48`
> (72) in the standard 107-byte frame.  The `0x1E`/`0x1F` combination is
> therefore unreliable during boot; only the 107-byte real-time frame carries
> stable firmware version information.

---

## Frame Type Summary

| Length | Hex | Function code | Contains | Stage |
|--------|-----|---------------|----------|-------|
| **79 B** | `0x4F` | `0x1C` | Partial real-time data (no inverter SN, no rated_power/run_mode) | Very early boot |
| **64 B** | `0x40` | `0x1C` | Inverter SN + rated_power only | Early boot (handshake) |
| **46 B** | `0x2E` | `0x0E` | WiFi firmware version string | Early boot |
| **158 B** | `0x9E` | `0x1C` | Inverter SN + config register address list | Mid-boot config dump |
| **107 B** | `0x6B` | `0x1C` | Full real-time data | Normal operation |

---

## Frame 1 — 79-byte Compact Real-Time Frame

### Description

Sent during the very first seconds of the boot sequence (observed at
`06:58:01` and `06:58:06` in the example log).  Two copies are emitted about
5 seconds apart.

It shares the function code `0x1C` with the standard 107-byte real-time frame
but is shorter because:

- The **inverter serial-number** section (21 bytes at `0x25–0x39`) is absent.
- The first 7 bytes of the standard data section (`rated_power`, `const_0x0205`,
  `run_mode`, `reserved`) are absent.

The remaining 40 bytes of data (starting at `0x25`) are in the same layout as
the standard real-time data section from offset `+0x07` onwards, i.e. starting
with `grid_voltage_V`.

At boot, AC power and PV currents are zero (inverter not yet injecting), PV
voltages show the open-circuit voltage of the panels, and `e_total` already
reflects the lifetime energy counter read from non-volatile memory.

### Example frames

```
Frame A (06:58:01):
24244F000801011C33304D3334313031304C3036313900000000000000
010E2C00010128003F09000000008A133B013B01000000000000000000
007D00000000000100010003000000000000000D7D

Frame B (06:58:06):
24244F000801011C33304D3334313031304C3036313900000000000000
010E2C00010128003E09000000008A133C013C01000000000000000000
007D0000000000010001000300000000000000C614
```

### Layout

Header bytes `0x00–0x24` follow the common header described above.

| Byte(s) | Field | Frame A raw | Frame B raw | Frame A decoded | Frame B decoded |
|---------|-------|-------------|-------------|-----------------|-----------------|
| `0x02–0x03` | Frame length | `4F 00` | `4F 00` | 79 | 79 |
| `0x07` | Function code | `1C` | `1C` | 0x1C | 0x1C |
| `0x08–0x1C` | WiFi SN | `33 30 4D ...` | `33 30 4D ...` | `30M341010L0619` | `30M341010L0619` |
| `0x1E` | DSP FW (raw) | `0E` | `0E` | 14 | 14 |
| `0x1F` | ARM FW (raw) | `2C` | `2C` | 44 | 44 |
| `0x21` | HW version | `01` | `01` | 1 | 1 |
| `0x22–0x23` | FW version | `01 28` | `01 28` | 1.40 | 1.40 |

Data section — starts at byte `0x25` (corresponds to `+0x07` in the standard frame):

| Byte(s) | Std offset | Field | Frame A raw | Frame B raw | Frame A decoded | Frame B decoded |
|---------|-----------|-------|-------------|-------------|-----------------|-----------------|
| `0x25–0x26` | `+0x07` | Grid voltage (×0.1 V) | `3F 09` | `3E 09` | 236.7 V | 236.6 V |
| `0x27` | `+0x09` | Grid current (×0.1 A) | `00` | `00` | 0.0 A | 0.0 A |
| `0x28` | `+0x0A` | Padding | `00` | `00` | — | — |
| `0x29–0x2A` | `+0x0B` | AC power (W) | `00 00` | `00 00` | 0 W | 0 W |
| `0x2B–0x2C` | `+0x0D` | Grid frequency (×0.01 Hz) | `8A 13` | `8A 13` | 50.02 Hz | 50.02 Hz |
| `0x2D–0x2E` | `+0x0F` | Vpv1 (×0.1 V) | `3B 01` | `3C 01` | 31.5 V | 31.6 V |
| `0x2F–0x30` | `+0x11` | Vpv2 (×0.1 V) | `3B 01` | `3C 01` | 31.5 V | 31.6 V |
| `0x31–0x32` | `+0x13` | Ipv1 (×0.1 A) | `00 00` | `00 00` | 0.0 A | 0.0 A |
| `0x33–0x34` | `+0x15` | Ipv2 (×0.1 A) | `00 00` | `00 00` | 0.0 A | 0.0 A |
| `0x35–0x36` | `+0x17` | Ppv1 (W) | `00 00` | `00 00` | 0 W | 0 W |
| `0x37–0x38` | `+0x19` | Ppv2 (W) | `00 00` | `00 00` | 0 W | 0 W |
| `0x39–0x3A` | `+0x1B` | MPPT mode | `00 00` | `00 00` | 0 (single) | 0 (single) |
| `0x3B–0x3C` | `+0x1D` | E_total (×0.1 kWh) | `7D 00` | `7D 00` | 12.5 kWh | 12.5 kWh |
| `0x3D–0x3E` | `+0x1F` | Reserved | `00 00` | `00 00` | — | — |
| `0x3F–0x40` | `+0x21` | E_today (×0.1 kWh) | `00 00` | `00 00` | 0.0 kWh | 0.0 kWh |
| `0x41–0x42` | `+0x23` | Temperature 1 (°C) | `01 00` | `01 00` | 1 °C | 1 °C |
| `0x43–0x44` | `+0x25` | Temperature 2 (°C) | `01 00` | `01 00` | 1 °C | 1 °C |
| `0x45–0x46` | `+0x27` | Status flags | `03 00` | `03 00` | 0x0003 | 0x0003 |
| `0x47–0x4C` | `+0x29` | Tail (6 B, all zero) | `00 00 00 00 00 00` | `00 00 00 00 00 00` | — | — |
| `0x4D–0x4E` | — | CRC (BE) | `0D 7D` | `C6 14` | 0x0D7D ✓ | 0xC614 ✓ |

> **Observation:** Both PV voltages (~31.5 V) are the open-circuit voltage of
> the panels at dawn — the inverter has not yet started MPPT tracking.  The
> `e_total` value (12.5 kWh) is the lifetime yield read from flash at boot.
> Status `0x0003` is the same value seen in normal operation.

---

## Frame 2 — 64-byte Minimal Handshake Frame

### Description

Sent during the early boot sequence (observed at `06:58:11`, ~5 s after the
compact frame).  Contains only the header, the full inverter serial number, and
the first two data words (`rated_power` and `const_0x0205`).  No real-time
sensor data is present.

This is likely the dongle announcing the connected inverter's identity and rated
power to the server before real-time data is available.

### Example frame

```
24244000080101 1C 33304D3334313031304C3036313900000000000000
010E1D000102190033304D3334313031304C3036313900000000000000
E8030502C592
```

### Layout

| Byte(s) | Field | Raw | Decoded |
|---------|-------|-----|---------|
| `0x02–0x03` | Frame length | `40 00` | 64 |
| `0x07` | Function code | `1C` | 0x1C |
| `0x08–0x1C` | WiFi SN | `33 30 4D ...` | `30M341010L0619` |
| `0x1E` | DSP FW (raw) | `0E` | 14 |
| `0x1F` | ARM FW (raw) | `1D` | 29 |
| `0x21` | HW version | `01` | 1 |
| `0x22–0x23` | FW version | `02 19` | 2.25 |
| `0x25–0x39` | Inverter SN | `33 30 4D ...` | `30M341010L0619` |
| `0x3A–0x3B` | Rated power (W) | `E8 03` | 1000 W |
| `0x3C–0x3D` | Frame-type marker | `05 02` | 0x0205 |
| `0x3E–0x3F` | CRC (BE) | `C5 92` | 0xC592 ✓ |

> **Observation:** Both WiFi SN and Inverter SN are identical
> (`30M341010L0619`), confirming that this inverter's serial number was read
> from the device.  The rated power of 1000 W identifies this as a 1 kW
> X1-Micro model.

---

## Frame 3 — 46-byte Firmware-Version Response

### Description

Sent immediately after the minimal handshake (observed at `06:58:12`, sequence
number `0x02`).  Uses function code `0x0E` (firmware version query/response)
rather than `0x1C`.  The payload contains the WiFi module's firmware version
string in ASCII (`005.03`).

### Example frame

```
24242E00080102 0E 33304D3334313031304C3036313900000000000000
010E0B000102070 0 0E3030352E3033843F
```

### Layout

| Byte(s) | Field | Raw | Decoded |
|---------|-------|-----|---------|
| `0x02–0x03` | Frame length | `2E 00` | 46 |
| `0x06` | Sequence number | `02` | 2 (note: not 1) |
| `0x07` | Function code | `0E` | 0x0E (firmware version) |
| `0x08–0x1C` | WiFi SN | `33 30 4D ...` | `30M341010L0619` |
| `0x1E` | DSP FW (raw) | `0E` | 14 |
| `0x1F` | ARM FW (raw) | `0B` | 11 |
| `0x21` | HW version | `01` | 1 |
| `0x22–0x23` | FW version | `02 07` | 2.7 |
| `0x25` | Response length byte | `0E` | 14 |
| `0x26–0x2B` | Firmware version string | `30 30 35 2E 30 33` | `005.03` (ASCII) |
| `0x2C–0x2D` | CRC (BE) | `84 3F` | 0x843F ✓ |

> **Observation:** The firmware string `005.03` matches the WiFi firmware version
> documented in the README (`Wifi: 005.03`).  The `FW version` field in the
> header shows `2.7` in this frame (different from the `2.25` seen in the 64-byte
> frame), which further illustrates that the header firmware fields are not
> reliable during the boot sequence.  The `0x0E` byte at `0x25` may be a
> sub-function echo (matching the function code), a length field, or a DSP
> firmware cross-reference (DSP FW = 14 = 0x0E); its precise role is unclear.

---

## Frame 4 — 158-byte Configuration Parameter Dump

### Description

Sent about 5–6 seconds after the firmware-version frame (observed at
`06:58:17`).  The frame header and inverter-SN section are identical to the
standard 107-byte frame, and the first four bytes of the data section
(`rated_power` and `const_0x0205`) are also correct.  However, from byte `+0x04`
onwards the data is **not real-time sensor values** — it is a configuration /
register-address dump.

If the standard 107-byte decoder is naïvely applied to this frame, the
`e_total` and `e_today` fields would read spurious values (e.g. 294.4 kWh and
345.6 kWh respectively), which are garbage produced by reinterpreting the config
bytes.

### Example frame

```
24249E000801011C33304D3334313031304C30363139000000000000
00010E7B000202190033304D3334313031304C303631390000000000
0000E8030502035B0020008001800280038004800580068007800880
09800A800B800C800D800E800F801080118012801380148015801680
1780188019801A801B801C801D801E801F8000000000070000000000
00000000000000000000000000000000431F
```

### Layout — header and known fields

| Byte(s) | Field | Raw | Decoded |
|---------|-------|-----|---------|
| `0x02–0x03` | Frame length | `9E 00` | 158 |
| `0x07` | Function code | `1C` | 0x1C |
| `0x08–0x1C` | WiFi SN | `33 30 4D ...` | `30M341010L0619` |
| `0x1E` | DSP FW (raw) | `0E` | 14 |
| `0x1F` | ARM FW (raw) | `7B` | 123 |
| `0x21` | HW version | `02` | 2 |
| `0x22–0x23` | FW version | `02 19` | 2.25 |
| `0x25–0x39` | Inverter SN | `33 30 4D ...` | `30M341010L0619` |
| `0x3A–0x3B` | Rated power (W) | `E8 03` | 1000 W |
| `0x3C–0x3D` | Frame-type marker | `05 02` | 0x0205 |

### Layout — config data section (bytes `0x3E`–`0x9B`)

From byte `0x3E` (data offset `+0x04`) onwards the bytes are configuration data
rather than real-time values.  The standard offsets for `run_mode`, `reserved`,
`grid_voltage`, etc. therefore contain garbage if decoded as real-time data.

The 94 config bytes are:

```
03 5B 00 20 00 80 01 80 02 80 03 80 04 80 05 80
06 80 07 80 08 80 09 80 0A 80 0B 80 0C 80 0D 80
0E 80 0F 80 10 80 11 80 12 80 13 80 14 80 15 80
16 80 17 80 18 80 19 80 1A 80 1B 80 1C 80 1D 80
1E 80 1F 80 00 00 00 00 07 00 00 00 00 00 00 00
00 00 00 00 00 00 00 00 00 00 00 00 00 00
```

| Offset in config | Raw bytes | LE u16 | Notes |
|-----------------|-----------|--------|-------|
| `+0x00` | `03` | — | Sub-command byte; possibly `0x03` = "read holding registers" |
| `+0x01` | `5B` | — | Payload length or related byte; 0x5B = 91 |
| `+0x02–0x03` | `00 20` | 0x0020 = 32 | Number of register addresses that follow |
| `+0x04` | `00` | — | Padding / high byte |
| `+0x05–0x06` | `80 01` | `0x8001` = reg 1 | Register address 0x8001 |
| `+0x07–0x08` | `80 02` | `0x8002` = reg 2 | Register address 0x8002 |
| … | … | … | … (incrementing) |
| `+0x43–0x44` | `80 1F` | `0x801F` = reg 31 | Register address 0x801F |
| `+0x45–0x46` | `00 00` | 0x0000 | — |
| `+0x47–0x48` | `00 00` | 0x0000 | — |
| `+0x49–0x4A` | `07 00` | 0x0007 | Unknown |
| `+0x4B–0x5D` | `00 …` | 0x0000 | All zeros |

**Expanded register address list (32 entries, LE u16):**

| Entry | Raw bytes | Value |
|-------|-----------|-------|
| 0 | `00 80` | `0x8000` |
| 1 | `01 80` | `0x8001` |
| 2 | `02 80` | `0x8002` |
| 3 | `03 80` | `0x8003` |
| 4 | `04 80` | `0x8004` |
| 5 | `05 80` | `0x8005` |
| 6 | `06 80` | `0x8006` |
| 7 | `07 80` | `0x8007` |
| 8 | `08 80` | `0x8008` |
| 9 | `09 80` | `0x8009` |
| 10 | `0A 80` | `0x800A` |
| 11 | `0B 80` | `0x800B` |
| 12 | `0C 80` | `0x800C` |
| 13 | `0D 80` | `0x800D` |
| 14 | `0E 80` | `0x800E` |
| 15 | `0F 80` | `0x800F` |
| 16 | `10 80` | `0x8010` |
| 17 | `11 80` | `0x8011` |
| 18 | `12 80` | `0x8012` |
| 19 | `13 80` | `0x8013` |
| 20 | `14 80` | `0x8014` |
| 21 | `15 80` | `0x8015` |
| 22 | `16 80` | `0x8016` |
| 23 | `17 80` | `0x8017` |
| 24 | `18 80` | `0x8018` |
| 25 | `19 80` | `0x8019` |
| 26 | `1A 80` | `0x801A` |
| 27 | `1B 80` | `0x801B` |
| 28 | `1C 80` | `0x801C` |
| 29 | `1D 80` | `0x801D` |
| 30 | `1E 80` | `0x801E` |
| 31 | `1F 80` | `0x801F` |

> **Interpretation:** This appears to be the dongle requesting (or confirming)
> a read of 32 consecutive inverter registers in the `0x8000`–`0x801F` range,
> which is the register block used by SolaX's internal Modbus-like bus for
> real-time data.  The value `0x0007` near the end (at config `+0x49`) is of
> unknown meaning.  The real-time data from these 32 registers is what
> ultimately populates the standard 107-byte frame once the inverter finishes
> its boot sequence.

### CRC

| Byte(s) | Raw | Decoded |
|---------|-----|---------|
| `0x9C–0x9D` | `43 1F` | 0x431F ✓ |

---

## Frame 5 — 107-byte Standard Real-Time Frame (reference)

Included here for comparison.  This is the frame type decoded by the integration
in normal operation.  It appears after the boot sequence is complete (first seen
at `06:58:22` in the example log, ~30 s after boot started, and subsequently on
a regular ~5-minute interval during operation).

### Example frames

```
Frame A (06:58:22):
24246B000801011C33304D3334313031304C3036313900000000000000
010E48000202190033304D3334313031304C3036313900000000000000
E80305020128003C090000000087133F013E01000000000000000000
007D00000000000100010003000000000000004147

Frame B (07:01:31, normal operation):
24246B000801011C33304D3334313031304C3036313900000000000000
010E48000202190033304D3334313031304C3036313900000000000000
E803050201280034090000000086134A014A01000000000000000000
007D00000000000100010003000000000000005806
```

### Decoded values (standard layout)

| Field | Frame A (06:58:22) | Frame B (07:01:31) | Notes |
|-------|---------------------|---------------------|-------|
| WiFi SN | `30M341010L0619` | `30M341010L0619` | |
| Inverter SN | `30M341010L0619` | `30M341010L0619` | |
| DSP FW (raw) | 14 | 14 | 0x0E |
| ARM FW (raw) | 72 | 72 | 0x48 |
| HW version | 2 | 2 | |
| FW version | 2.25 | 2.25 | |
| Rated power | 1000 W | 1000 W | |
| Run mode | 1 (Normal) | 1 (Normal) | |
| Grid voltage | 236.4 V | 235.6 V | |
| Grid current | 0.0 A | 0.0 A | No AC output yet |
| AC power | 0 W | 0 W | |
| Grid frequency | 49.99 Hz | 49.98 Hz | |
| Vpv1 | 31.9 V | 33.0 V | Open-circuit / dawn |
| Vpv2 | 31.8 V | 33.0 V | |
| Ipv1 | — (single-MPPT) | — (single-MPPT) | |
| Ipv2 | — (single-MPPT) | — (single-MPPT) | |
| MPPT mode | 0 (single) | 0 (single) | |
| E_total | 12.5 kWh | 12.5 kWh | |
| E_today | 0.0 kWh | 0.0 kWh | |
| Temperature 1 | 1 °C | 1 °C | |
| Temperature 2 | 1 °C | 1 °C | |
| Status flags | 0x0003 | 0x0003 | |

---

## Boot Sequence Timeline (example log)

```
06:58:01  79-byte compact frame  (CRC OK)  — grid live, panels at OCV, no output
06:58:06  79-byte compact frame  (CRC OK)  — same; slight panel voltage increase
06:58:11  64-byte minimal frame  (CRC OK)  — inverter SN + rated_power handshake
06:58:12  46-byte firmware frame (CRC OK)  — WiFi firmware = "005.03"
06:58:17 158-byte config frame   (CRC OK)  — register address list (0x8000–0x801F)
06:58:22 107-byte standard frame (CRC OK)  — first full real-time data frame
07:01:31 107-byte standard frame (CRC OK)  — subsequent normal update (~3 min later)
```

---

## CRC Reference

All frames use **CRC-16/BUYPASS** (poly `0x8005`, init `0x0000`, no input or
output reflection, no final XOR).  The CRC covers all bytes from the first `$`
to the last data byte, **excluding** the 2 CRC bytes themselves.  The CRC is
appended in **big-endian** order (high byte first).

Python reference implementation:

```python
def crc16_buypass(data: bytes) -> int:
    crc = 0x0000
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x8005) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc
```

---

## Interactive Frame Decoder (Python helper script)

Copy the block below into a `.py` file (or run it directly with `python3`) to
decode frames interactively.  Paste the hex of any captured frame on one line
(spaces are ignored), press Enter, and the script prints the decoded fields.
Press **CTRL-C** to quit.

The script recognises all five frame types documented above, reports
**`wrong crc`** for a checksum mismatch, and **`frame unknown`** for any
length that is not in the table.

> ⚠️ **Reminder:** field interpretations are speculative — see the disclaimer
> at the top of this document.

```python
#!/usr/bin/env python3
"""
SolaX Pocket WiFi — interactive frame decoder.

Paste a hex frame on one line (spaces are ignored), press Enter.
Repeat for each subsequent frame.  Press CTRL-C to quit.

Recognised frame types
  107 B (0x6B)  Standard real-time frame         FC=0x1C
   79 B (0x4F)  Compact real-time frame (boot)   FC=0x1C
   64 B (0x40)  Minimal handshake (boot)          FC=0x1C
   46 B (0x2E)  Firmware-version response (boot)  FC=0x0E
  158 B (0x9E)  Configuration dump (boot)         FC=0x1C

All other lengths  →  "frame unknown"
Failed CRC         →  "wrong crc"
"""

import struct
import sys


# ---------------------------------------------------------------------------
# CRC-16/BUYPASS  (poly 0x8005, init 0x0000, no reflection, no final XOR)
# ---------------------------------------------------------------------------
def crc16_buypass(data: bytes) -> int:
    crc = 0
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x8005 if crc & 0x8000 else crc << 1) & 0xFFFF
    return crc


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def _u16(f: bytes, off: int) -> int:
    return struct.unpack_from("<H", f, off)[0]


def _sn(raw: bytes) -> str:
    return raw.rstrip(b"\x00").decode("ascii", errors="replace")


# ---------------------------------------------------------------------------
# Common header printer (bytes 0x00–0x24)
# ---------------------------------------------------------------------------
def _print_header(f: bytes) -> None:
    print(f"  WiFi SN      : {_sn(f[0x08:0x1D])}")
    print(f"  Sequence     : {f[0x06]}")
    print(f"  Func code    : 0x{f[0x07]:02X}")
    print(f"  DSP FW (raw) : {f[0x1E]}")
    print(f"  ARM FW (raw) : {f[0x1F]}  (varies across boot frames; stable only in the 107 B frame)")
    print(f"  HW version   : {f[0x21]}")
    print(f"  FW version   : {f[0x22]}.{f[0x23]}")


# ---------------------------------------------------------------------------
# Shared real-time sensor block
#
# Relative offsets (all LE u16 unless noted):
#   +0x00  grid_voltage  x0.1 V
#   +0x02  grid_current  u8  x0.1 A   (+0x03 padding)
#   +0x04  AC_power      W
#   +0x06  grid_freq     x0.01 Hz
#   +0x08  Vpv1          x0.1 V
#   +0x0A  Vpv2          x0.1 V
#   +0x0C  Ipv1          x0.1 A
#   +0x0E  Ipv2          x0.1 A
#   +0x10  Ppv1          W
#   +0x12  Ppv2          W
#   +0x14  MPPT_mode
#   +0x16  E_total       x0.1 kWh
#   +0x18  (reserved 2 B)
#   +0x1A  E_today       x0.1 kWh
#   +0x1C  T1            deg C
#   +0x1E  T2            deg C
#   +0x20  status_flags
#   +0x22  tail (6 B, ignored)
#
# base = 0x25 for the 79 B compact frame (no inverter SN / preamble)
# base = 0x41 for the 107 B standard frame (= 0x3A + 7 bytes of preamble)
# ---------------------------------------------------------------------------
def _print_sensor_block(f: bytes, base: int) -> None:
    print(f"  Grid voltage  : {_u16(f, base + 0x00) / 10:.1f} V")
    print(f"  Grid current  : {f[base + 0x02] / 10:.1f} A")
    print(f"  AC power      : {_u16(f, base + 0x04)} W")
    print(f"  Grid frequency: {_u16(f, base + 0x06) / 100:.2f} Hz")
    print(f"  Vpv1          : {_u16(f, base + 0x08) / 10:.1f} V")
    print(f"  Vpv2          : {_u16(f, base + 0x0A) / 10:.1f} V")
    print(f"  Ipv1          : {_u16(f, base + 0x0C) / 10:.1f} A")
    print(f"  Ipv2          : {_u16(f, base + 0x0E) / 10:.1f} A")
    print(f"  Ppv1          : {_u16(f, base + 0x10)} W")
    print(f"  Ppv2          : {_u16(f, base + 0x12)} W")
    print(f"  MPPT mode     : {_u16(f, base + 0x14)}")
    print(f"  E_total       : {_u16(f, base + 0x16) / 10:.1f} kWh")
    print(f"  E_today       : {_u16(f, base + 0x1A) / 10:.1f} kWh")
    print(f"  Temperature 1 : {_u16(f, base + 0x1C)} C")
    print(f"  Temperature 2 : {_u16(f, base + 0x1E)} C")
    print(f"  Status flags  : 0x{_u16(f, base + 0x20):04X}")


# ---------------------------------------------------------------------------
# Per-type decoders
# ---------------------------------------------------------------------------
def _decode_107(f: bytes) -> None:
    print("  Type         : 107 B — Standard real-time frame")
    _print_header(f)
    print(f"  Inverter SN  : {_sn(f[0x25:0x3A])}")
    print(f"  Rated power  : {_u16(f, 0x3A)} W")
    print(f"  Run mode     : {f[0x3E]}")
    _print_sensor_block(f, 0x41)


def _decode_79(f: bytes) -> None:
    print("  Type         : 79 B — Compact real-time frame (boot)")
    _print_header(f)
    print("  (no inverter SN / rated_power / run_mode in this frame type)")
    _print_sensor_block(f, 0x25)


def _decode_64(f: bytes) -> None:
    print("  Type         : 64 B — Minimal handshake (boot)")
    _print_header(f)
    print(f"  Inverter SN  : {_sn(f[0x25:0x3A])}")
    print(f"  Rated power  : {_u16(f, 0x3A)} W")
    print(f"  Marker       : 0x{_u16(f, 0x3C):04X}")


def _decode_46(f: bytes) -> None:
    print("  Type         : 46 B — Firmware-version response (boot)")
    _print_header(f)
    fw_str = f[0x26:0x2C].decode("ascii", errors="replace")
    print(f"  WiFi FW ver  : {fw_str}")


def _decode_158(f: bytes) -> None:
    print("  Type         : 158 B — Configuration parameter dump (boot)")
    _print_header(f)
    print(f"  Inverter SN  : {_sn(f[0x25:0x3A])}")
    print(f"  Rated power  : {_u16(f, 0x3A)} W")
    cfg = f[0x3E:]
    print(f"  Sub-command  : 0x{cfg[0]:02X}")
    regs = [struct.unpack_from("<H", cfg, 4 + i * 2)[0] for i in range(32)]
    print(f"  Registers    : 0x{regs[0]:04X}–0x{regs[-1]:04X}  ({len(regs)} entries)")


_DECODERS = {
    107: _decode_107,
    79:  _decode_79,
    64:  _decode_64,
    46:  _decode_46,
    158: _decode_158,
}


# ---------------------------------------------------------------------------
# Main decode entry-point
# ---------------------------------------------------------------------------
def decode_frame(raw_hex: str) -> None:
    raw_hex = "".join(raw_hex.split())   # strip all whitespace / newlines
    if not raw_hex:
        return

    try:
        frame = bytes.fromhex(raw_hex)
    except ValueError as exc:
        print(f"  parse error: {exc}")
        return

    actual_len = len(frame)
    if actual_len < 4:
        print("frame unknown  (too short)")
        return
    if frame[0:2] != b"$$":
        print("frame unknown  (missing $$ magic)")
        return

    reported_len = _u16(frame, 2)
    if reported_len != actual_len:
        print(f"frame unknown  (length field {reported_len} != actual {actual_len} bytes)")
        return

    calc_crc  = crc16_buypass(frame[:-2])
    frame_crc = struct.unpack_from(">H", frame, actual_len - 2)[0]
    if calc_crc != frame_crc:
        print(f"wrong crc  (computed 0x{calc_crc:04X}, frame carries 0x{frame_crc:04X})")
        return

    decoder = _DECODERS.get(actual_len)
    if decoder is None:
        print(f"frame unknown  ({actual_len} B — CRC OK but length not recognised)")
        return

    print(f"  CRC OK       : 0x{frame_crc:04X}")
    decoder(frame)


# ---------------------------------------------------------------------------
# Interactive loop
# ---------------------------------------------------------------------------
def main() -> None:
    print("SolaX frame decoder — paste hex (spaces ignored), press Enter.")
    print("CTRL-C to quit.\n")
    while True:
        try:
            raw = input("frame> ")
        except (EOFError, KeyboardInterrupt):
            print()
            break
        decode_frame(raw)
        print()


if __name__ == "__main__":
    main()
```
