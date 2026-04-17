import sys
import os
import requests
from guessit import guessit
from dotenv import load_dotenv

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel,
    QPushButton, QComboBox, QMessageBox,
    QScrollArea, QFrame, QHBoxLayout, QSizePolicy
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap

# ---------------------------
# LOAD ENV VARIABLES
# ---------------------------
# Loads TMDB API key from .env file so it's not hardcoded
load_dotenv()

API_KEY = os.getenv("TMDB_API_KEY")
BASE_URL = "https://api.themoviedb.org/3"
IMAGE_BASE = "https://image.tmdb.org/t/p/w300"


# ---------------------------
# APPLICATION THEME (DARK MODE)
# ---------------------------
# Applies a consistent dark UI theme across all widgets
def apply_dark_theme(app):
    app.setStyle("Fusion")

    from PyQt6.QtGui import QPalette, QColor

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(30, 30, 30))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(220, 220, 220))
    palette.setColor(QPalette.ColorRole.Base, QColor(25, 25, 25))
    palette.setColor(QPalette.ColorRole.Text, QColor(220, 220, 220))
    palette.setColor(QPalette.ColorRole.Button, QColor(45, 45, 45))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(220, 220, 220))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(0, 120, 215))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    app.setPalette(palette)


# ---------------------------
# TMDB API SEARCH FUNCTION
# ---------------------------
# Queries TheMovieDB for up to 3 candidate matches
def search_movies(title, year=None):
    url = f"{BASE_URL}/search/movie"
    params = {"api_key": API_KEY, "query": title}

    if year:
        params["year"] = year

    try:
        r = requests.get(url, params=params)
        return r.json().get("results", [])[:3]
    except:
        return []


# ---------------------------
# FORMAT FINAL FILE NAME
# ---------------------------
# Converts selected movie metadata into Plex-style filename
def format_name(movie, ext):
    title = movie["title"]
    year = movie.get("release_date", "")[:4] or "Unknown"
    return f"{title} ({year}){ext}"


