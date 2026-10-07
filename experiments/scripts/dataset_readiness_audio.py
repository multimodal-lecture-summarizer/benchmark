"""Independent source-container frame declarations for bounded audio extraction."""
import struct


def declared_audio_frames(encoded: bytes) -> int:
    """Reject unknown/truncated containers instead of trusting decoder-clamped counts."""
    if encoded.startswith(b"RIFF"):
        return _wav_frames(encoded)
    if encoded.startswith(b"fLaC"):
        return _flac_frames(encoded)
    raise ValueError("unsupported or unverified embedded audio container")


def _wav_frames(encoded: bytes) -> int:
    if len(encoded) < 12 or encoded[8:12] != b"WAVE":
        raise ValueError("invalid RIFF WAVE header")
    declared_end = 8 + struct.unpack_from("<I", encoded, 4)[0]
    if declared_end > len(encoded) or declared_end < 12:
        raise ValueError("truncated or invalid declared RIFF length")
    position, alignment, data_bytes = 12, None, None
    while position < declared_end:
        if position + 8 > declared_end:
            raise ValueError("truncated RIFF chunk header")
        kind = encoded[position:position + 4]
        size = struct.unpack_from("<I", encoded, position + 4)[0]
        start, end = position + 8, position + 8 + size
        if end > declared_end or end > len(encoded):
            raise ValueError("truncated RIFF chunk payload")
        if kind == b"fmt ":
            if size < 16 or alignment is not None:
                raise ValueError("invalid or repeated WAVE format chunk")
            codec, channels, rate, byte_rate, alignment, bits = struct.unpack_from("<HHIIHH", encoded, start)
            if codec not in {1, 3, 65534} or min(channels, rate, alignment, bits) <= 0:
                raise ValueError("unsupported WAVE sample format")
            if codec == 65534:
                if size < 40 or struct.unpack_from("<H", encoded, start + 16)[0] < 22:
                    raise ValueError("invalid extensible WAVE format")
                guid = encoded[start + 24:start + 40]
                if guid not in (bytes.fromhex("0100000000001000800000aa00389b71"),
                                 bytes.fromhex("0300000000001000800000aa00389b71")):
                    raise ValueError("unsupported extensible WAVE codec")
            if alignment != channels * ((bits + 7) // 8) or byte_rate != rate * alignment:
                raise ValueError("inconsistent WAVE block alignment")
        elif kind == b"data":
            if data_bytes is not None:
                raise ValueError("multiple WAVE data chunks are unsupported")
            data_bytes = size
        position = end + (size % 2)
        if position > declared_end:
            raise ValueError("missing RIFF chunk padding")
    if alignment is None or data_bytes is None or not data_bytes or data_bytes % alignment:
        raise ValueError("missing or incomplete WAVE sample frames")
    return data_bytes // alignment


def _flac_frames(encoded: bytes) -> int:
    if len(encoded) < 42 or encoded[4] & 0x7f != 0 or int.from_bytes(encoded[5:8], "big") != 34:
        raise ValueError("missing FLAC STREAMINFO")
    # STREAMINFO bytes 10..17 pack rate(20), channels(3), bits(5), total samples(36).
    frames = int.from_bytes(encoded[18:26], "big") & ((1 << 36) - 1)
    if not frames:
        raise ValueError("FLAC has no independently declared sample count")
    position = 4
    while True:
        if position + 4 > len(encoded):
            raise ValueError("truncated FLAC metadata header")
        last = bool(encoded[position] & 0x80)
        size = int.from_bytes(encoded[position + 1:position + 4], "big")
        position += 4 + size
        if position > len(encoded):
            raise ValueError("truncated FLAC metadata payload")
        if last:
            break
    if position == len(encoded):
        raise ValueError("FLAC contains no encoded audio frames")
    return frames
