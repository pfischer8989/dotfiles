#!/usr/bin/env python3
"""Check a final master before it goes to a distributor.

    release_check.py <file.wav> [--out DIR]

Prints the file's format, peaks, loudness and silence, with a verdict on each,
and writes release-check.md and release-check.json to DIR when given. Exit 0 if
nothing blocks the upload, 1 if something does, 2 if the file can't be read.

Numbers only: this measures and doesn't hear. Loudness is never a failure,
because how loud a master should be is Paul's call.
"""

import argparse
import hashlib
import json
import os
import struct
import sys

import numpy as np

SILENCE_DB = -60.0        # below this counts as silence at the ends
MAX_HEAD_SILENCE = 2.0    # seconds before the song starts
MAX_TAIL_SILENCE = 5.0    # seconds after it ends
TRUE_PEAK_WARN = -1.0     # dBTP; lossy store encodes can clip above this


def db(value):
    return float(20 * np.log10(value)) if value > 0 else float("-inf")


def read_wav(path):
    """Return (samples as float64 [frames, channels], info). Raises ValueError."""
    with open(path, "rb") as f:
        head = f.read(12)
        if len(head) < 12 or head[:4] != b"RIFF" or head[8:12] != b"WAVE":
            raise ValueError("not a RIFF WAV file")
        fmt = None
        while True:
            chunk = f.read(8)
            if len(chunk) < 8:
                raise ValueError("no audio data found")
            name, size = struct.unpack("<4sI", chunk)
            if name == b"fmt ":
                body = f.read(size + (size & 1))
                code, channels, rate, _, _, bits = struct.unpack("<HHIIHH", body[:16])
                if code == 0xFFFE and len(body) >= 26:  # extensible: real code follows
                    code = struct.unpack("<H", body[24:26])[0]
                fmt = (code, channels, rate, bits)
            elif name == b"data":
                if fmt is None:
                    raise ValueError("audio data before its format")
                data = f.read(size)
                break
            else:
                f.seek(size + (size & 1), 1)

    code, channels, rate, bits = fmt
    if not channels or not rate:
        raise ValueError("bad format chunk")
    width = bits // 8
    usable = len(data) - len(data) % (width * channels)
    if code == 3 and bits in (32, 64):
        samples = np.frombuffer(data[:usable], "<f%d" % width).astype(np.float64)
    elif code == 1 and bits == 16:
        samples = np.frombuffer(data[:usable], "<i2") / 32768.0
    elif code == 1 and bits == 24:
        raw = np.frombuffer(data[:usable], np.uint8).reshape(-1, 3)
        ints = raw[:, 0].astype(np.int32) | raw[:, 1].astype(np.int32) << 8 \
            | raw[:, 2].astype(np.int8).astype(np.int32) << 16
        samples = ints / 8388608.0
    elif code == 1 and bits == 32:
        samples = np.frombuffer(data[:usable], "<i4") / 2147483648.0
    else:
        raise ValueError("unsupported WAV encoding (format %d, %d bit)" % (code, bits))
    info = {"channels": channels, "rate": rate, "bits": bits, "float": code == 3}
    return samples.reshape(-1, channels), info


def biquad_response(b, a, n):
    """A biquad's frequency response on an n-point rfft grid."""
    z = np.exp(-2j * np.pi * np.fft.rfftfreq(n))
    return (b[0] + b[1] * z + b[2] * z * z) / (a[0] + a[1] * z + a[2] * z * z)


