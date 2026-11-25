"""Step 2 panel: search or drop beatmap folders, select difficulty/pattern, and add to pack."""

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QButtonGroup,
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

from osu_pack_builder.domain.naming import detectar_patron_sugerido
from osu_pack_builder.infrastructure.songs_scanner import filter_song_folders
from osu_pack_builder.ui.theme import COLOR_ACCENT_BLUE


class AddMapPanel(QFrame):
    """Panel for searching/dropping song folders, picking difficulty & pattern, and adding."""

    def __init__(
        self,
        get_folders: Callable[[], list[Path]],
        on_add_map: Callable[[Path, Path, str, str], bool],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("PanelCard")
        self.setAcceptDrops(True)
        self._get_folders = get_folders
        self._on_add_map = on_add_map

        self.carpeta_actual: Path | None = None
        self.archivos_osu: list[Path] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(7)

        title = QLabel("2. Buscar y Añadir Mapas")
        title.setStyleSheet("font-size: 15px; font-weight: bold;")
        layout.addWidget(title)

        search_row = QHBoxLayout()
        search_row.setSpacing(6)
        self.entry_buscar = QLineEdit()
        self.entry_buscar.setPlaceholderText("🔍 Buscar canción o arrastra una carpeta aquí...")
        self.entry_buscar.textChanged.connect(self._on_buscar)
        self.entry_buscar.returnPressed.connect(self._on_enter)
        search_row.addWidget(self.entry_buscar, 1)

        btn_browse = QPushButton("Examinar...")
        btn_browse.setObjectName("PrimaryBtn")
        btn_browse.clicked.connect(self._seleccionar_manual)
        search_row.addWidget(btn_browse)
        layout.addLayout(search_row)

        self.list_resultados = QListWidget()
        self.list_resultados.setMaximumHeight(140)
        self.list_resultados.hide()
        self.list_resultados.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.list_resultados)

        self.lbl_folder = QLabel("Busca una canción arriba o examina manualmente")
        self.lbl_folder.setStyleSheet("color: #9CA3AF;")
        self.lbl_folder.setWordWrap(True)
        layout.addWidget(self.lbl_folder)

        layout.addWidget(QLabel("Dificultad (.osu):"))
        self.combo_osus = QComboBox()
        self.combo_osus.addItem("(Primero busca y selecciona un mapa)")
        self.combo_osus.currentTextChanged.connect(self._on_cambio_osu)
        layout.addWidget(self.combo_osus)

        lbl_pat = QLabel("Tipo de patrón:")
        lbl_pat.setStyleSheet("font-weight: bold;")
        layout.addWidget(lbl_pat)

        self.pattern_group = QButtonGroup(self)
        self.pattern_group.setExclusive(True)
        self._pattern_buttons: dict[str, QPushButton] = {}
        row_pat = QHBoxLayout()
        row_pat.setSpacing(5)
        for opt in ("DJ", "CJ", "SJ", "ANCHOR", "Ninguno"):
            btn = QPushButton(opt)
            btn.setObjectName("SegmentedBtn")
            btn.setCheckable(True)
            btn.setChecked(opt == "Ninguno")
            self.pattern_group.addButton(btn)
            self._pattern_buttons[opt] = btn
            row_pat.addWidget(btn)
        layout.addLayout(row_pat)

        lbl_ver = QLabel("Versión parafraseada (opcional):")
        lbl_ver.setStyleSheet("font-size: 12px;")
        layout.addWidget(lbl_ver)

        self.entry_custom_version = QLineEdit()
        self.entry_custom_version.setPlaceholderText("Vacío = automático, o escribe un nombre corto...")
        layout.addWidget(self.entry_custom_version)

        self.btn_add = QPushButton("+ Añadir Dificultad al Pack")
        self.btn_add.setObjectName("SuccessBtn")
        self.btn_add.setMinimumHeight(36)
        self.btn_add.setEnabled(False)
        self.btn_add.clicked.connect(self._handle_add)
        layout.addWidget(self.btn_add)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if Path(url.toLocalFile()).is_dir():
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())
            if path.is_dir():
                self._cargar_carpeta(path)
                break

    def _on_buscar(self, texto: str) -> None:
        query = texto.strip().lower()
        self.list_resultados.clear()
        if not query:
            self.list_resultados.hide()
            return

        coincidencias = filter_song_folders(self._get_folders(), query, limit=6)
        if not coincidencias:
            item = QListWidgetItem("No se encontraron mapas en Songs")
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
        ruta = QFileDialog.getExistingDirectory(self, "Selecciona la Carpeta del Mapa")
        if ruta:
            self._cargar_carpeta(Path(ruta))

    def _cargar_carpeta(self, carpeta: Path) -> None:
        archivos_osu = [f for f in carpeta.iterdir() if f.is_file() and f.suffix == ".osu"]
        if not archivos_osu:
            QMessageBox.warning(
                self, "Atención", f"La carpeta '{carpeta.name}' no contiene archivos .osu."
            )
            return

        self.carpeta_actual = carpeta
        self.archivos_osu = archivos_osu
        self.lbl_folder.setText(f"✓ {carpeta.name}")
        self.lbl_folder.setStyleSheet(f"color: {COLOR_ACCENT_BLUE}; font-weight: bold;")

        nombres = [f.name for f in archivos_osu]
        self.combo_osus.blockSignals(True)
        self.combo_osus.clear()
        self.combo_osus.addItems(nombres)
        self.combo_osus.blockSignals(False)
        self._on_cambio_osu(nombres[0])
        self.btn_add.setEnabled(True)

    def _on_cambio_osu(self, valor_osu: str) -> None:
        sugerido = detectar_patron_sugerido(valor_osu)
        target = sugerido if sugerido in self._pattern_buttons else "Ninguno"
        self._pattern_buttons[target].setChecked(True)

    def _handle_add(self) -> None:
        if not self.carpeta_actual or not self.archivos_osu:
            return

        nombre_elegido = self.combo_osus.currentText()
        osu_elegido = next((f for f in self.archivos_osu if f.name == nombre_elegido), None)
        if not osu_elegido:
            QMessageBox.critical(self, "Error", "No se encontró el archivo .osu seleccionado.")
            return

        checked = self.pattern_group.checkedButton()
        patron = checked.text() if checked else "Ninguno"
        custom_version = self.entry_custom_version.text().strip()

        if self._on_add_map(self.carpeta_actual, osu_elegido, patron, custom_version):
            self.reset_selection()

    def reset_selection(self) -> None:
        """Reset panel inputs after successfully adding a map."""
        self.combo_osus.blockSignals(True)
        self.combo_osus.clear()
        self.combo_osus.addItem("(Busca otra canción arriba para continuar)")
        self.combo_osus.blockSignals(False)
        self._pattern_buttons["Ninguno"].setChecked(True)
        self.entry_custom_version.clear()
        self.btn_add.setEnabled(False)
        self.lbl_folder.setText("Escribe arriba para buscar y agregar el siguiente mapa...")
        self.lbl_folder.setStyleSheet("color: #9CA3AF;")
        self.carpeta_actual = None
        self.archivos_osu = []
