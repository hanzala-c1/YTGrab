import sys
import os
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QPushButton, QComboBox, QProgressBar, QLabel, QFileDialog
)
from src.downloader import FormatFetcher, DownloadWorker


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YTGrab")
        self.resize(480, 220)
        self.out_dir = os.path.expanduser("~/Downloads")
        self.formats = []

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

        dl_row = QHBoxLayout()
        self.folder_btn = QPushButton(f"Save to: {self.out_dir}")
        self.folder_btn.clicked.connect(self.choose_folder)
        self.download_btn = QPushButton("Download")
        self.download_btn.setEnabled(False)
        self.download_btn.clicked.connect(self.start_download)
        dl_row.addWidget(self.folder_btn)
        dl_row.addWidget(self.download_btn)
        layout.addLayout(dl_row)

        self.progress = QProgressBar()
        layout.addWidget(self.progress)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

    def fetch_formats(self):
        url = self.url_input.text().strip()
        if not url:
            return
        self.fetch_btn.setEnabled(False)
        self.status_label.setText("Fetching formats...")

        self.fetcher = FormatFetcher(url)
        self.fetcher.finished.connect(self.on_formats_ready)
        self.fetcher.error.connect(self.on_error)
        self.fetcher.start()

    def on_formats_ready(self, formats, title):
        self.formats = formats
        self.title_label.setText(f"Title: {title}")
        self.quality_box.clear()
        for f in formats:
            self.quality_box.addItem(f["label"], f["id"])
        self.quality_box.setEnabled(True)
        self.download_btn.setEnabled(True)
        self.fetch_btn.setEnabled(True)
        self.status_label.setText("Ready.")

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose folder", self.out_dir)
        if folder:
            self.out_dir = folder
            self.folder_btn.setText(f"Save to: {self.out_dir}")

    def start_download(self):
        format_id = self.quality_box.currentData()
        url = self.url_input.text().strip()
        self.download_btn.setEnabled(False)
        self.progress.setValue(0)

        self.worker = DownloadWorker(url, format_id, self.out_dir)
        self.worker.progress.connect(self.progress.setValue)
        self.worker.status.connect(self.status_label.setText)
        self.worker.done.connect(self.on_done)
        self.worker.error.connect(self.on_error)
        self.worker.start()

    def on_done(self, msg):
        self.status_label.setText(msg)
        self.download_btn.setEnabled(True)

    def on_error(self, msg):
        self.status_label.setText(f"Error: {msg}")
        self.fetch_btn.setEnabled(True)
        self.download_btn.setEnabled(True)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
