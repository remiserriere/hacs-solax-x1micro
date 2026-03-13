"""Binary frame decoder for SolaX Pocket WiFi MQTT data."""

from __future__ import annotations

import logging
import struct
from typing import Any

_LOGGER = logging.getLogger(__name__)


FRAME_MAGIC = b"$$"
FRAME_LENGTH = 107  # exact byte count for a real-time data frame
FRAME_LENGTH_COMPACT = 79  # compact start-up frame (no inv-SN, no first 7 data bytes)
FRAME_LENGTH_MINIMAL = 64  # minimal handshake frame (rated_power + const only)
FRAME_LENGTH_FIRMWARE = 46  # firmware-version response (function code 0x0E)
FRAME_LENGTH_CONFIG = 158  # configuration parameter dump (47 extra bytes appended)
FUNC_CODE_REALTIME = 0x1C
FUNC_CODE_FIRMWARE = 0x0E


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

    Other observed frame types (handled by dedicated decoders, not this one):
      79-byte  (0x4F): Compact start-up frame — function code 0x1C but missing
                       the inverter-SN section and the first 7 data bytes.
                       Sent during the initial boot sequence.
                       Handled by decode_compact_frame().
      64-byte  (0x40): Minimal handshake frame — function code 0x1C, contains
                       only rated_power + const_0x0205, no real-time data.
                       Part of the same boot sequence.
                       Identified by classify_boot_frame().
      46-byte  (0x2E): Firmware-version response — function code 0x0E,
                       contains an ASCII firmware string (e.g. "005.03").
                       Identified by classify_boot_frame().
      158-byte (0x9E): Configuration parameter dump — function code 0x1C but
                       51 extra bytes of parameter data appended.  The bytes at
                       the e_total/e_today offsets contain garbage (e.g. 2944,
                       yielding the spurious 294.4 kWh value seen in logs).
                       Identified by classify_boot_frame().
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


def decode_compact_frame(data: bytes) -> dict[str, Any] | None:
    """Decode a 79-byte compact start-up frame (sent during the boot sequence).

    This frame shares the magic bytes and function code (0x1C) with the standard
    real-time frame but omits the inverter-SN section (21 bytes) and the first
    7 bytes of the data section (rated_power, const_0x0205, run_mode, reserved).
    The remaining 40 data bytes are identical in layout to standard data offsets
    7–46, starting with grid_voltage_V.

    Returns a partial dict of real-time values (rated_power_W, run_mode, and
    inverter_sn are absent), or None if the frame is invalid or does not match
    this format.

    Frame layout (exactly 79 bytes):
      0x00  2  Magic "$$"
      0x02  2  Total length (LE) = 0x004F
      0x04  1  Message type (0x08)
      0x05  1  Protocol version
      0x06  1  Sequence number
      0x07  1  Function code (0x1C)
      0x08 21  WiFi module SN (ASCII, null-padded)
      0x1D  1  Number of inverters
      0x1E  1  DSP firmware version
      0x1F  1  ARM firmware version
      0x20  1  Reserved
      0x21  1  Hardware version
      0x22  1  Firmware major
      0x23  1  Firmware minor
      0x24  1  Reserved
      0x25 40  Data section starting at standard offset 7 (grid_voltage_V)
      0x4D  2  Checksum (BE)
    """
    if len(data) != FRAME_LENGTH_COMPACT:
        return None
    if data[:2] != FRAME_MAGIC:
        return None
    if data[7] != FUNC_CODE_REALTIME:
        return None

    expected_crc: int = struct.unpack_from(">H", data, FRAME_LENGTH_COMPACT - 2)[0]
    computed_crc: int = crc16_buypass(data[: FRAME_LENGTH_COMPACT - 2])
    if computed_crc != expected_crc:
        _LOGGER.debug(
            "Compact frame CRC mismatch: computed 0x%04X, got 0x%04X",
            computed_crc,
            expected_crc,
        )
        return None

    wifi_sn: str = data[8:29].rstrip(b"\x00").decode("ascii", errors="replace")

    # Data section starts at byte 37, corresponding to standard data offset 7.
    # compact_off 0  == standard data offset 7  (grid_voltage_V)
    # compact_off 2  == standard data offset 9  (grid_current_A, 1 byte)
    # compact_off 4  == standard data offset 11 (ac_power_W)
    # compact_off 6  == standard data offset 13 (grid_freq_Hz)
    # compact_off 8  == standard data offset 15 (vpv1_V)
    # compact_off 10 == standard data offset 17 (vpv2_V)
    # compact_off 12 == standard data offset 19 (ipv1_A)
    # compact_off 14 == standard data offset 21 (ipv2_A)
    # compact_off 16 == standard data offset 23 (ppv1_W)
    # compact_off 18 == standard data offset 25 (ppv2_W)
    # compact_off 20 == standard data offset 27 (mppt_mode)
    # compact_off 22 == standard data offset 29 (e_total_kWh)
    # compact_off 26 == standard data offset 33 (e_today_kWh)
    # compact_off 28 == standard data offset 35 (temperature1_C)
    # compact_off 30 == standard data offset 37 (temperature2_C)
    # compact_off 32 == standard data offset 39 (status_flags)
    OFF = 37

    def u16(off: int) -> int:
        return struct.unpack_from("<H", data, OFF + off)[0]

    def u8(off: int) -> int:
        return data[OFF + off]

    dual_mppt: bool = u16(20) == 2

    if dual_mppt:
        ipv1: float | None = u16(12) / 10.0
        ipv2: float | None = u16(14) / 10.0
        ppv1: int | None = u16(16)
        ppv2: int | None = u16(18)
        pdc_total: int | None = ppv1 + ppv2
    else:
        ipv1 = None
        ipv2 = None
        ppv1 = None
        ppv2 = None
        pdc_total = None

    return {
        "wifi_sn": wifi_sn,
        "grid_voltage_V": u16(0) / 10.0,
        "grid_current_A": u8(2) / 10.0,
        "ac_power_W": u16(4),
        "grid_freq_Hz": u16(6) / 100.0,
        "vpv1_V": u16(8) / 10.0,
        "vpv2_V": u16(10) / 10.0,
        "ipv1_A": ipv1,
        "ipv2_A": ipv2,
        "ppv1_W": ppv1,
        "ppv2_W": ppv2,
        "pdc_total_W": pdc_total,
        "e_total_kWh": u16(22) / 10.0,
        "e_today_kWh": u16(26) / 10.0,
        "temperature1_C": u16(28),
        "temperature2_C": u16(30),
        "status_flags": u16(32),
        "dual_mppt": dual_mppt,
    }