def k_weighting(rate):
    """The two K-weighting biquads of ITU-R BS.1770 at any sample rate."""
    # High shelf.
    f0, gain, q = 1681.974450955533, 3.999843853973347, 0.7071752369554196
    k = np.tan(np.pi * f0 / rate)
    vh = 10 ** (gain / 20)
    vb = vh ** 0.4996667741545416
    a0 = 1 + k / q + k * k
    shelf = ([(vh + vb * k / q + k * k) / a0, 2 * (k * k - vh) / a0,
              (vh - vb * k / q + k * k) / a0],
             [1, 2 * (k * k - 1) / a0, (1 - k / q + k * k) / a0])
    # High pass.
    f0, q = 38.13547087602444, 0.5003270373238773
    k = np.tan(np.pi * f0 / rate)
    a0 = 1 + k / q + k * k
    high = ([1, -2, 1], [1, 2 * (k * k - 1) / a0, (1 - k / q + k * k) / a0])
    return shelf, high


def integrated_lufs(samples, rate):
    """Gated integrated loudness per BS.1770-4, or None if too short or silent."""
    frames = samples.shape[0]
    block = int(round(rate * 0.4))
    hop = int(round(rate * 0.1))
    if frames < block:
        return None
    # Filter in the frequency domain, padded so the filters' tails don't wrap.
    n = frames + rate
    shelf, high = k_weighting(rate)
    response = biquad_response(*shelf, n) * biquad_response(*high, n)
    # BS.1770 weights L, R and C by 1 and the surrounds by 1.41; masters are stereo.
    power = np.zeros(frames)
    for ch in range(samples.shape[1]):
        weighted = np.fft.irfft(np.fft.rfft(samples[:, ch], n) * response, n)[:frames]
        power += weighted * weighted
    total = np.concatenate(([0.0], np.cumsum(power)))
    starts = np.arange(0, frames - block + 1, hop)
    energy = (total[starts + block] - total[starts]) / block
    with np.errstate(divide="ignore"):
        loudness = -0.691 + 10 * np.log10(energy)
    kept = energy[loudness > -70]
    if not len(kept):
        return None
    threshold = -0.691 + 10 * np.log10(kept.mean()) - 10
    kept = energy[loudness > max(-70, threshold)]
    return float(-0.691 + 10 * np.log10(kept.mean()))


def true_peak(samples, oversample=4, size=1 << 16):
    """The highest peak after oversampling, a linear value, per BS.1770 annex 2."""
    pad = 1024  # thrown away at both ends of a block, where the resampling rings
    step = size - 2 * pad
    best = 0.0
    for ch in range(samples.shape[1]):
        x = samples[:, ch]
        for start in range(-pad, max(len(x) - pad, 1), step):
            seg = x[max(start, 0):start + size]
            seg = np.pad(seg, (max(-start, 0), size - len(seg) - max(-start, 0)))
            spec = np.fft.rfft(seg)
            spec[-1] *= 0.5
            up = np.fft.irfft(spec, size * oversample) * oversample
            best = max(best, float(np.abs(up[pad * oversample:-pad * oversample]).max()))
    return best


def silence_at_ends(samples, rate):
    """Seconds of silence at the start and end of the file."""
    loud = np.flatnonzero(np.abs(samples).max(axis=1) > 10 ** (SILENCE_DB / 20))
    if not len(loud):
        return samples.shape[0] / rate, samples.shape[0] / rate
    return float(loud[0] / rate), float((samples.shape[0] - 1 - loud[-1]) / rate)


def check(path):
    samples, info = read_wav(path)
    rate = info["rate"]
    seconds = samples.shape[0] / rate
    peak = float(np.abs(samples).max()) if samples.size else 0.0
    # Clipped: a run of 3+ samples at full scale in one channel.
    full = np.abs(samples) >= 32767 / 32768
    runs = full[:-2] & full[1:-1] & full[2:] if samples.shape[0] > 2 else full[:0]
    head, tail = silence_at_ends(samples, rate)
    tp = true_peak(samples) if samples.size else 0.0
    lufs = integrated_lufs(samples, rate)
    sha = hashlib.sha256()
    with open(path, "rb") as f:
        for piece in iter(lambda: f.read(1 << 20), b""):
            sha.update(piece)
    result = {
        "file": os.path.basename(path),
        "sha256": sha.hexdigest(),
        "seconds": round(seconds, 2),
        "channels": info["channels"],
        "rate": rate,
        "bits": info["bits"],
        "float": info["float"],
        "sample_peak_db": round(db(peak), 2),
        "true_peak_db": round(db(tp), 2),
        "integrated_lufs": None if lufs is None else round(lufs, 1),
        "clipped_runs": int(runs.sum()),
        "head_silence_s": round(head, 2),
        "tail_silence_s": round(tail, 2),
    }
    result["findings"] = judge(result)
    return result


