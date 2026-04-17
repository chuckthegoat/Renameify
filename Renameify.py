import sys
import os
import requests
from guessit import guessit
from dotenv import load_dotenv

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel,
    QPushButton, QComboBox, QMessageBox,
    QScrollArea, QHBoxLayout
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap

from PyQt6.QtCore import QRunnable, QThreadPool, pyqtSignal, QObject, QTimer
import time

# =========================================================
# ENVIRONMENT + CONFIGURATION
# =========================================================

# Load environment variables from .env file (TMDB API key)
load_dotenv()

# TMDB API configuration constants
API_KEY = os.getenv("TMDB_API_KEY")
BASE_URL = "https://api.themoviedb.org/3"
IMAGE_BASE = "https://image.tmdb.org/t/p/w300"

# Thread pool definition and API call parameters
thread_pool = QThreadPool.globalInstance()
LAST_API_CALL = 0
MIN_API_INTERVAL = 0.25  # 250ms between TMDB calls

# =========================================================
# WORKER THREADS
# =========================================================
class WorkerSignals(QObject):
    result = pyqtSignal(object, list)

class TMDBWorker(QRunnable):
    def __init__(self, title, year, callback):
        super().__init__()
        self.title = title
        self.year = year
        self.signals = WorkerSignals()
        self.signals.result.connect(callback)

    def run(self):
        global LAST_API_CALL

        # ---------------------------
        # RATE LIMIT TMDB CALLS
        # ---------------------------
        now = time.time()
        wait = MIN_API_INTERVAL - (now - LAST_API_CALL)
        if wait > 0:
            time.sleep(wait)

        LAST_API_CALL = time.time()

        try:
            params = {"api_key": API_KEY, "query": self.title}

            # Add year filter if available from filename parsing
            if self.year:
                params["year"] = self.year

            r = requests.get(f"{BASE_URL}/search/movie", params=params, timeout=10)

            # Return only top 3 results for UI simplicity
            results = r.json().get("results", [])[:3]

        except:
            # Fail silently to avoid breaking UI flow
            results = []

        # send results back to UI thread
        self.signals.result.emit(self, results)
        
class PosterWorker(QRunnable):
    def __init__(self, url, callback):
        super().__init__()
        self.url = url
        self.callback = callback

    def run(self):
        try:
            data = requests.get(self.url, timeout=10).content
            self.callback(data)
        except:
            pass

# =========================================================
# MOVIE ROW UI COMPONENT
# =========================================================

