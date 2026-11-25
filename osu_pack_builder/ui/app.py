"""Main PySide6 application window with 2-column split-view and background generation."""

import logging
import threading
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from osu_pack_builder.application.add_map import add_map_to_pack
from osu_pack_builder.application.generate_pack import generate_pack
from osu_pack_builder.application.remove_map import remove_map_from_pack
from osu_pack_builder.application.update_map import clear_custom_versions, update_map_in_pack
from osu_pack_builder.domain.models import MAX_OSU_FILENAME_LEN
from osu_pack_builder.domain.naming import (
    build_version_name,
    detectar_patron_sugerido,
    normalize_pattern,
    parse_osu_filename,
)
from osu_pack_builder.infrastructure.pack_repository import PackRepository
from osu_pack_builder.infrastructure.songs_scanner import detect_songs_dir, list_song_folders
from osu_pack_builder.ui.components.add_map_panel import AddMapPanel
from osu_pack_builder.ui.components.base_map_panel import BaseMapPanel
from osu_pack_builder.ui.components.pack_list_panel import PackListPanel
from osu_pack_builder.ui.components.songs_header import SongsHeader
from osu_pack_builder.ui.dialogs import (
    EditMapDialog,
    ParafraseoDialog,
    PatronModalDialog,
    TitleCutterScopeDialog,
)

logger = logging.getLogger(__name__)

_TITLE_WORD_OPTIONS: dict[str, int | None] = {
    "1 palabra": 1,
    "2 palabras": 2,
    "3 palabras": 3,
    "Completo": None,
}


class _GeneratePackWorker(QThread):
    """Background worker running generate_pack without freezing the Qt event loop."""

    paraphrase_requested = Signal(str, str, str, str)
    finished_ok = Signal(object, int)
    failed = Signal(str)

    def __init__(
        self,
        init_file: Path,
        repository: PackRepository,
        default_creator: str,
        title_words: int | None,
    ) -> None:
        super().__init__()
        self._init_file = init_file
        self._repository = repository
        self._default_creator = default_creator
        self._title_words = title_words
        self._reply_event = threading.Event()
        self._reply_value: str = ""

    def provide_paraphrase_reply(self, value: str) -> None:
        """Supply the user's paraphrased name from the GUI thread and resume."""
        self._reply_value = value
        self._reply_event.set()

    def _ask_paraphrase(
        self,
        indice: str,
        clave_osu: str,
        version_original: str,
        prefix_base: str,
    ) -> str:
        self._reply_event.clear()
        self.paraphrase_requested.emit(indice, clave_osu, version_original, prefix_base)
        self._reply_event.wait()
        return self._reply_value

    def run(self) -> None:
        try:
            out_dir, count = generate_pack(
                self._init_file,
                repository=self._repository,
                callback_parafraseo=self._ask_paraphrase,
                default_creator=self._default_creator,
                title_words=self._title_words,
            )
            self.finished_ok.emit(out_dir, count)
        except Exception as exc:
            logger.exception("Error inesperado al generar el pack")
            self.failed.emit(str(exc))


