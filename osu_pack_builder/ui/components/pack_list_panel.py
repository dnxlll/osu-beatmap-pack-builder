"""Right-column PySide6 panel displaying registered pack maps as a responsive card grid."""

from collections import Counter
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPixmap, QResizeEvent
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from osu_pack_builder.domain.models import AUDIO_EXTENSIONS, IMAGE_EXTENSIONS
from osu_pack_builder.domain.naming import (
    build_version_name,
    limpiar_bpm_od,
    normalize_pattern,
    parse_osu_filename,
)
from osu_pack_builder.domain.osu_file import extract_background_filename
from osu_pack_builder.infrastructure.media_processor import load_thumbnail
from osu_pack_builder.ui.theme import COLOR_PRIMARY, PATTERN_META

_THUMB_SIZE = (96, 60)


def _pil_to_qpixmap(pil_img) -> QPixmap:
    """Convert a PIL Image to an owned QPixmap."""
    rgb = pil_img.convert("RGB")
    w, h = rgb.size
    data = rgb.tobytes("raw", "RGB")
    qimg = QImage(data, w, h, w * 3, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(qimg.copy())


class PackListPanel(QFrame):
    """Interactive responsive grid of maps currently registered in pack.json."""

    def __init__(
        self,
        on_remove_map: Callable[[str], None],
        on_clear_pack: Callable[[], None],
        on_edit_map: Callable[[str], None] | None = None,
        get_songs_dir: Callable[[], Path] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("PanelCard")
        self._on_remove_map = on_remove_map
        self._on_clear_pack = on_clear_pack
        self._on_edit_map = on_edit_map
        self._get_songs_dir = get_songs_dir
        self._thumb_cache: dict[str, QPixmap | None] = {}

        self._last_pack: dict[str, dict] = {}
        self._active_filter: str = ""
        self._title_words: int | None = 1
        self._cards: list[QFrame] = []
        self._current_cols: int = 1

        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(80)
        self._resize_timer.timeout.connect(self._relayout_if_needed)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(8)

        header = QHBoxLayout()
        self.lbl_title = QLabel("Pack Actual (0 mapas)")
        self.lbl_title.setStyleSheet("font-size: 15px; font-weight: bold;")
        header.addWidget(self.lbl_title)
        header.addStretch()

        self.btn_clear = QPushButton("Vaciar")
        self.btn_clear.setObjectName("DangerBtn")
        self.btn_clear.setMinimumWidth(75)
        self.btn_clear.clicked.connect(self._on_clear_pack)
        header.addWidget(self.btn_clear)
        root.addLayout(header)

        self.filter_container = QWidget()
        self.filter_layout = QHBoxLayout(self.filter_container)
        self.filter_layout.setContentsMargins(0, 0, 0, 0)
        self.filter_layout.setSpacing(6)
        root.addWidget(self.filter_container)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.grid_host = QWidget()
        self.grid_host.setStyleSheet("background: transparent;")
        self.grid_layout = QGridLayout(self.grid_host)
        self.grid_layout.setContentsMargins(0, 0, 4, 0)
        self.grid_layout.setSpacing(8)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_area.setWidget(self.grid_host)
        root.addWidget(self.scroll_area, 1)

    @staticmethod
    def _compute_columns(width: int) -> int:
        if width >= 1060:
            return 3
        if width >= 680:
            return 2
        return 1

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._resize_timer.start()

    def _relayout_if_needed(self) -> None:
        if not self._cards:
            return
        new_cols = self._compute_columns(self.scroll_area.viewport().width())
        if new_cols != self._current_cols:
            self._current_cols = new_cols
            self._relayout_cards()

    def _relayout_cards(self) -> None:
        while self.grid_layout.count():
            self.grid_layout.takeAt(0)

        for col in range(3):
            self.grid_layout.setColumnStretch(col, 1 if col < self._current_cols else 0)

        for idx, card in enumerate(self._cards):
            row = idx // self._current_cols
            col = idx % self._current_cols
            self.grid_layout.addWidget(card, row, col)

    def set_title_words(self, title_words: int | None) -> None:
        """Update the title word-count setting and refresh difficulty previews."""
        self._title_words = title_words
        if self._last_pack:
            self.render_pack(self._last_pack)

    def _toggle_filter(self, pattern: str) -> None:
        self._active_filter = "" if self._active_filter == pattern else pattern
        self.render_pack(self._last_pack)

    def _render_filter_bar(self, valid_entries: list[tuple[str, dict]]) -> None:
        while self.filter_layout.count():
            item = self.filter_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not valid_entries:
            return

        counts = Counter(
            normalize_pattern(m.get("__pattern__") or m.get("patron"))
            for _, m in valid_entries
        )

        is_all = self._active_filter == ""
        btn_all = QPushButton(f"Todos ({len(valid_entries)})")
        btn_all.setStyleSheet(
            f"background-color: {COLOR_PRIMARY if is_all else '#2B303A'}; "
            "padding: 4px 10px; font-size: 11px;"
        )
        btn_all.clicked.connect(lambda: self._toggle_filter(""))
        self.filter_layout.addWidget(btn_all)

        for pattern, (_, color) in PATTERN_META.items():
            cnt = counts.get(pattern, 0)
            if cnt == 0:
                continue
            active = self._active_filter == pattern
            bg = color if active or is_all else "#2B303A"
            border = "border: 1px solid #FFFFFF;" if active else ""
            btn = QPushButton(f"{pattern}: {cnt}")
            btn.setStyleSheet(
                f"background-color: {bg}; {border} padding: 4px 10px; font-size: 11px;"
            )
            btn.clicked.connect(lambda _=False, p=pattern: self._toggle_filter(p))
            self.filter_layout.addWidget(btn)

        self.filter_layout.addStretch()

    def render_pack(self, pack: dict[str, dict]) -> None:
        """Rebuild the card grid from the current pack dictionary."""
        self._last_pack = pack
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._cards.clear()

        valid_entries = [(idx, m) for idx, m in pack.items() if isinstance(m, dict)]
        count = len(valid_entries)
        label_word = "mapa" if count == 1 else "mapas"
        self.lbl_title.setText(f"Pack Actual ({count} {label_word})")
        self.btn_clear.setEnabled(count > 0)

        if self._active_filter and not any(
            normalize_pattern(m.get("__pattern__") or m.get("patron")) == self._active_filter
            for _, m in valid_entries
        ):
            self._active_filter = ""

        self._render_filter_bar(valid_entries)

        if count == 0:
            empty = QLabel("El pack está vacío.\nAñade mapas desde el panel izquierdo.")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet("color: #9CA3AF; padding: 40px;")
            self.grid_layout.setColumnStretch(0, 1)
            self.grid_layout.addWidget(empty, 0, 0)
            return

        filtered = [
            (idx, m)
            for idx, m in valid_entries
            if not self._active_filter
            or normalize_pattern(m.get("__pattern__") or m.get("patron")) == self._active_filter
        ]

        self._current_cols = self._compute_columns(self.scroll_area.viewport().width())
        for indice, mapa in filtered:
            self._cards.append(self._create_map_card(indice, mapa))
        self._relayout_cards()

    def _resolve_image_path(self, mapa: dict) -> Path | None:
        image_keys = [k for k in mapa if k.lower().endswith(IMAGE_EXTENSIONS)]
        if not image_keys:
            return None

        chosen_key = image_keys[0]
        if len(image_keys) > 1:
            osu_key = next((k for k in mapa if k.endswith(".osu")), None)
            if osu_key:
                osu_path = Path(mapa[osu_key])
                if osu_path.exists():
                    declared = extract_background_filename(
                        osu_path.read_text(encoding="utf-8", errors="ignore")
                    )
                    if declared and declared in mapa:
                        chosen_key = declared

        candidate = Path(mapa[chosen_key])
        if not candidate.exists() and self._get_songs_dir is not None:
            fallback = self._get_songs_dir() / candidate.parent.name / candidate.name
            if fallback.exists():
                return fallback
        return candidate

    def _get_pixmap(self, image_path: Path | None) -> QPixmap | None:
        if not image_path:
            return None
        key = str(image_path)
        if key not in self._thumb_cache:
            pil_img = load_thumbnail(image_path, size=_THUMB_SIZE)
            self._thumb_cache[key] = _pil_to_qpixmap(pil_img) if pil_img is not None else None
        return self._thumb_cache[key]

    def _create_map_card(self, indice: str, mapa: dict) -> QFrame:
        card = QFrame()
        card.setObjectName("MapCard")

        body = QHBoxLayout(card)
        body.setContentsMargins(10, 10, 10, 10)
        body.setSpacing(10)

        img_path = self._resolve_image_path(mapa)
        pixmap = self._get_pixmap(img_path)

        thumb = QLabel()
        thumb.setFixedSize(*_THUMB_SIZE)
        thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if pixmap is not None:
            thumb.setPixmap(pixmap)
            thumb.setStyleSheet("border-radius: 6px;")
        else:
            thumb.setText("No hallada" if img_path is not None else "Sin BG")
            thumb.setStyleSheet(
                "background-color: #141619; color: #6B7280; "
                "border-radius: 6px; font-size: 10px;"
            )
        body.addWidget(thumb, 0, Qt.AlignmentFlag.AlignTop)

        info = QVBoxLayout()
        info.setSpacing(3)

        top_row = QHBoxLayout()
        top_row.setSpacing(6)
        lbl_idx = QLabel(f"#{indice}")
        lbl_idx.setStyleSheet("color: #9CA3AF; font-size: 11px; font-weight: bold;")
        top_row.addWidget(lbl_idx)

        patron = normalize_pattern(mapa.get("__pattern__") or mapa.get("patron"))
        if patron:
            badge_color = PATTERN_META.get(patron, ("", "#4A4A4A"))[1]
            badge = QLabel(patron)
            badge.setStyleSheet(
                f"background-color: {badge_color}; color: white; font-size: 10px; "
                "font-weight: bold; padding: 2px 6px; border-radius: 4px;"
            )
            top_row.addWidget(badge)

        top_row.addStretch()

        if self._on_edit_map is not None:
            btn_edit = QPushButton("✎")
            btn_edit.setObjectName("IconBtn")
            btn_edit.setFixedSize(24, 22)
            btn_edit.clicked.connect(lambda _=False, i=indice: self._on_edit_map(i))
            top_row.addWidget(btn_edit)

        btn_del = QPushButton("✕")
        btn_del.setObjectName("IconDangerBtn")
        btn_del.setFixedSize(24, 22)
        btn_del.clicked.connect(lambda _=False, i=indice: self._on_remove_map(i))
        top_row.addWidget(btn_del)
        info.addLayout(top_row)

        osu_name = next((k for k in mapa if k.endswith(".osu")), "Desconocido")
        lbl_title = QLabel(limpiar_bpm_od(osu_name))
        lbl_title.setWordWrap(True)
        lbl_title.setStyleSheet("font-size: 12px; font-weight: bold;")
        info.addWidget(lbl_title)

        custom_v = mapa.get("__custom_version__")
        if custom_v:
            preview_text = f"✎ {custom_v}"
            preview_color = "#8CC8FF"
        else:
            auto_v = build_version_name(
                parse_osu_filename(osu_name, title_words=self._title_words),
                pattern=patron,
            )
            preview_text = f"→ {auto_v}"
            preview_color = "#A8B3C2"

        lbl_preview = QLabel(preview_text)
        lbl_preview.setWordWrap(True)
        lbl_preview.setStyleSheet(f"color: {preview_color}; font-size: 11px;")
        info.addWidget(lbl_preview)

        audio_name = next(
            (k for k in mapa if k.lower().endswith(AUDIO_EXTENSIONS)),
            "Sin audio",
        )
        lbl_audio = QLabel(f"🎵 {audio_name}")
        lbl_audio.setStyleSheet("color: #9CA3AF; font-size: 11px;")
        info.addWidget(lbl_audio)

        body.addLayout(info, 1)
        return card
