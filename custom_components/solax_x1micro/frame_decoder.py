"""Binary frame decoder for SolaX Pocket WiFi MQTT data."""
from __future__ import annotations

import logging
import struct
from typing import Any

_LOGGER = logging.getLogger(__name__)


FRAME_MAGIC = b"$$"
FRAME_MIN_LENGTH = 107
FUNC_CODE_REALTIME = 0x1C


def decode_solax_frame(data: bytes) -> dict[str, Any] | None:
    """Decode a SolaX Cloud $$ binary frame (function code 0x1C, real-time data).

    Returns a dict of parsed values, or None if the frame is invalid.

    All multi-byte integers in the frame are little-endian.

    Frame layout (107 bytes for X1-Micro):
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
      0x65  2  Checksum (LE)

    Data section (offsets relative to 0x3A):
      0   rated_power_W   ×1 W
      2   const_0x0205    frame type/format identifier (invariant)
      4   run_mode        enum (1=Normal, 0=Standby)
      5   reserved        always 0x0028
      7   grid_voltage_V  ×0.1 V
      9   grid_current_A  ×0.1 A  (single byte)
      10  padding         always 0x00
      11  ac_power_dual_W ×1 W    (AC power when dual-MPPT active)
      13  grid_freq_Hz    ×0.01 Hz
      15  vpv1_V          ×0.1 V  (also used for Pac in single-MPPT mode)
      17  vpv2_V          ×0.1 V
      19  ipv1_A          ×0.1 A
      21  ipv2_A          ×0.1 A
      23  ppv1_W          ×1 W
      25  ppv2_W          ×1 W
      27  mppt_mode       0=single-MPPT, 2=dual-MPPT
      29  e_total_kWh     ×0.1 kWh (only in dual-MPPT mode)
      31  reserved        always 0
      33  e_today_kWh     ×0.1 kWh (only in dual-MPPT mode)
      35  temperature1_C  ×1 °C
      37  temperature2_C  ×1 °C
      39  status_flags    flags (0x01=single-MPPT, 0x03=dual-MPPT)
    """
    if len(data) < FRAME_MIN_LENGTH:
        _LOGGER.debug(
            "Frame too short: got %d bytes, expected at least %d",
            len(data),
            FRAME_MIN_LENGTH,
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

    total_len: int = struct.unpack_from("<H", data, 2)[0]
    wifi_sn: str = data[8:29].rstrip(b"\x00").decode("ascii", errors="replace")
    inv_sn: str = data[37:58].rstrip(b"\x00").decode("ascii", errors="replace")

    OFF = 0x3A

    def u16(off: int) -> int:
        return struct.unpack_from("<H", data, OFF + off)[0]

    def u8(off: int) -> int:
        return data[OFF + off]

    vpv1 = u16(15) / 10.0
    vpv2 = u16(17) / 10.0

    # Detect operating mode: dual-MPPT when both PV channels have voltage
    dual_mppt = vpv1 > 0.0 and vpv2 > 0.0

    if dual_mppt:
        pac = u16(11)
        ipv1: float | None = u16(19) / 10.0
        ipv2: float | None = u16(21) / 10.0
        ppv1: int | None = u16(23)
        ppv2: int | None = u16(25)
        pdc_total: int | None = ppv1 + ppv2
        e_total: float | None = u16(29) / 10.0
        e_today: float | None = u16(33) / 10.0
        vpv1_out: float | None = vpv1
        vpv2_out: float | None = vpv2
    else:
        # Single-MPPT mode: Pac is encoded at d[15-16]; per-channel fields are 0
        pac = u16(15)
        ipv1 = None
        ipv2 = None
        ppv1 = None
        ppv2 = None
        pdc_total = None
        e_total = None
        e_today = None
        vpv1_out = None
        vpv2_out = None

    return {
        "wifi_sn": wifi_sn,
        "inverter_sn": inv_sn,
        "rated_power_W": u16(0),
        "run_mode": u8(4),
        "grid_voltage_V": u16(7) / 10.0,
        "grid_current_A": u8(9) / 10.0,
        "ac_power_W": pac,
        "grid_freq_Hz": u16(13) / 100.0,
        "vpv1_V": vpv1_out,
        "vpv2_V": vpv2_out,
        "ipv1_A": ipv1,
        "ipv2_A": ipv2,
        "ppv1_W": ppv1,
        "ppv2_W": ppv2,
        "pdc_total_W": pdc_total,
        "e_total_kWh": e_total,
        "e_today_kWh": e_today,
        "temperature1_C": u16(35),
        "temperature2_C": u16(37),
        "status_flags": u16(39),
        "dual_mppt": dual_mppt,
        "total_len": total_len,
    }
