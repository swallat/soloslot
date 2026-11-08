"""Audio playback from memory (sounddevice / PortAudio)."""

from __future__ import annotations

import threading

import numpy as np
from PySide6.QtCore import QObject, QTimer, Signal

TICK_MS = 25
CHUNK_SECONDS = 0.2


class SoundDeviceOutput:
    """Audio device through PortAudio (sounddevice). Raises on a missing library or device.

    Audio goes into a small FIFO that the device callback drains; `processed_us` counts what
    the device has actually taken, so the playhead follows what is heard.
    """

    BUFFER_SECONDS = 0.5

    def __init__(self, sample_rate: int, channels: int) -> None:
        import sounddevice as sd  # lazy: PortAudio may be missing on Linux

        self._rate, self._frame = sample_rate, 2 * channels
        self._fifo = bytearray()
        self._lock = threading.Lock()
        self._consumed = 0  # frames handed to the device
        self._limit = int(self.BUFFER_SECONDS * sample_rate) * self._frame
        self._stream = sd.RawOutputStream(
            samplerate=sample_rate, channels=channels, dtype="int16", callback=self._callback
        )

    def _callback(self, outdata, frames, _time, _status) -> None:
        need = frames * self._frame
        with self._lock:
            chunk = bytes(self._fifo[:need])
            del self._fifo[:need]
            self._consumed += len(chunk) // self._frame
        outdata[: len(chunk)] = chunk
        outdata[len(chunk) :] = bytes(need - len(chunk))

    def start(self) -> None:
        self._stream.start()

    def stop(self) -> None:
        self._stream.stop()
        self._stream.close()

    def free_bytes(self) -> int:
        with self._lock:
            return max(self._limit - len(self._fifo), 0)

    def write(self, data: bytes) -> int:
        with self._lock:
            self._fifo += data
        return len(data)

    def processed_us(self) -> int:
        with self._lock:
            return int(self._consumed * 1e6 / self._rate)


class Player(QObject):
    """Plays a float32 (frames, channels) buffer; seek, pause and play a span.

    `output_factory(sample_rate, channels)` makes the audio output, so tests can fake it.
    """

    positionChanged = Signal(float)  # seconds
    stateChanged = Signal(bool)  # playing?

    def __init__(self, output_factory=SoundDeviceOutput) -> None:
        super().__init__()
        self._factory = output_factory
        self._audio: np.ndarray | None = None
        self._rate = 44100
        self._out = None
        self._base = 0  # frame where the current output started
        self._sent = 0  # frames written to the output since it started
        self._stop_at: int | None = None
        self._pos = 0  # frame position while not playing
        self.playing = False
        self.error = ""
        self._timer = QTimer(self)
        self._timer.setInterval(TICK_MS)
        self._timer.timeout.connect(self._tick)

    # -- state
    @property
    def duration(self) -> float:
        return 0.0 if self._audio is None else len(self._audio) / self._rate

    def position(self) -> float:
        if self.playing and self._out is not None:
            played = int(self._out.processed_us() * self._rate / 1e6)
            return (self._base + min(played, self._sent)) / self._rate
        return self._pos / self._rate

    def set_audio(self, audio: np.ndarray, sample_rate: int) -> None:
        """Replace the audio (e.g. after the slots changed). Keeps position and play state."""
        was_playing, pos, stop_at = self.playing, self.position(), self._stop_at
        self._halt()
        self._audio, self._rate = audio, sample_rate
        self._pos = min(int(pos * sample_rate), len(audio))
        if was_playing:
            self.play(pos, None if stop_at is None else stop_at / sample_rate)

    # -- control
    def play(self, start: float | None = None, stop: float | None = None) -> None:
        if self._audio is None:
            return
        if start is not None:
            self._pos = min(max(int(start * self._rate), 0), len(self._audio))
        if self._pos >= len(self._audio):
            self._pos = 0
        self._halt()
        channels = min(self._audio.shape[1], 2)
        try:
            self._out = self._factory(self._rate, channels)
            self._out.start()
        except Exception as e:  # no device, or the platform refused the format
            self.error = str(e)
            self._out = None
            return
        self.error = ""
        self._base, self._sent = self._pos, 0
        self._stop_at = None if stop is None else min(int(stop * self._rate), len(self._audio))
        self.playing = True
        self._timer.start()
        self._tick()
        self.stateChanged.emit(True)

    def pause(self) -> None:
        if self.playing:
            self._pos = int(self.position() * self._rate)
            self._halt()
            self.stateChanged.emit(False)

    def stop(self) -> None:
        was = self.playing
        self._halt()
        self._pos = 0
        if was:
            self.stateChanged.emit(False)
        self.positionChanged.emit(0.0)

    def seek(self, seconds: float) -> None:
        """Move the playhead; keeps playing if it was."""
        if self.playing:
            self.play(seconds, None if self._stop_at is None else self._stop_at / self._rate)
        else:
            self._pos = min(
                max(int(seconds * self._rate), 0), 0 if self._audio is None else len(self._audio)
            )
            self.positionChanged.emit(self._pos / self._rate)

    # -- internals
    def _halt(self) -> None:
        self._timer.stop()
        if self._out is not None:
            self._out.stop()
            self._out = None
        self.playing = False

    def _end(self) -> int:
        n = len(self._audio)
        return n if self._stop_at is None else min(self._stop_at, n)

    def _tick(self) -> None:
        if not self.playing or self._out is None or self._audio is None:
            return
        end = self._end()
        channels = min(self._audio.shape[1], 2)
        while self._base + self._sent < end:
            room = self._out.free_bytes() // (2 * channels)
            frames = min(room, int(CHUNK_SECONDS * self._rate), end - self._base - self._sent)
            if frames <= 0:
                break
            a = self._base + self._sent
            chunk = np.clip(self._audio[a : a + frames, :channels], -1.0, 1.0)
            written = self._out.write((chunk * 32767).astype("<i2").tobytes())
            self._sent += written // (2 * channels)
            if written < frames * 2 * channels:
                break
        pos = self.position()
        self.positionChanged.emit(pos)
        if self._base + self._sent >= end and pos * self._rate >= end - 1:
            self._pos = end if self._stop_at is None else self._stop_at
            if self._pos >= len(self._audio):
                self._pos = 0
            self._halt()
            self.stateChanged.emit(False)
            self.positionChanged.emit(self._pos / self._rate)