class MovieRow(QWidget):
    def __init__(self, filepath, remove_callback):
        super().__init__()

        # Store file reference and callback for deletion
        self.filepath = filepath
        self.remove_callback = remove_callback

        # Extract filename and extension for rename operations
        filename = os.path.basename(filepath)
        self.base, self.ext = os.path.splitext(filename)

        # Use guessit to extract metadata (title/year) from filename
        info = guessit(filename)
        title = info.get("title")
        year = info.get("year")

        # Query TMDB only if a title was detected
        self.matches = []

        if title:
            worker = TMDBWorker(title, year, self.on_matches_ready)
            thread_pool.start(worker)

        # =====================================================
        # UI LAYOUT SETUP
        # =====================================================

        layout = QHBoxLayout(self)

        # ---------------------------
        # LEFT: POSTER DISPLAY AREA
        # ---------------------------
        self.poster = QLabel()
        self.poster.setFixedWidth(120)
        self.poster.setMinimumHeight(180)
        self.poster.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.poster)

        # ---------------------------
        # RIGHT: DATA COLUMN
        # ---------------------------
        right = QVBoxLayout()

        # =====================================================
        # REMOVE BUTTON (TOP RIGHT OF ROW)
        # =====================================================

        top_bar = QHBoxLayout()
        top_bar.addStretch()  # pushes button to far right

        remove_btn = QPushButton("×")
        remove_btn.setFixedSize(16, 16)

        # Minimal red "x" button styling
        remove_btn.setStyleSheet("""
            QPushButton {
                color: #ff5c5c;
                background: transparent;
                border: none;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                color: #ff1f1f;
            }
        """)

        # Trigger removal callback passed from parent widget
        remove_btn.clicked.connect(lambda: self.remove_callback(self))

        top_bar.addWidget(remove_btn)
        right.addLayout(top_bar)

        # =====================================================
        # ORIGINAL FILE DISPLAY
        # =====================================================

        orig_label = QLabel("Original File")
        orig_label.setStyleSheet("color: #888; font-size: 14px;")
        right.addWidget(orig_label)

        self.file_label = QLabel(filename)
        self.file_label.setWordWrap(True)
        self.file_label.setStyleSheet(
            "color: #000; font-weight: 500;"
        )
        right.addWidget(self.file_label)

        # =====================================================
        # NEW NAME PREVIEW DISPLAY
        # =====================================================

        preview_label = QLabel("New Name Preview")
        preview_label.setStyleSheet("color: #888; font-size: 14px;")
        right.addWidget(preview_label)

        self.preview = QLabel()
        self.preview.setWordWrap(True)
        self.preview.setStyleSheet(
            "color: #000; font-weight: 500;"
        )
        right.addWidget(self.preview)

        # =====================================================
        # MATCH SELECTION DROPDOWN
        # =====================================================

        match_label = QLabel("Match")
        match_label.setStyleSheet("color: #888; font-size: 14px;")
        right.addWidget(match_label)

        self.combo = QComboBox()

        # Populate dropdown with TMDB results
        for m in self.matches:
            year = (m.get("release_date") or "")[:4] or "?"
            self.combo.addItem(f"{m['title']} ({year})", m)

        # Update preview whenever selection changes
        self.combo.currentIndexChanged.connect(self.update_preview)
        self.combo.setStyleSheet(
            "color: #000; font-weight: 500;"
        )

        right.addWidget(self.combo)

        # Add right column to main layout
        layout.addLayout(right)

        # Initialize preview on creation
        self.update_preview()

    # =========================================================
    # CALLBACK HANDLER FOR THEMOVIEDB SEARCH THREADS
    # =========================================================
    def on_matches_ready(self, worker, results):
        """
        Receives TMDB results from background thread
        and updates UI safely in main thread.
        """

        self.matches = results

        self.combo.blockSignals(True)
        self.combo.clear()

        for m in results:
            year = (m.get("release_date") or "")[:4] or "?"
            self.combo.addItem(f"{m['title']} ({year})", m)

        self.combo.blockSignals(False)

        self.update_preview()

    # =========================================================
    # UPDATE PREVIEW + POSTER
    # =========================================================

    def update_preview(self):
        """
        Updates:
        - filename preview
        - poster image
        based on selected TMDB match
        """

        movie = self.combo.currentData()
        if not movie:
            self.preview.setText("No match")
            return

        # Build Plex-style filename preview
        title = movie.get("title", "Unknown")
        year = (movie.get("release_date") or "")[:4] or "Unknown"
        self.preview.setText(f"{title} ({year}){self.ext}")

        # Load poster image if available
        if movie.get("poster_path"):
            url = IMAGE_BASE + movie["poster_path"]

            def set_poster(data):
                pix = QPixmap()
                pix.loadFromData(data)
                self.poster.setPixmap(pix.scaledToWidth(120))

            worker = PosterWorker(url, set_poster)
            thread_pool.start(worker)

    # =========================================================
    # RENAME FILE ON DISK
    # =========================================================

    def rename(self):
        """
        Renames file using selected TMDB metadata
        into Plex-compatible format.
        """

        movie = self.combo.currentData()
        if not movie:
            return

        title = movie.get("title", "Unknown")
        year = (movie.get("release_date") or "")[:4] or "Unknown"

        new_name = f"{title} ({year}){self.ext}"
        new_path = os.path.join(os.path.dirname(self.filepath), new_name)

        os.rename(self.filepath, new_path)


# =========================================================
# MAIN APPLICATION WINDOW
# =========================================================

class MovieRenamer(QWidget):
    def __init__(self):
        super().__init__()

        # Track all active movie rows
        self.rows = []

        self.setWindowTitle("Renameify Movie Renamer")
        self.resize(900, 600)

        # Main vertical layout for entire window
        layout = QVBoxLayout(self)

        # Empty-state label
        self.empty_label = QLabel("Drag and drop movie files")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setStyleSheet("""
            color: #555;
            font-size: 18px;
            font-weight: 500;
        """)
        self.empty_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(self.empty_label)

        # Scrollable container for movie rows
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)

        self.container = QWidget()
        self.list_layout = QVBoxLayout(self.container)
        self.list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.scroll.setWidget(self.container)
        layout.addWidget(self.scroll)

        # Button to rename all queued files
        btn = QPushButton("Rename All")
        btn.clicked.connect(self.rename_all)
        layout.addWidget(btn)

        # Enable drag-and-drop file support
        self.setAcceptDrops(True)

        self.update_empty_state()

    # =========================================================
    # DRAG & DROP HANDLING
    # =========================================================

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.accept()

    def dropEvent(self, e):
        # Convert dropped URLs into file paths
        for url in e.mimeData().urls():
            path = url.toLocalFile()
            if os.path.isfile(path):
                self.add_file(path)

    # =========================================================
    # ROW MANAGEMENT
    # =========================================================

    def update_empty_state(self):
        """
        Shows placeholder text when no movies are loaded.
        Hides it when rows exist.
        """
        if len(self.rows) == 0:
            self.empty_label.show()
        else:
            self.empty_label.hide()

    def add_file(self, path):
        row = MovieRow(path, self.remove_row)
        self.rows.append(row)
        self.list_layout.addWidget(row)
        self.update_empty_state()

    def remove_row(self, row):
        self.rows.remove(row)
        row.setParent(None)
        row.deleteLater()
        self.update_empty_state()

    # =========================================================
    # BATCH RENAME ACTION
    # =========================================================

    def rename_all(self):
        for r in self.rows:
            r.rename()


# =========================================================
# APPLICATION ENTRY POINT
# =========================================================

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MovieRenamer()
    window.show()
    sys.exit(app.exec())
