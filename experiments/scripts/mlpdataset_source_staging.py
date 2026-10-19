"""Verified, bounded runtime staging for sequential preview extraction."""
import hashlib
import os
from pathlib import Path
import shutil
import tempfile
import time
from collections import OrderedDict


class SourceBindingMismatchError(RuntimeError):
    """Source bytes no longer match the bound media identity."""


class PreviewSourceStager:
    CHUNK = 1024 * 1024
    FREE_FLOOR = 256 * 1024 * 1024

    def __init__(self, max_bytes=2 * 1024**3, enabled=True, local_parent=None,
                 ram_candidates=None, memory_available_bytes=None):
        self.max_bytes = max(0, int(max_bytes))
        self.enabled = bool(enabled)
        self.local_parent = Path(local_parent) if local_parent is not None else None
        self.ram_candidates = [Path(p) for p in (ram_candidates if ram_candidates is not None else ['/dev/shm'])]
        self.memory_available_bytes = memory_available_bytes
        self.root = None
        self.parent = None
        self.root_identity = None
        self.entries = OrderedDict()
        self.memo = {}
        self.closed = False
        self.metrics = dict(mode='not_started', cap_bytes=0, current_bytes=0, peak_bytes=0,
                            copies=0, hits=0, fallbacks=0, copy_seconds=0.0,
                            fallback_reasons={})

    @staticmethod
    def fingerprint(path):
        stat = path.stat()
        return (stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)

    def memory_available(self):
        if self.memory_available_bytes is not None:
            return int(self.memory_available_bytes)
        try:
            with open('/proc/meminfo', encoding='ascii') as handle:
                for line in handle:
                    if line.startswith('MemAvailable:'):
                        return int(line.split()[1]) * 1024
        except OSError:
            pass
        try:
            return os.sysconf('SC_AVPHYS_PAGES') * os.sysconf('SC_PAGE_SIZE')
        except (AttributeError, ValueError, OSError):
            return 0  # Unknown RAM capacity: choose disk scratch.

    def fallback(self, source, reason, key=None, memoize=False):
        self.metrics['fallbacks'] += 1
        reasons = self.metrics['fallback_reasons']
        reasons[reason] = reasons.get(reason, 0) + 1
        if memoize and key is not None:
            self.memo[key] = reason
        return source

    def initialize(self, required_bytes):
        if self.root is not None:
            return
        memory_cap = max(0, self.memory_available() // 4 - self.FREE_FLOOR)
        candidates = []
        if self.local_parent is None:
            candidates.extend((path, 'ram', memory_cap) for path in self.ram_candidates)
        local = self.local_parent or (Path('/content') if Path('/content').is_dir() else Path(tempfile.gettempdir()))
        candidates.append((local, 'local', self.max_bytes))
        for parent, mode, memory_limit in candidates:
            try:
                if not parent.is_dir():
                    continue
                cap = min(self.max_bytes, memory_limit,
                          max(0, shutil.disk_usage(parent).free - self.FREE_FLOOR))
                if cap <= 0 or cap < required_bytes:
                    continue
                root = Path(tempfile.mkdtemp(prefix='mlp-preview-stage-', dir=str(parent))).resolve()
                self.root, self.parent = root, parent.resolve()
                stat = root.stat()
                self.root_identity = (stat.st_dev, stat.st_ino)
                self.metrics.update(mode=mode, cap_bytes=cap)
                return
            except OSError:
                continue
        self.metrics['mode'] = 'unavailable'

    def expired(self, deadline):
        if time.monotonic() >= deadline:
            raise TimeoutError('staging deadline reached')

    def remove_entry(self, key):
        entry = self.entries.pop(key)
        entry['path'].unlink(missing_ok=True)
        self.metrics['current_bytes'] -= entry['size']

    def verify(self, path, expected, deadline):
        digest = hashlib.sha256()
        with path.open('rb') as handle:
            while True:
                self.expired(deadline)
                block = handle.read(self.CHUNK)
                if not block:
                    break
                digest.update(block)
        self.expired(deadline)
        return digest.hexdigest() == expected

    def get(self, source_path, expected_sha256, deadline):
        source = Path(source_path)
        if self.closed or not self.enabled or self.max_bytes == 0:
            return self.fallback(source, 'disabled_or_closed')
        part = None
        copy_started = None
        key = None
        try:
            self.expired(deadline)
            resolved = source.resolve(strict=True)
            original_stat = self.fingerprint(resolved)
            expected = str(expected_sha256).lower()
            if len(expected) != 64 or any(c not in '0123456789abcdef' for c in expected):
                return self.fallback(source, 'invalid_expected_sha256')
            key = (str(resolved), *original_stat, expected)
            if key in self.memo:
                return self.fallback(source, self.memo[key])
            if key in self.entries:
                entry = self.entries[key]
                try:
                    valid = self.fingerprint(entry['path']) == entry['stat']
                    if not valid:
                        valid = self.verify(entry['path'], expected, deadline)
                    if valid:
                        entry['stat'] = self.fingerprint(entry['path'])
                        self.entries.move_to_end(key)
                        self.metrics['hits'] += 1
                        return entry['path']
                except OSError:
                    pass
                self.remove_entry(key)
            size = original_stat[0]
            if size > self.max_bytes:
                return self.fallback(source, 'insufficient_capacity', key, True)
            self.initialize(size)
            if self.root is None or size > self.metrics['cap_bytes']:
                return self.fallback(source, 'insufficient_capacity', key, True)
            while self.entries and self.metrics['current_bytes'] + size > self.metrics['cap_bytes']:
                self.remove_entry(next(iter(self.entries)))
            if shutil.disk_usage(self.root).free - self.FREE_FLOOR < size:
                return self.fallback(source, 'insufficient_free_space', key, True)
            target = self.root / (hashlib.sha256(repr(key).encode()).hexdigest() + resolved.suffix)
            part = target.with_suffix(target.suffix + '.part')
            digest = hashlib.sha256()
            copied = 0
            copy_started = time.monotonic()
            with resolved.open('rb') as src, part.open('xb') as dst:
                while True:
                    self.expired(deadline)
                    block = src.read(self.CHUNK)
                    if not block:
                        break
                    if (self.metrics['current_bytes'] + copied + len(block) > self.metrics['cap_bytes']
                            or shutil.disk_usage(self.root).free < self.FREE_FLOOR + len(block)):
                        raise OSError('scratch space exhausted')
                    dst.write(block)
                    digest.update(block)
                    copied += len(block)
                    self.metrics['peak_bytes'] = max(self.metrics['peak_bytes'], self.metrics['current_bytes'] + copied)
            self.expired(deadline)
            if digest.hexdigest() != expected or self.fingerprint(resolved) != original_stat:
                raise SourceBindingMismatchError('Source digest or fingerprint changed during staging')
            part.replace(target)
            part = None
            self.entries[key] = dict(path=target, size=copied, stat=self.fingerprint(target))
            self.metrics['current_bytes'] += copied
            self.metrics['copies'] += 1
            return target
        except (OSError, TimeoutError, ValueError) as error:
            reason = type(error).__name__ + ': ' + str(error)
            return self.fallback(source, reason, key, str(error) == 'scratch space exhausted')
        finally:
            if part is not None:
                part.unlink(missing_ok=True)
            if copy_started is not None:
                self.metrics['copy_seconds'] += time.monotonic() - copy_started

    def stats(self):
        return {**self.metrics, 'fallback_reasons': dict(self.metrics['fallback_reasons'])}

    def close(self):
        if self.root is not None and self.root.exists():
            stat = self.root.lstat()
            if (not self.root.is_symlink() and self.root.parent == self.parent
                    and self.root.name.startswith('mlp-preview-stage-')
                    and (stat.st_dev, stat.st_ino) == self.root_identity):
                shutil.rmtree(self.root)
                self.entries.clear()
                self.metrics['current_bytes'] = 0
        self.closed = True
