"""G.711 µ-law: лёгкое преобразование без audioop (совместимость с Python 3.13+)."""

from __future__ import annotations


def _ulaw_byte_to_linear(u: int) -> int:
    """Один байт µ-law → 16-bit linear (ITU-T G.711)."""
    u = (~u) & 0xFF
    sign = u & 0x80
    exponent = (u >> 4) & 0x07
    mantissa = u & 0x0F
    sample = (((mantissa << 3) + 0x84) << exponent) - 0x84
    if sign:
        sample = -sample
    return int(max(-32768, min(32767, sample)))


def ulaw_bytes_to_pcm16_mono(ulaw: bytes) -> bytes:
    """Поток µ-law → little-endian PCM16 mono."""
    out = bytearray(len(ulaw) * 2)
    j = 0
    for b in ulaw:
        s = _ulaw_byte_to_linear(b)
        out[j] = s & 0xFF
        out[j + 1] = (s >> 8) & 0xFF
        j += 2
    return bytes(out)


def pcm8k_to_pcm16k_dup(pcm8k_le: bytes) -> bytes:
    """Удвоение семплов 8 kHz → 16 kHz (ZOH), вход — PCM16 LE mono."""
    n = len(pcm8k_le) // 2
    out = bytearray(n * 4)
    for i in range(n):
        lo = pcm8k_le[i * 2]
        hi = pcm8k_le[i * 2 + 1]
        out[i * 4] = lo
        out[i * 4 + 1] = hi
        out[i * 4 + 2] = lo
        out[i * 4 + 3] = hi
    return bytes(out)


def linear_sample_to_ulaw(sample: int) -> int:
    """Один семпл linear int16 → µ-law byte."""
    bias = 0x84
    clip = 32635
    sample = max(-clip, min(clip, int(sample)))
    sign = 0x80 if sample < 0 else 0
    if sample < 0:
        sample = -sample
    sample += bias
    exponent = 7
    exp_mask = 0x4000
    while exponent > 0 and not (sample & exp_mask):
        exp_mask >>= 1
        exponent -= 1
    mantissa = (sample >> (exponent + 3)) & 0x0F
    ulaw = ~(sign | (exponent << 4) | mantissa) & 0xFF
    return ulaw


def pcm16_mono_to_ulaw(pcm_le: bytes) -> bytes:
    """PCM16 LE mono → µ-law байты (длина pcm кратна 2)."""
    import struct

    n = len(pcm_le) // 2
    samples = struct.unpack(f"<{n}h", pcm_le)
    return bytes(linear_sample_to_ulaw(s) for s in samples)


def downsample_pcm16_24k_to_8k(pcm24k_le: bytes) -> bytes:
    """Простое усреднение троек семплов: 24 kHz → 8 kHz, mono LE."""
    import struct

    n = len(pcm24k_le) // 2
    samples = struct.unpack(f"<{n}h", pcm24k_le)
    out: list[int] = []
    for i in range(0, n - 2, 3):
        v = (samples[i] + samples[i + 1] + samples[i + 2]) // 3
        out.append(int(max(-32768, min(32767, v))))
    return struct.pack(f"<{len(out)}h", *out)


def downsample_pcm16_24k_to_16k(pcm24k_le: bytes) -> bytes:
    """Линейная интерполяция вдоль времени: 24 kHz → 16 kHz, mono int16 LE (шаг позиции 1.5 семпла)."""
    import struct

    n = len(pcm24k_le) // 2
    if n < 2:
        return b""
    samples = struct.unpack(f"<{n}h", pcm24k_le)
    out: list[int] = []
    pos = 0.0
    while True:
        i = int(pos)
        if i >= n - 1:
            break
        frac = pos - i
        s = samples[i] * (1.0 - frac) + samples[i + 1] * frac
        out.append(int(max(-32768, min(32767, round(s)))))
        pos += 1.5
    return struct.pack(f"<{len(out)}h", *out)