# ---------------------------
# MOVIE ROW UI COMPONENT
# ---------------------------
# Represents a single movie entry (poster + metadata + controls)
class MovieRow(QFrame):
    def __init__(self, filepath):
        super().__init__()

        # Store file reference for renaming operations
        self.filepath = filepath
        self.on_remove = None

        # ---------------------------
        # ROW STYLING CONTAINER
        # ---------------------------
        self.setStyleSheet("""
            QFrame {
                background-color: #2a2a2a;
                border-radius: 10px;
                padding: 10px;
            }
        """)

        # Main horizontal layout: poster (left) + details (right)
        main = QHBoxLayout()
        main.setSpacing(15)
        main.setContentsMargins(10, 10, 10, 10)

        # ---------------------------
        # LEFT COLUMN: POSTER DISPLAY
        # ---------------------------
        self.poster = QLabel()
        self.poster.setFixedSize(120, 180)
        self.poster.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.poster.setStyleSheet("background-color: #444; border-radius: 6px;")

        main.addWidget(self.poster)

        # ---------------------------
        # RIGHT COLUMN: DATA + CONTROLS
        # ---------------------------
        right = QVBoxLayout()
        right.setSpacing(10)

        # ---------------------------
        # REMOVE BUTTON (TOP RIGHT)
        # ---------------------------
        # Small red "x" button for removing row
        top = QHBoxLayout()
        top.addStretch()

        self.remove_button = QPushButton("x")
        self.remove_button.setFixedSize(20, 20)
        self.remove_button.setStyleSheet("""
            QPushButton {
                color: #ff4d4d;
                background: transparent;
                border: none;
                font-size: 14px;
            }
            QPushButton:hover {
                color: #ff1a1a;
            }
        """)
        self.remove_button.clicked.connect(self.handle_remove)

        top.addWidget(self.remove_button)
        right.addLayout(top)

        # ---------------------------
        # FILE METADATA PARSING
        # ---------------------------
        # Extracts title/year guess from filename using guessit
        filename = os.path.basename(filepath)
        self.name, self.ext = os.path.splitext(filename)

        info = guessit(filename)
        title = info.get("title")
        year = info.get("year")

        # Query TMDB for candidate matches (top 3 results)
        self.matches = search_movies(title, year) if title else []

        # ---------------------------
        # FIELD LAYOUT (TABLE-STYLE ALIGNMENT)
        # ---------------------------
        # Each field is a label + value aligned in a fixed row structure
        field_grid = QVBoxLayout()
        field_grid.setSpacing(8)

        def make_row(label_text, widget):
            """
            Creates a consistent two-column row:
            LABEL (fixed width) + VALUE (aligned)
            """

            row = QHBoxLayout()
            row.setSpacing(10)

            # Label column (fixed width ensures alignment across rows)
            label = QLabel(label_text)
            label.setFixedWidth(90)
            label.setStyleSheet("color: #aaa; font-size: 12px; font-weight: 600;")

            # Value widget (combo box or label)
            widget.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

            # Align both elements properly
            row.addWidget(label, alignment=Qt.AlignmentFlag.AlignTop)
            row.addWidget(widget, alignment=Qt.AlignmentFlag.AlignLeft)

            container = QWidget()
            container.setLayout(row)

            return container

        # ---------------------------
        # ORIGINAL FILE FIELD
        # ---------------------------
        self.file_label = QLabel(filename)
        self.file_label.setWordWrap(True)

        # ---------------------------
        # MATCH SELECTION DROPDOWN
        # ---------------------------
        self.combo = QComboBox()

        if self.matches:
            for m in self.matches:
                t = m["title"]
                y = m.get("release_date", "")[:4]
                r = m.get("vote_average", 0)
                self.combo.addItem(f"{t} ({y}) {r:.1f}", m)
        else:
            self.combo.addItem("No match", None)

        self.combo.currentIndexChanged.connect(self.update_row)

        # ---------------------------
        # NEW NAME PREVIEW FIELD
        # ---------------------------
        self.preview = QLabel("")
        self.preview.setWordWrap(True)
        self.preview.setStyleSheet("color: #ccc; font-weight: 500;")

        # Add all fields into structured grid
        field_grid.addWidget(make_row("Original File", self.file_label))
        field_grid.addWidget(make_row("Match", self.combo))
        field_grid.addWidget(make_row("New Name", self.preview))

        # Attach field grid to right panel
        right.addLayout(field_grid)
        right.addStretch()

        # Combine left (poster) + right (fields)
        main.addLayout(right)

        self.setLayout(main)

        # Initial render of preview + poster
        self.update_row()

    # ---------------------------
    # UPDATE ROW DISPLAY
    # ---------------------------
    # Updates preview name and loads poster image
    def update_row(self):
        movie = self.combo.currentData()

        if not movie:
            self.preview.setText("No valid match")
            return

        # Update filename preview
        self.preview.setText(format_name(movie, self.ext))

        # Load poster image from TMDB
        if movie.get("poster_path"):
            try:
                url = IMAGE_BASE + movie["poster_path"]
                data = requests.get(url).content

                pixmap = QPixmap()
                pixmap.loadFromData(data)

                self.poster.setPixmap(
                    pixmap.scaled(
                        120,
                        180,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                )
            except:
                pass

    # ---------------------------
    # RENAME FILE ON DISK
    # ---------------------------
    def rename(self):
        movie = self.combo.currentData()
        if not movie:
            return

        # Generate Plex-style filename
        new_name = format_name(movie, self.ext)
        new_path = os.path.join(os.path.dirname(self.filepath), new_name)

        try:
            os.rename(self.filepath, new_path)
            print(f"Renamed -> {new_name}")
        except Exception as e:
            print(f"Error: {e}")

    # ---------------------------
    # REMOVE ROW FROM UI
    # ---------------------------
    def handle_remove(self):
        if self.on_remove:
            self.on_remove(self)


# ---------------------------
# MAIN APPLICATION WINDOW
# ---------------------------
class MovieRenamer(QWidget):
    def __init__(self):
        super().__init__()

        # Window configuration
        self.setWindowTitle("Plex Movie Renamer")
        self.resize(1000, 700)

        # Store active rows
        self.rows = []

        # ---------------------------
        # MAIN LAYOUT
        # ---------------------------
        layout = QVBoxLayout()

        # Header label
        self.label = QLabel("Drag and drop movie files anywhere")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet("color: #aaa; font-size: 16px;")
        layout.addWidget(self.label)

        # ---------------------------
        # SCROLLABLE LIST AREA
        # ---------------------------
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)

        self.container = QWidget()
        self.list_layout = QVBoxLayout()
        self.list_layout.setSpacing(10)

        self.container.setLayout(self.list_layout)
        self.scroll.setWidget(self.container)

        layout.addWidget(self.scroll)

        # ---------------------------
        # CONFIRM BUTTON
        # ---------------------------
        self.button = QPushButton("Confirm Rename")
        self.button.setStyleSheet("""
            QPushButton {
                background-color: #0078d7;
                padding: 10px;
                border-radius: 6px;
                font-weight: bold;
            }
        """)
        self.button.clicked.connect(self.rename_all)

        layout.addWidget(self.button)

        self.setLayout(layout)

        # Enable drag and drop
        self.setAcceptDrops(True)

    # ---------------------------
    # DRAG AND DROP HANDLING
    # ---------------------------
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if os.path.isfile(path):
                self.add_row(path)

    # ---------------------------
    # ADD NEW MOVIE ROW
    # ---------------------------
    def add_row(self, filepath):
        row = MovieRow(filepath)
        row.on_remove = self.remove_row
        self.rows.append(row)
        self.list_layout.addWidget(row)

    # ---------------------------
    # REMOVE MOVIE ROW
    # ---------------------------
    def remove_row(self, row):
        self.list_layout.removeWidget(row)
        self.rows.remove(row)
        row.setParent(None)
        row.deleteLater()

    # ---------------------------
    # BATCH RENAME ALL FILES
    # ---------------------------
    def rename_all(self):
        confirm = QMessageBox.question(
            self,
            "Confirm Rename",
            "Rename all files?"
        )

        if confirm != QMessageBox.StandardButton.Yes:
            return

        for row in self.rows:
            row.rename()

        QMessageBox.information(self, "Done", "Renaming complete!")


# ---------------------------
# APPLICATION ENTRY POINT
# ---------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)

    apply_dark_theme(app)

    window = MovieRenamer()
    window.show()

    sys.exit(app.exec())
