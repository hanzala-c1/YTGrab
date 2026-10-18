import sys
import os
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QPushButton, QComboBox, QProgressBar, QLabel, QFileDialog,
    QListWidget, QListWidgetItem, QCheckBox, QMessageBox
)
from src.downloader import FormatFetcher, DownloadWorker, PlaylistFetcher


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YTGrab")
        self.resize(560, 480)
        self.out_dir = os.path.expanduser("~/Downloads")
        self.formats = []
        self.queue = []
        self.current_item = None
        self.worker = None
        self.cookie_file = None

        layout = QVBoxLayout(self)

        url_row = QHBoxLayout()
        self.url_input = QLineEdit(placeholderText="Paste video URL...")
        self.fetch_btn = QPushButton("Fetch")
        self.fetch_btn.clicked.connect(self.fetch_formats)
        url_row.addWidget(self.url_input)
        url_row.addWidget(self.fetch_btn)
        layout.addLayout(url_row)

        self.title_label = QLabel("")
        layout.addWidget(self.title_label)

        self.quality_box = QComboBox()
        self.quality_box.setEnabled(False)
        layout.addWidget(self.quality_box)

        self.audio_only_check = QCheckBox("Audio only (MP3)")
        self.audio_only_check.stateChanged.connect(
            lambda state: self.quality_box.setEnabled(not state and bool(self.formats))
        )
        layout.addWidget(self.audio_only_check)


        add_row = QHBoxLayout()
        self.add_btn = QPushButton("Add to Queue")
        self.add_btn.setEnabled(False)
        self.add_btn.clicked.connect(self.add_to_queue)
        add_row.addWidget(self.add_btn)
        layout.addLayout(add_row)

        layout.addWidget(QLabel("Queue:"))
        self.queue_list = QListWidget()
        layout.addWidget(self.queue_list)

        queue_btn_row = QHBoxLayout()
        self.remove_btn = QPushButton("Remove Selected")
        self.remove_btn.clicked.connect(self.remove_selected)
        self.start_btn = QPushButton("Start Queue")
        self.start_btn.clicked.connect(self.start_queue)
        queue_btn_row.addWidget(self.remove_btn)
        queue_btn_row.addWidget(self.start_btn)
        layout.addLayout(queue_btn_row)

        dl_row = QHBoxLayout()
        self.folder_btn = QPushButton(f"Save to: {self.out_dir}")
        self.folder_btn.clicked.connect(self.choose_folder)
        dl_row.addWidget(self.folder_btn)
        layout.addLayout(dl_row)

        self.progress = QProgressBar()
        layout.addWidget(self.progress)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

    def show_error(self, title, message, retry_callback=None):
        self.status_label.setText("Error — see popup for details")

        if "sign in to confirm" in message.lower() or "not a bot" in message.lower():
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Warning)
            box.setWindowTitle("YouTube verification needed")
            box.setText(
                "YouTube is asking to verify this isn't a bot.\n\n"
                "This happens occasionally and isn't an app problem — "
                "it clears up by importing a cookies file from your browser."
            )
            import_btn = box.addButton("Import Cookies...", QMessageBox.ButtonRole.ActionRole)
            box.addButton(QMessageBox.StandardButton.Cancel)
            box.exec()
            if box.clickedButton() == import_btn:
                self.import_cookies()
                if self.cookie_file and retry_callback:
                    retry_callback()
            return

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Critical)
        box.setWindowTitle(title)
        box.setText(message)
        box.setTextInteractionFlags(box.textInteractionFlags() |
                                     __import__("PySide6.QtCore", fromlist=["Qt"]).Qt.TextInteractionFlag.TextSelectableByMouse)
        box.exec()

    def import_cookies(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select cookies.txt", "", "Text files (*.txt)")
        if path:
            self.cookie_file = path
            self.cookie_label.setText(f"Cookies: {os.path.basename(path)}")

    def fetch_formats(self):
        url = self.url_input.text().strip()
        if not url:
            return
        self.fetch_btn.setEnabled(False)

        # Cheap local check first — only hit the network twice for actual playlists
        looks_like_playlist = "list=" in url or "/playlist" in url
        if looks_like_playlist:
            self.status_label.setText("Checking URL...")
            self.playlist_fetcher = PlaylistFetcher(url, cookie_file=self.cookie_file)
            self.playlist_fetcher.finished.connect(self.on_playlist_ready)
            self.playlist_fetcher.not_playlist.connect(lambda: self.fetch_single(url))
            self.playlist_fetcher.error.connect(lambda e: self.fetch_single(url))
            self.playlist_fetcher.start()
        else:
            self.fetch_single(url)

    def fetch_single(self, url):
        self.status_label.setText("Fetching formats...")
        self.fetcher = FormatFetcher(url, cookie_file=self.cookie_file)
        self.fetcher.finished.connect(self.on_formats_ready)
        self.fetcher.error.connect(self.on_error)
        self.fetcher.start()

    def on_playlist_ready(self, entries, playlist_title):
        self.status_label.setText(
            f"Playlist detected: {len(entries)} videos. Adding all at best quality."
        )
        for e in entries:
            item = {"url": e["url"], "format_id": "best", "title": e["title"], "status": "Queued"}
            self.queue.append(item)
            list_item = QListWidgetItem(f"Queued - {e['title']}")
            self.queue_list.addItem(list_item)
            item["list_item"] = list_item
        self.url_input.clear()
        self.fetch_btn.setEnabled(True)

    def on_formats_ready(self, formats, title):
        self.formats = formats
        self.current_title = title
        self.title_label.setText(f"Title: {title}")
        self.quality_box.clear()
        for f in formats:
            self.quality_box.addItem(f["label"], f["id"])
        self.quality_box.setEnabled(True)
        self.add_btn.setEnabled(True)
        self.fetch_btn.setEnabled(True)
        self.status_label.setText("Ready to add to queue.")

    def add_to_queue(self):
        url = self.url_input.text().strip()
        format_id = self.quality_box.currentData()
        title = getattr(self, "current_title", url)
        if not url or not format_id:
            return

        audio_only = self.audio_only_check.isChecked()
        item = {"url": url, "format_id": format_id, "title": title,
                "status": "Queued", "audio_only": audio_only}
        self.queue.append(item)

        list_item = QListWidgetItem(f"Queued - {title}")
        self.queue_list.addItem(list_item)
        item["list_item"] = list_item

        self.url_input.clear()
        self.title_label.setText("")
        self.quality_box.clear()
        self.quality_box.setEnabled(False)
        self.add_btn.setEnabled(False)
        self.formats = []
        self.status_label.setText(f"Added to queue ({len(self.queue)} total).")

    def remove_selected(self):
        row = self.queue_list.currentRow()
        if row < 0:
            return
        if self.queue[row] is self.current_item:
            self.status_label.setText("Can't remove an item that's currently downloading.")
            return
        self.queue_list.takeItem(row)
        del self.queue[row]

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose folder", self.out_dir)
        if folder:
            self.out_dir = folder
            self.folder_btn.setText(f"Save to: {self.out_dir}")

    def start_queue(self):
        if self.worker is not None:
            return
        self.process_next()

    def process_next(self):
        pending = [i for i in self.queue if i["status"] == "Queued"]
        if not pending:
            self.status_label.setText("Queue complete.")
            self.worker = None
            return

        item = pending[0]
        self.current_item = item
        item["status"] = "Downloading"
        item["list_item"].setText(f"Downloading - {item['title']}")
        self.progress.setValue(0)
        self.status_label.setText(f"Downloading: {item['title']}")

        self.worker = DownloadWorker(
            item["url"], item["format_id"], self.out_dir,
            audio_only=item.get("audio_only", False),
            cookie_file=self.cookie_file
        )
        self.worker.progress.connect(self.progress.setValue)
        self.worker.status.connect(self.status_label.setText)
        self.worker.done.connect(self.on_item_done)
        self.worker.error.connect(self.on_item_error)
        self.worker.start()

    def on_item_done(self, msg):
        item = self.current_item
        item["status"] = "Done"
        item["list_item"].setText(f"Done - {item['title']}")
        self.worker = None
        self.process_next()

    def on_item_error(self, msg):
        item = self.current_item
        item["status"] = "Failed"
        item["list_item"].setText(f"Failed - {item['title']}")
        self.worker = None
        self.show_error(f"Download failed: {item['title']}", msg, retry_callback=self.start_queue)
        self.process_next()

    def on_error(self, msg):
        self.fetch_btn.setEnabled(True)
        self.show_error("Fetch failed", msg, retry_callback=self.fetch_formats)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
