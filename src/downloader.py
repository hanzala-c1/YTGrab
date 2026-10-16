from PySide6.QtCore import QThread, Signal
import yt_dlp


class FormatFetcher(QThread):
    """Fetches available quality/formats for a URL without downloading."""
    finished = Signal(list, str)  # formats, title
    error = Signal(str)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        try:
            opts = {"quiet": True, "no_warnings": True}
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(self.url, download=False)

            formats = []
            for f in info.get("formats", []):
                if f.get("vcodec") == "none":
                    continue
                size = f.get("filesize") or f.get("filesize_approx")
                size_mb = f"{size / 1_000_000:.1f}MB" if size else "?"
                label = f"{f.get('format_note', f.get('height', '?'))}p " \
                         f"{f.get('ext', '')} - {size_mb}"
                formats.append({"id": f["format_id"], "label": label})

            self.finished.emit(formats, info.get("title", "video"))
        except Exception as e:
            self.error.emit(str(e))


class DownloadWorker(QThread):
    """Downloads a single URL at the chosen format, reporting progress."""
    progress = Signal(int)
    status = Signal(str)
    done = Signal(str)
    error = Signal(str)

    def __init__(self, url, format_id, out_dir):
        super().__init__()
        self.url = url
        self.format_id = format_id
        self.out_dir = out_dir

    def _hook(self, d):
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            if total:
                pct = int(d.get("downloaded_bytes", 0) / total * 100)
                self.progress.emit(pct)
            self.status.emit(f"Downloading... {d.get('_speed_str', '')}")
        elif d["status"] == "finished":
            self.status.emit("Converting...")

    def run(self):
        try:
            opts = {
                "format": f"{self.format_id}+bestaudio/best",
                "outtmpl": f"{self.out_dir}/%(title)s.%(ext)s",
                "progress_hooks": [self._hook],
                "merge_output_format": "mp4",
            }
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([self.url])
            self.done.emit("Download complete.")
        except Exception as e:
            self.error.emit(str(e))


class PlaylistFetcher(QThread):
    """Checks if a URL is a playlist and lists its entries (flat, no per-video formats)."""
    finished = Signal(list, str)  # entries, playlist_title
    not_playlist = Signal()
    error = Signal(str)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        try:
            opts = {"quiet": True, "no_warnings": True, "extract_flat": True}
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(self.url, download=False)

            if info.get("_type") != "playlist" or "entries" not in info:
                self.not_playlist.emit()
                return

            entries = []
            for e in info["entries"]:
                if not e:
                    continue
                entries.append({
                    "url": e.get("url") or f"https://youtube.com/watch?v={e.get('id')}",
                    "title": e.get("title", "Unknown"),
                })

            self.finished.emit(entries, info.get("title", "Playlist"))
        except Exception as e:
            self.error.emit(str(e))