def judge(r):
    """A list of [level, text]: level is block, warn or ok."""
    out = []

    def add(level, text):
        out.append([level, text])

    if r["channels"] != 2:
        add("block", "%d channels; stores expect stereo" % r["channels"])
    else:
        add("ok", "stereo")
    if r["float"] or r["bits"] not in (16, 24):
        add("block", "%d-bit%s; export 16 or 24-bit PCM" % (r["bits"], " float" if r["float"] else ""))
    else:
        add("ok", "%d-bit PCM" % r["bits"])
    if r["rate"] != 44100:
        add("warn", "%d Hz; one guide says LANDR wants 44.1 kHz, so check theirs" % r["rate"])
    else:
        add("ok", "44.1 kHz")
    if r["true_peak_db"] > TRUE_PEAK_WARN:
        add("warn", "true peak %.2f dBTP, above %.1f; store encodes may clip"
            % (r["true_peak_db"], TRUE_PEAK_WARN))
    else:
        add("ok", "true peak %.2f dBTP" % r["true_peak_db"])
    if r["clipped_runs"]:
        add("warn", "%d runs of 3+ samples at full scale" % r["clipped_runs"])
    else:
        add("ok", "no runs at full scale")
    if r["head_silence_s"] > MAX_HEAD_SILENCE:
        add("warn", "%.2f s of silence at the start" % r["head_silence_s"])
    else:
        add("ok", "%.2f s of silence at the start" % r["head_silence_s"])
    if r["tail_silence_s"] > MAX_TAIL_SILENCE:
        add("warn", "%.2f s of silence at the end" % r["tail_silence_s"])
    else:
        add("ok", "%.2f s of silence at the end" % r["tail_silence_s"])
    if r["integrated_lufs"] is None:
        add("block", "no measurable audio")
    return out


def to_markdown(r):
    minutes = int(r["seconds"] // 60)
    lines = [
        "# Release check: %s" % r["file"],
        "",
        "| | |",
        "|---|---|",
        "| Length | %d:%04.1f |" % (minutes, r["seconds"] - minutes * 60),
        "| Format | %d-bit%s, %d Hz, %d channels |"
        % (r["bits"], " float" if r["float"] else "", r["rate"], r["channels"]),
        "| Integrated loudness | %s LUFS |" % r["integrated_lufs"],
        "| True peak | %.2f dBTP |" % r["true_peak_db"],
        "| Sample peak | %.2f dBFS |" % r["sample_peak_db"],
        "| SHA-256 | `%s` |" % r["sha256"],
        "",
    ]
    for level, text in r["findings"]:
        lines.append("- **%s:** %s" % (level, text))
    lines += ["", "This measures and doesn't hear.", ""]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check a final master for release.")
    parser.add_argument("path")
    parser.add_argument("--out", help="folder for release-check.md and .json")
    args = parser.parse_args(argv)
    try:
        result = check(args.path)
    except (OSError, ValueError) as err:
        print("ERROR: %s: %s" % (args.path, err), file=sys.stderr)
        return 2
    text = to_markdown(result)
    print(text)
    if args.out:
        os.makedirs(args.out, exist_ok=True)
        with open(os.path.join(args.out, "release-check.md"), "w") as f:
            f.write(text)
        with open(os.path.join(args.out, "release-check.json"), "w") as f:
            json.dump(result, f, indent=2)
    return 1 if any(level == "block" for level, _ in result["findings"]) else 0


if __name__ == "__main__":
    sys.exit(main())