def classify_boot_frame(data: bytes) -> str | None:
    """Identify a known non-standard boot frame by length and function code.

    Verifies the magic bytes and CRC before classifying.  Returns a short
    human-readable description for known frame types, or None if the frame
    is unknown, has invalid magic, or has an invalid CRC.

    Known types (all sent during the inverter boot sequence):
      64-byte  (0x40): Minimal handshake — function code 0x1C, rated_power only.
      46-byte  (0x2E): Firmware-version response — function code 0x0E, contains
                       the inverter firmware version string (e.g. "005.03").
      158-byte (0x9E): Configuration parameter dump — function code 0x1C with
                       51 extra bytes of parameter data; real-time data offsets
                       contain garbage values and must not be used.
    """
    n = len(data)
    if n < 8 or data[:2] != FRAME_MAGIC:
        return None

    expected_crc: int = struct.unpack_from(">H", data, n - 2)[0]
    computed_crc: int = crc16_buypass(data[: n - 2])
    if computed_crc != expected_crc:
        return None

    func = data[7]

    if n == FRAME_LENGTH_MINIMAL and func == FUNC_CODE_REALTIME:
        inv_sn = data[37:58].rstrip(b"\x00").decode("ascii", errors="replace")
        rated_power = struct.unpack_from("<H", data, 58)[0]
        return (
            f"minimal handshake (64B): inverter_sn={inv_sn!r},"
            f" rated_power={rated_power}W"
        )

    if n == FRAME_LENGTH_FIRMWARE and func == FUNC_CODE_FIRMWARE:
        # Firmware version string starts at byte 38 (after a 1-byte length field
        # at byte 37) and is 6 ASCII characters long (e.g. b"005.03").
        fw_bytes = data[38 : n - 2]
        fw_str = fw_bytes.rstrip(b"\x00").decode("ascii", errors="replace")
        return f"firmware-version response (46B): firmware={fw_str!r}"

    if n == FRAME_LENGTH_CONFIG and func == FUNC_CODE_REALTIME:
        inv_sn = data[37:58].rstrip(b"\x00").decode("ascii", errors="replace")
        rated_power = struct.unpack_from("<H", data, 58)[0]
        return (
            f"configuration parameter dump (158B): inverter_sn={inv_sn!r},"
            f" rated_power={rated_power}W"
        )

    return None
