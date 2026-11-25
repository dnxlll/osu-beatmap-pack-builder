"""Top header bar displaying version, Songs directory, guide, and update button."""

from collections.abc import Callable
from pathlib import Path

from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from osu_pack_builder.domain.models import APP_VERSION
from osu_pack_builder.ui.dialogs import GuideDialog
from osu_pack_builder.ui.theme import COLOR_ACCENT_BLUE


class SongsHeader(QWidget):
    """Header bar with title, version, Songs indicator, guide, and update button."""

    def __init__(
        self,
        songs_dir: Path,
        map_count: int,
        on_change_songs: Callable[[], None],
        on_check_or_install_update: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        top_row = QHBoxLayout()
        title = QLabel("osu! BeatmapPack Builder")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        top_row.addWidget(title)

        lbl_ver = QLabel(f"v{APP_VERSION}")
        lbl_ver.setStyleSheet("color: #9CA3AF; font-size: 12px; padding-left: 4px;")
        top_row.addWidget(lbl_ver)
        top_row.addStretch()

        self.btn_update = QPushButton("↻ Buscar actualización")
        self.btn_update.setToolTip("Comprobar si hay una nueva versión en GitHub")
        if on_check_or_install_update is not None:
            self.btn_update.clicked.connect(on_check_or_install_update)
        top_row.addWidget(self.btn_update)

        btn_guide = QPushButton("? Guía")
        btn_guide.setToolTip("Cómo crear tu beatmap pack paso a paso")
        btn_guide.clicked.connect(self._open_guide)
        top_row.addWidget(btn_guide)

        btn_change = QPushButton("Cambiar Songs...")
        btn_change.setObjectName("PrimaryBtn")
        btn_change.clicked.connect(on_change_songs)
        top_row.addWidget(btn_change)
        layout.addLayout(top_row)

        self.lbl_songs_dir = QLabel("")
        self.lbl_songs_dir.setStyleSheet(f"color: {COLOR_ACCENT_BLUE}; font-size: 12px;")
        layout.addWidget(self.lbl_songs_dir)
        self.update_songs_info(songs_dir, map_count)

    def set_update_available(self, version: str) -> None:
        """Highlight the update button when a newer release is detected."""
        self.btn_update.setObjectName("SuccessBtn")
        self.btn_update.setText(f"⬆ Instalar v{version}")
        self.btn_update.setToolTip(f"Nueva versión v{version} disponible. Haz clic para instalar.")
        self.btn_update.style().unpolish(self.btn_update)
        self.btn_update.style().polish(self.btn_update)

    def update_songs_info(self, songs_dir: Path, map_count: int) -> None:
        """Refresh displayed Songs directory path and folder count."""
        self.lbl_songs_dir.setText(f"📁 Songs: {songs_dir} ({map_count} carpetas)")

    def _open_guide(self) -> None:
        GuideDialog(self).exec()
