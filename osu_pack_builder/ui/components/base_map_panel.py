"""Step 1 panel: base pack folder and init_file selection."""

import shutil
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from osu_pack_builder.infrastructure.app_paths import get_marathon_audio_path
from osu_pack_builder.infrastructure.songs_scanner import filter_song_folders
from osu_pack_builder.ui.theme import COLOR_ERROR_TEXT, COLOR_SUCCESS


class BaseMapPanel(QFrame):
    """Panel for searching or browsing the base beatmap folder (init_file)."""

    def __init__(
        self,
        get_folders: Callable[[], list[Path]],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("PanelCard")
        self._get_folders = get_folders
        self.init_file: Path | None = None
        self.archivos_base_disponibles: list[Path] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        header_row = QHBoxLayout()
        title = QLabel("1. Carpeta Base (init_file)")
        title.setStyleSheet("font-size: 15px; font-weight: bold;")
        header_row.addWidget(title)
        header_row.addStretch()

        btn_marathon = QPushButton("⬇ MARATHON.mp3 (10m)")
        btn_marathon.setToolTip(
            "Guarda el audio base de 10 minutos para crear tu mapa init_file en osu!"
        )
        btn_marathon.setStyleSheet("padding: 3px 8px; font-size: 11px;")
        btn_marathon.clicked.connect(self._descargar_marathon)
        header_row.addWidget(btn_marathon)
        layout.addLayout(header_row)

        search_row = QHBoxLayout()
        search_row.setSpacing(6)
        self.entry_buscar = QLineEdit()
        self.entry_buscar.setPlaceholderText("🔍 Buscar carpeta base en Songs (ej. ScriptTest)...")
        self.entry_buscar.textChanged.connect(self._on_buscar)
        self.entry_buscar.returnPressed.connect(self._on_enter)
        search_row.addWidget(self.entry_buscar, 1)

        btn_browse = QPushButton("Examinar...")
        btn_browse.setObjectName("PrimaryBtn")
        btn_browse.clicked.connect(self._seleccionar_manual)
        search_row.addWidget(btn_browse)
        layout.addLayout(search_row)

        self.list_resultados = QListWidget()
        self.list_resultados.setMaximumHeight(130)
        self.list_resultados.hide()
        self.list_resultados.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.list_resultados)

        self.combo_init = QComboBox()
        self.combo_init.hide()
        self.combo_init.currentTextChanged.connect(self._cambiar_init_file)
        layout.addWidget(self.combo_init)

        self.lbl_status = QLabel("⚠️ Ninguna carpeta base seleccionada")
        self.lbl_status.setStyleSheet("color: #9CA3AF;")
        self.lbl_status.setWordWrap(True)
        layout.addWidget(self.lbl_status)

    def _on_buscar(self, texto: str) -> None:
        query = texto.strip().lower()
        self.list_resultados.clear()
        if not query:
            self.list_resultados.hide()
            return

        coincidencias = filter_song_folders(self._get_folders(), query, limit=6)
        if not coincidencias:
            item = QListWidgetItem("Sin coincidencias")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.list_resultados.addItem(item)
        else:
            for carpeta in coincidencias:
                item = QListWidgetItem(f"📁 {carpeta.name}")
                item.setData(Qt.ItemDataRole.UserRole, carpeta)
                self.list_resultados.addItem(item)
        self.list_resultados.show()

    def _on_enter(self) -> None:
        coincidencias = filter_song_folders(self._get_folders(), self.entry_buscar.text(), limit=1)
        if coincidencias:
            self._elegir_desde_busqueda(coincidencias[0])

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        carpeta = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(carpeta, Path):
            self._elegir_desde_busqueda(carpeta)

    def _elegir_desde_busqueda(self, carpeta: Path) -> None:
        self.entry_buscar.clear()
        self.list_resultados.hide()
        self._cargar_carpeta(carpeta)

    def _seleccionar_manual(self) -> None:
        ruta = QFileDialog.getExistingDirectory(self, "Selecciona la Carpeta Base (con init_file)")
        if ruta:
            self._cargar_carpeta(Path(ruta))

    def _cargar_carpeta(self, carpeta: Path) -> None:
        archivos_osu = list(carpeta.glob("*.osu"))
        if not archivos_osu:
            QMessageBox.critical(
                self,
                "Error",
                f"No se encontró ningún archivo .osu en:\n{carpeta.name}\n"
                "Asegúrate de que contenga el archivo base .osu.",
            )
            self.init_file = None
            self.combo_init.hide()
            self.lbl_status.setText("Error: no se encontró archivo .osu")
            self.lbl_status.setStyleSheet(f"color: {COLOR_ERROR_TEXT};")
            return

        self.archivos_base_disponibles = archivos_osu
        nombres = [f.name for f in archivos_osu]
        archivos_delete = [f for f in archivos_osu if "delete" in f.name.lower()]
        predeterminado = archivos_delete[0] if archivos_delete else archivos_osu[0]
        self.init_file = predeterminado

        self.combo_init.blockSignals(True)
        self.combo_init.clear()
        self.combo_init.addItems(nombres)
        self.combo_init.setCurrentText(predeterminado.name)
        self.combo_init.blockSignals(False)

        if len(archivos_osu) > 1:
            self.combo_init.show()
            self.lbl_status.setText(f"✓ Base seleccionada: {predeterminado.name}")
        else:
            self.combo_init.hide()
            self.lbl_status.setText(f"✓ Archivo base: {self.init_file.name}")
        self.lbl_status.setStyleSheet(f"color: {COLOR_SUCCESS}; font-weight: bold;")

    def _cambiar_init_file(self, nombre_elegido: str) -> None:
        for f in self.archivos_base_disponibles:
            if f.name == nombre_elegido:
                self.init_file = f
                self.lbl_status.setText(f"✓ Base seleccionada: {self.init_file.name}")
                self.lbl_status.setStyleSheet(f"color: {COLOR_SUCCESS}; font-weight: bold;")
                break

    def _descargar_marathon(self) -> None:
        src = get_marathon_audio_path()
        if not src.exists():
            QMessageBox.warning(
                self,
                "Archivo no disponible",
                f"No se encontró el audio base en:\n{src}",
            )
            return

        dest, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar audio base MARATHON.mp3",
            "MARATHON.mp3",
            "Audio MP3 (*.mp3)",
        )
        if not dest:
            return

        try:
            shutil.copyfile(src, dest)
            QMessageBox.information(
                self,
                "Audio guardado",
                f"MARATHON.mp3 guardado en:\n{dest}\n\n"
                "Arrástralo a osu! para crear la dificultad base (init_file).",
            )
        except OSError as exc:
            QMessageBox.critical(self, "Error al guardar", f"No se pudo guardar el archivo:\n{exc}")
