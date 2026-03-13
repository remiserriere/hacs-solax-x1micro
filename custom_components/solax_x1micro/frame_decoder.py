"""Binary frame decoder for SolaX Pocket WiFi MQTT data."""

from __future__ import annotations

import logging
import struct
from typing import Any

_LOGGER = logging.getLogger(__name__)


FRAME_MAGIC = b"$$"
FRAME_LENGTH = 107  # exact byte count for a real-time data frame
FUNC_CODE_REALTIME = 0x1C


def crc16_buypass(data: bytes) -> int:
    """Compute CRC-16/BUYPASS (also known as CRC-16/VERIFONE) checksum."""
    crc = 0x0000
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x8005) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


def decode_solax_frame(data: bytes) -> dict[str, Any] | None:
    """Decode a SolaX Cloud $$ binary frame (function code 0x1C, real-time data).

    Returns a dict of parsed values, or None if the frame is invalid.

    All multi-byte integers in the frame are little-endian.

    Frame layout (exactly 107 bytes for X1-Micro real-time data):
      0x00  2  Magic "$$"
      0x02  2  Total length (LE)
      0x04  1  Message type (0x08 = data upload)
      0x05  1  Protocol version
      0x06  1  Sequence number
      0x07  1  Function code (0x1C = real-time data)
      0x08 21  WiFi module SN (ASCII, null-padded)
      0x1D  1  Number of inverters
      0x1E  1  DSP firmware version
      0x1F  1  ARM firmware version
      0x20  1  Reserved
      0x21  1  Hardware version
      0x22  1  Firmware major
      0x23  1  Firmware minor
      0x24  1  Reserved
      0x25 21  Inverter SN (ASCII, null-padded)
      0x3A 47  Data section (see below)
      0x69  2  Checksum (BE)

    Data section (offsets relative to 0x3A) — layout is fixed regardless of mode:
      0   rated_power_W   ×1 W
      2   const_0x0205    invariant frame-type marker (always 0x0205)
      4   run_mode        enum (1=Normal, 0=Standby)
      5   reserved        always 0x0028
      7   grid_voltage_V  ×0.1 V
      9   grid_current_A  ×0.1 A  (single byte)
      10  padding         always 0x00
      11  ac_power_W      ×1 W    (always present; 0 W when no AC output)
      13  grid_freq_Hz    ×0.01 Hz
      15  vpv1_V          ×0.1 V  (always present; open-circuit V when tracking off)
      17  vpv2_V          ×0.1 V  (always present; open-circuit V when tracking off)
      19  ipv1_A          ×0.1 A  (valid only in dual-MPPT mode; 0 otherwise)
      21  ipv2_A          ×0.1 A  (valid only in dual-MPPT mode; 0 otherwise)
      23  ppv1_W          ×1 W    (valid only in dual-MPPT mode; 0 otherwise)
      25  ppv2_W          ×1 W    (valid only in dual-MPPT mode; 0 otherwise)
      27  mppt_mode       0=single-MPPT, 2=dual-MPPT
      29  e_total_kWh     ×0.1 kWh (always present)
      31  reserved        always 0
      33  e_today_kWh     ×0.1 kWh (always present)
      35  temperature1_C  ×1 °C
      37  temperature2_C  ×1 °C
      39  status_flags    0x0003 in normal operation

    Single-MPPT vs dual-MPPT on the X1-Micro 2-in-1:
      The X1-Micro has two independent PV inputs (MPPT1 and MPPT2). When both
      inputs produce enough power the inverter tracks them in dual-MPPT mode
      (mppt_mode=2) and the per-channel fields (ipv1/ipv2, ppv1/ppv2) contain
      meaningful individual measurements.

      When irradiance is too low (dawn/dusk), one input is heavily shaded, or
      one panel is disconnected, the inverter operates in single-MPPT mode
      (mppt_mode=0). The per-channel fields are 0 in this mode. Critically,
      ac_power, vpv1/vpv2, e_total, and e_today are present and valid in both
      modes at the same fixed offsets.

    Other observed frame types (all rejected by this decoder):
      79-byte  (0x4F): Compact start-up frame — function code 0x1C but missing
                       the inverter-SN section and the first 7 data bytes.
                       Sent during the initial boot sequence.
      64-byte  (0x40): Minimal handshake frame — function code 0x1C, contains
                       only rated_power + const_0x0205, no real-time data.
                       Part of the same boot sequence.
      46-byte  (0x2E): Firmware-version response — function code 0x0E,
                       contains an ASCII firmware string (e.g. "05.03").
      158-byte (0x9E): Configuration parameter dump — function code 0x1C but
                       47 extra bytes of parameter data appended.  The bytes at
                       the e_total/e_today offsets contain garbage (e.g. 2944,
                       yielding the spurious 294.4 kWh value seen in logs).
                       Rejected by the exact-length check below.
    """
    if len(data) != FRAME_LENGTH:
        _LOGGER.debug(
            "Frame length mismatch: got %d bytes, expected exactly %d",
            len(data),
            FRAME_LENGTH,
        )
        return None
    if data[:2] != FRAME_MAGIC:
        _LOGGER.debug("Frame magic mismatch: %s", data[:2].hex())
        return None
    if data[7] != FUNC_CODE_REALTIME:
        _LOGGER.debug(
            "Unexpected function code: 0x%02X (expected 0x%02X)",
            data[7],
            FUNC_CODE_REALTIME,
        )
        return None

    frame_len = len(data)
    expected_crc: int = struct.unpack_from(">H", data, frame_len - 2)[0]
    computed_crc: int = crc16_buypass(data[: frame_len - 2])
    if computed_crc != expected_crc:
        _LOGGER.debug(
            "CRC mismatch: computed 0x%04X, got 0x%04X",
            computed_crc,
            expected_crc,
        )
        return None

    total_len: int = struct.unpack_from("<H", data, 2)[0]
    wifi_sn: str = data[8:29].rstrip(b"\x00").decode("ascii", errors="replace")
    inv_sn: str = data[37:58].rstrip(b"\x00").decode("ascii", errors="replace")

    OFF = 0x3A

    def u16(off: int) -> int:
        return struct.unpack_from("<H", data, OFF + off)[0]

    def u8(off: int) -> int:
        return data[OFF + off]

    # Validate invariant fields that distinguish real-time data from other
    # 107-byte frame variants that might share the same magic and function code.
    if u16(2) != 0x0205:
        _LOGGER.debug("Unexpected frame-type marker at offset 2: 0x%04X", u16(2))
        return None
    if u16(5) != 0x0028:
        _LOGGER.debug("Unexpected reserved field at offset 5: 0x%04X", u16(5))
        return None

    # Determine operating mode from the mppt_mode field.
    # dual-MPPT (mppt_mode=2): both channels track independently; per-channel
    # fields (ipv1/ipv2, ppv1/ppv2) contain individual measurements.
    # single-MPPT (mppt_mode=0): one channel or low-power; per-channel fields
    # are 0 and reported as None.  ac_power, vpv1/vpv2, e_total, and e_today
    # are valid and populated at the same offsets in both modes.
    dual_mppt: bool = u16(27) == 2

    if dual_mppt:
        ipv1: float | None = u16(19) / 10.0
        ipv2: float | None = u16(21) / 10.0
        ppv1: int | None = u16(23)
        ppv2: int | None = u16(25)
        pdc_total: int | None = ppv1 + ppv2
    else:
        ipv1 = None
        ipv2 = None
        ppv1 = None
        ppv2 = None
        pdc_total = None

    return {
        "wifi_sn": wifi_sn,
        "inverter_sn": inv_sn,
        "rated_power_W": u16(0),
        "run_mode": u8(4),
        "grid_voltage_V": u16(7) / 10.0,
        "grid_current_A": u8(9) / 10.0,
        "ac_power_W": u16(11),
        "grid_freq_Hz": u16(13) / 100.0,
        "vpv1_V": u16(15) / 10.0,
        "vpv2_V": u16(17) / 10.0,
        "ipv1_A": ipv1,
        "ipv2_A": ipv2,
        "ppv1_W": ppv1,
        "ppv2_W": ppv2,
        "pdc_total_W": pdc_total,
        "e_total_kWh": u16(29) / 10.0,
        "e_today_kWh": u16(33) / 10.0,
        "temperature1_C": u16(35),
        "temperature2_C": u16(37),
        "status_flags": u16(39),
        "dual_mppt": dual_mppt,
        "total_len": total_len,
    }