class BeatmapPackApp(QMainWindow):
    """Main PySide6 window orchestrating the 2-column split-view beatmap pack workflow."""

    def __init__(self, repository: PackRepository, default_creator: str = "") -> None:
        super().__init__()

        self.repository = repository
        self.default_creator = default_creator

        self.setWindowTitle("osu! BeatmapPack Builder")
        self.resize(1060, 740)
        self.setMinimumSize(900, 620)

        self.songs_dir: Path = detect_songs_dir()
        self.carpetas_songs: list[Path] = []
        self._current_title_words_label: str = "1 palabra"
        self._worker: _GeneratePackWorker | None = None

        self._cargar_indice_songs()
        self._build_layout()
        self._refresh_pack_list()

    def _cargar_indice_songs(self) -> None:
        try:
            self.carpetas_songs = list_song_folders(self.songs_dir)
        except OSError as exc:
            logger.error("No se pudo leer el directorio Songs: %s", exc)
            QMessageBox.warning(
                self,
                "Error al leer Songs",
                f"No se pudo leer el directorio Songs:\n{exc}\n\n"
                "Usa 'Cambiar Songs...' para seleccionar otro.",
            )
            self.carpetas_songs = []

    def _build_layout(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 10, 16, 14)
        root.setSpacing(10)

        self.header = SongsHeader(
            songs_dir=self.songs_dir,
            map_count=len(self.carpetas_songs),
            on_change_songs=self._cambiar_directorio_songs,
        )
        root.addWidget(self.header)

        workspace = QHBoxLayout()
        workspace.setSpacing(14)
        root.addLayout(workspace, 1)

        # Left column: fixed comfortable width inside a clean scroll area
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFixedWidth(445)
        left_host = QWidget()
        left_host.setStyleSheet("background: transparent;")
        left_layout = QVBoxLayout(left_host)
        left_layout.setContentsMargins(0, 0, 6, 0)
        left_layout.setSpacing(10)

        self.base_panel = BaseMapPanel(get_folders=lambda: self.carpetas_songs)
        left_layout.addWidget(self.base_panel)

        self.add_panel = AddMapPanel(
            get_folders=lambda: self.carpetas_songs,
            on_add_map=self._handle_add_map,
        )
        left_layout.addWidget(self.add_panel)

        cutter_card = QFrame()
        cutter_card.setObjectName("PanelCard")
        cutter_layout = QVBoxLayout(cutter_card)
        cutter_layout.setContentsMargins(14, 12, 14, 12)
        cutter_layout.setSpacing(8)

        cutter_title = QLabel("3. Cortador de Nombre de Dificultad")
        cutter_title.setStyleSheet("font-size: 14px; font-weight: bold;")
        cutter_layout.addWidget(cutter_title)

        self.title_words_group = QButtonGroup(self)
        self.title_words_group.setExclusive(True)
        self._title_word_buttons: dict[str, QPushButton] = {}
        row_cutter = QHBoxLayout()
        row_cutter.setSpacing(6)
        for label in _TITLE_WORD_OPTIONS:
            btn = QPushButton(label)
            btn.setObjectName("SegmentedBtn")
            btn.setCheckable(True)
            btn.setChecked(label == "1 palabra")
            btn.clicked.connect(lambda _=False, lbl=label: self._on_title_words_change(lbl))
            self.title_words_group.addButton(btn)
            self._title_word_buttons[label] = btn
            row_cutter.addWidget(btn)
        cutter_layout.addLayout(row_cutter)
        left_layout.addWidget(cutter_card)
        left_layout.addStretch()

        left_scroll.setWidget(left_host)
        workspace.addWidget(left_scroll)

        # Right column: expanding pack gallery + progress bar + generate button
        right_col = QVBoxLayout()
        right_col.setSpacing(10)

        self.pack_panel = PackListPanel(
            on_remove_map=self._handle_remove_map,
            on_clear_pack=self._handle_clear_pack,
            on_edit_map=self._handle_edit_map,
            get_songs_dir=lambda: self.songs_dir,
        )
        right_col.addWidget(self.pack_panel, 1)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.hide()
        right_col.addWidget(self.progress_bar)

        self.btn_generate = QPushButton("⚡ Generar Pack de Mapas Final")
        self.btn_generate.setObjectName("PrimaryBtn")
        self.btn_generate.setMinimumHeight(46)
        self.btn_generate.setStyleSheet("font-size: 15px; font-weight: bold;")
        self.btn_generate.clicked.connect(self._generar_pack_final)
        right_col.addWidget(self.btn_generate)

        workspace.addLayout(right_col, 1)

    def _on_title_words_change(self, selection: str) -> None:
        if selection == self._current_title_words_label:
            return

        pack = self.repository.load()
        manual_count = sum(
            1 for m in pack.values() if isinstance(m, dict) and m.get("__custom_version__")
        )
        if manual_count > 0:
            dialogo = TitleCutterScopeDialog(self, selection_label=selection, manual_count=manual_count)
            if dialogo.exec() != TitleCutterScopeDialog.DialogCode.Accepted or not dialogo.resultado:
                self._title_word_buttons[self._current_title_words_label].setChecked(True)
                return
            if dialogo.resultado == "all":
                pack = clear_custom_versions(self.repository)

        self._current_title_words_label = selection
        self.pack_panel.set_title_words(_TITLE_WORD_OPTIONS.get(selection, 1))
        if pack:
            self.pack_panel.render_pack(pack)

    def _cambiar_directorio_songs(self) -> None:
        nueva_ruta = QFileDialog.getExistingDirectory(self, "Selecciona tu carpeta Songs de osu!")
        if nueva_ruta:
            self.songs_dir = Path(nueva_ruta)
            self._cargar_indice_songs()
            self.header.update_songs_info(self.songs_dir, len(self.carpetas_songs))

    def _handle_add_map(
        self,
        carpeta: Path,
        osu_elegido: Path,
        patron_actual: str,
        version_personalizada: str,
    ) -> bool:
        if not patron_actual or patron_actual == "Ninguno":
            sugerido = detectar_patron_sugerido(osu_elegido.name)
            dialogo = PatronModalDialog(self, map_name=osu_elegido.name, sugerido=sugerido)
            if dialogo.exec() != PatronModalDialog.DialogCode.Accepted or dialogo.resultado is None:
                return False
            patron_actual = dialogo.resultado

        patron_para_guardar = normalize_pattern(patron_actual)

        try:
            indice, pack = add_map_to_pack(
                carpeta,
                osu_elegido,
                repository=self.repository,
                patron=patron_para_guardar,
                custom_version=version_personalizada,
            )
            tag_msg = f" [{patron_para_guardar}]" if patron_para_guardar else ""
            QMessageBox.information(
                self, "Éxito", f"Dificultad{tag_msg} agregada al pack con índice '{indice}'."
            )
            self.pack_panel.render_pack(pack)
            return True
        except Exception as exc:
            logger.exception("Error al agregar mapa al pack")
            QMessageBox.critical(
                self, "Error al guardar", f"Ocurrió un error al procesar el mapa:\n{exc}"
            )
            return False

    def _handle_edit_map(self, indice: str) -> None:
        pack = self.repository.load()
        mapa = pack.get(indice)
        if not isinstance(mapa, dict):
            return

        osu_key = next((k for k in mapa if k.endswith(".osu")), "")
        available_osus: list[Path] = []
        folder: Path | None = None

        if osu_key:
            candidate_dir = Path(mapa[osu_key]).parent
            if not candidate_dir.exists():
                fallback_dir = self.songs_dir / candidate_dir.name
                if fallback_dir.exists():
                    candidate_dir = fallback_dir
            if candidate_dir.exists() and candidate_dir.is_dir():
                folder = candidate_dir
                available_osus = [
                    f for f in candidate_dir.iterdir() if f.is_file() and f.suffix == ".osu"
                ]

        current_pattern = normalize_pattern(mapa.get("__pattern__") or mapa.get("patron"))
        current_custom = mapa.get("__custom_version__") or ""
        title_words = _TITLE_WORD_OPTIONS.get(self._current_title_words_label, 1)
        suggested_version = (
            build_version_name(
                parse_osu_filename(osu_key, title_words=title_words),
                pattern=current_pattern,
            )
            if osu_key and not current_custom
            else ""
        )

        dialogo = EditMapDialog(
            self,
            indice=indice,
            current_osu_name=osu_key,
            available_osus=available_osus,
            current_pattern=current_pattern,
            current_custom_version=current_custom,
            suggested_version=suggested_version,
        )
        if dialogo.exec() != EditMapDialog.DialogCode.Accepted or dialogo.resultado is None:
            return

        selected_osu, new_pattern, new_custom = dialogo.resultado
        try:
            updated_pack = update_map_in_pack(
                index=indice,
                repository=self.repository,
                patron=new_pattern,
                custom_version=new_custom,
                folder=folder if selected_osu is not None else None,
                selected_osu=selected_osu,
            )
            self.pack_panel.render_pack(updated_pack)
        except Exception as exc:
            logger.exception("Error al editar mapa #%s", indice)
            QMessageBox.critical(self, "Error al editar", f"No se pudo actualizar el mapa:\n{exc}")

    def _handle_remove_map(self, indice: str) -> None:
        try:
            pack = remove_map_from_pack(indice, self.repository)
            self.pack_panel.render_pack(pack)
        except OSError as exc:
            logger.exception("Error al eliminar mapa #%s", indice)
            QMessageBox.critical(self, "Error", f"No se pudo eliminar el mapa:\n{exc}")

    def _handle_clear_pack(self) -> None:
        reply = QMessageBox.question(
            self, "Confirmar", "¿Seguro que deseas vaciar pack.json?"
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self.repository.clear()
            self._refresh_pack_list()
            QMessageBox.information(self, "Listo", "pack.json ha sido reseteado.")
        except OSError as exc:
            QMessageBox.critical(self, "Error", f"No se pudo vaciar pack.json:\n{exc}")

    def _refresh_pack_list(self) -> None:
        self.pack_panel.render_pack(self.repository.load())

    def _on_worker_paraphrase(
        self,
        indice: str,
        clave_osu: str,
        version_original: str,
        prefix_base: str,
    ) -> None:
        dialogo = ParafraseoDialog(
            self,
            prefix_base=prefix_base,
            version_original=version_original,
            max_len=MAX_OSU_FILENAME_LEN,
        )
        if dialogo.exec() == ParafraseoDialog.DialogCode.Accepted and dialogo.resultado:
            reply = dialogo.resultado
        else:
            reply = version_original
        if self._worker is not None:
            self._worker.provide_paraphrase_reply(reply)

    def _on_worker_finished(self, carpeta_generada: Path, cantidad: int) -> None:
        self.progress_bar.hide()
        self.btn_generate.setEnabled(True)
        self.btn_generate.setText("⚡ Generar Pack de Mapas Final")
        self._worker = None
        QMessageBox.information(
            self,
            "¡Pack Generado con Éxito!",
            f"Se generaron {cantidad} archivo(s) .osu correctamente en tu carpeta de canciones:\n"
            f"{carpeta_generada.resolve()}",
        )
        self._refresh_pack_list()

    def _on_worker_failed(self, error_msg: str) -> None:
        self.progress_bar.hide()
        self.btn_generate.setEnabled(True)
        self.btn_generate.setText("⚡ Generar Pack de Mapas Final")
        self._worker = None
        QMessageBox.critical(
            self, "Error al generar", f"Ocurrió un error inesperado al generar el pack:\n{error_msg}"
        )

    def _generar_pack_final(self) -> None:
        init_file = self.base_panel.init_file
        if not init_file or not init_file.exists():
            QMessageBox.critical(
                self,
                "Falta Archivo Base",
                "Debes completar el Paso 1 y seleccionar una carpeta base válida que contenga init_file.",
            )
            return

        if not self.repository.load():
            QMessageBox.critical(
                self,
                "Pack Vacío",
                "Debes agregar al menos un mapa antes de generar el pack.",
            )
            return

        self.btn_generate.setEnabled(False)
        self.btn_generate.setText("⏳ Generando Pack...")
        self.progress_bar.show()

        title_words = _TITLE_WORD_OPTIONS.get(self._current_title_words_label, 1)
        self._worker = _GeneratePackWorker(
            init_file=init_file,
            repository=self.repository,
            default_creator=self.default_creator,
            title_words=title_words,
        )
        self._worker.paraphrase_requested.connect(self._on_worker_paraphrase)
        self._worker.finished_ok.connect(self._on_worker_finished)
        self._worker.failed.connect(self._on_worker_failed)
        self._worker.start()
