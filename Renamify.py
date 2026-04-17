import sys
import os
import requests
from guessit import guessit
from dotenv import load_dotenv

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem,
    QComboBox, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap

load_dotenv()

API_KEY = os.getenv("TMDB_API_KEY")
BASE_URL = "https://api.themoviedb.org/3"
IMAGE_BASE = "https://image.tmdb.org/t/p/w200"

class DropTable(QTableWidget):
    def __init__(self, parent):
        super().__init__(0, 4)
        self.parent = parent

        self.setHorizontalHeaderLabels([
            "Original File", "Match Selection", "Preview", "Poster"
        ])

        self.setAcceptDrops(True)
        self.setDragDropMode(QTableWidget.DragDropMode.DropOnly)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            filepath = url.toLocalFile()

            if os.path.isfile(filepath):
                self.parent.add_file(filepath)

        event.acceptProposedAction()

def apply_dark_theme(app):
    app.setStyle("Fusion")

    dark_palette = app.palette()

    from PyQt6.QtGui import QColor, QPalette

    dark_palette.setColor(QPalette.ColorRole.Window, QColor(30, 30, 30))
    dark_palette.setColor(QPalette.ColorRole.WindowText, QColor(220, 220, 220))
    dark_palette.setColor(QPalette.ColorRole.Base, QColor(25, 25, 25))
    dark_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(35, 35, 35))
    dark_palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(220, 220, 220))
    dark_palette.setColor(QPalette.ColorRole.ToolTipText, QColor(220, 220, 220))
    dark_palette.setColor(QPalette.ColorRole.Text, QColor(220, 220, 220))
    dark_palette.setColor(QPalette.ColorRole.Button, QColor(45, 45, 45))
    dark_palette.setColor(QPalette.ColorRole.ButtonText, QColor(220, 220, 220))
    dark_palette.setColor(QPalette.ColorRole.Highlight, QColor(0, 120, 215))
    dark_palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))

    app.setPalette(dark_palette)

def search_movies(title, year=None):
    url = f"{BASE_URL}/search/movie"
    params = {
        "api_key": API_KEY,
        "query": title,
    }

    if year:
        params["year"] = year

    try:
        response = requests.get(url, params=params)
        data = response.json()
        return data.get("results", [])[:3]
    except:
        return []


def format_name(movie, extension):
    title = movie["title"]
    year = movie["release_date"][:4] if movie.get("release_date") else "Unknown"
    return f"{title} ({year}){extension}"


class MovieRenamer(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Plex Movie Renamer")
        self.resize(1100, 600)

        self.files = []

        layout = QVBoxLayout()

        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        self.label = QLabel("Drag & drop movie files here")
        self.label.setStyleSheet("color: #aaa; font-size: 16px;")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.table = DropTable(self)
        self.table.setHorizontalHeaderLabels([
            "Original File", "Match Selection", "Preview", "Poster"
        ])

        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        self.rename_button = QPushButton("Confirm Rename")
        self.rename_button.clicked.connect(self.rename_files)

        layout.addWidget(self.label)
        layout.addWidget(self.table)
        layout.addWidget(self.rename_button)

        self.setLayout(layout)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            filepath = url.toLocalFile()

            if os.path.isfile(filepath):
                self.add_file(filepath)

    def add_file(self, filepath):
        row = self.table.rowCount()
        self.table.insertRow(row)

        filename = os.path.basename(filepath)
        name, ext = os.path.splitext(filename)

        info = guessit(filename)
        title = info.get("title")
        year = info.get("year")

        matches = search_movies(title, year) if title else []

        combo = QComboBox()

        if matches:
            for movie in matches:
                m_title = movie["title"]
                m_year = movie.get("release_date", "")[:4]
                rating = movie.get("vote_average", 0)
                display = f"{m_title} ({m_year}) ⭐ {rating:.1f}"
                combo.addItem(display, movie)
        else:
            combo.addItem("No match found", None)

        combo.currentIndexChanged.connect(
            lambda _, r=row, e=ext: self.update_preview(r, e)
        )

        self.table.setItem(row, 0, QTableWidgetItem(filename))
        self.table.setCellWidget(row, 1, combo)
        self.table.setItem(row, 2, QTableWidgetItem(""))
        self.table.setItem(row, 3, QTableWidgetItem(""))

        self.files.append(filepath)

        # Highlight low confidence
        low_confidence = False
        if not year or not matches:
            low_confidence = True

        if low_confidence:
            for col in range(3):
                item = self.table.item(row, col)
                if item:
                    item.setBackground(Qt.GlobalColor.yellow)

        self.update_preview(row, ext)

    def load_poster(self, row, movie):
        if not movie or not movie.get("poster_path"):
            return

        url = IMAGE_BASE + movie["poster_path"]

        try:
            data = requests.get(url).content
            pixmap = QPixmap()
            pixmap.loadFromData(data)

            label = QLabel()
            label.setPixmap(pixmap.scaledToWidth(80))

            self.table.setCellWidget(row, 3, label)
        except:
            pass

    def update_preview(self, row, extension):
        combo = self.table.cellWidget(row, 1)
        movie = combo.currentData()

        if movie:
            new_name = format_name(movie, extension)
            self.load_poster(row, movie)
        else:
            new_name = "No valid match"

        self.table.setItem(row, 2, QTableWidgetItem(new_name))

    def rename_files(self):
        confirm = QMessageBox.question(
            self,
            "Confirm Rename",
            "Are you sure you want to rename these files?",
        )

        if confirm != QMessageBox.StandardButton.Yes:
            return

        for row in range(self.table.rowCount()):
            filepath = self.files[row]
            combo = self.table.cellWidget(row, 1)
            movie = combo.currentData()

            if not movie:
                continue

            filename = os.path.basename(filepath)
            _, ext = os.path.splitext(filename)

            new_name = format_name(movie, ext)
            new_path = os.path.join(os.path.dirname(filepath), new_name)

            print(f"{filename} → {new_name}")

            try:
                os.rename(filepath, new_path)
            except Exception as e:
                print(f"Error renaming {filename}: {e}")

        QMessageBox.information(self, "Done", "Renaming complete!")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet("""
    QWidget {
        font-family: Segoe UI, Arial;
        font-size: 13px;
    }

    QTableWidget {
        gridline-color: #444;
        background-color: #1e1e1e;
        alternate-background-color: #252525;
        selection-background-color: #0078d7;
    }

    QHeaderView::section {
        background-color: #2d2d2d;
        padding: 6px;
        border: none;
    }

    QPushButton {
        background-color: #0078d7;
        border: none;
        padding: 10px;
        border-radius: 6px;
        font-weight: bold;
    }

    QPushButton:hover {
        background-color: #2893ff;
    }

    QPushButton:pressed {
        background-color: #005fa3;
    }

    QComboBox {
        background-color: #2d2d2d;
        padding: 5px;
        border-radius: 4px;
    }

    QLabel {
        font-size: 14px;
    }
    """)
    window = MovieRenamer()
    window.show()
    sys.exit(app.exec())
