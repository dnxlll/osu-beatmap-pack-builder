"""PySide6 modal dialogs for pattern selection, paraphrasing, editing, and title cutter."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from osu_pack_builder.domain.models import MAX_OSU_FILENAME_LEN
from osu_pack_builder.domain.naming import limpiar_bpm_od, normalize_pattern
from osu_pack_builder.ui.theme import (
    COLOR_ACCENT_BLUE,
    COLOR_ERROR_TEXT,
    COLOR_SUCCESS,
    COLOR_WARNING,
    PATTERN_META,
)


class PatronModalDialog(QDialog):
    """Modal dialog asking the user to select a pattern type (DJ, CJ, SJ, ANCHOR, or None)."""

    def __init__(self, parent: QWidget | None, map_name: str, sugerido: str = "") -> None:
        super().__init__(parent)
        self.setWindowTitle("Tipo de Patrón")
        self.setFixedSize(480, 240)
        self.resultado: str | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(10)

        title = QLabel("🎯 Selecciona el Tipo de Patrón")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        subtitle = QLabel(f"¿Qué tipo de patrón corresponde a este mapa?\n{limpiar_bpm_od(map_name)}")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(f"color: {COLOR_ACCENT_BLUE}; font-size: 12px;")
        layout.addWidget(subtitle)

        row_patterns = QHBoxLayout()
        row_patterns.setSpacing(8)
        for code, (desc, color) in PATTERN_META.items():
            bg = COLOR_SUCCESS if code == sugerido else color
            btn = QPushButton(f"{code}\n({desc})")
            btn.setMinimumHeight(52)
            btn.setStyleSheet(
                f"background-color: {bg}; color: white; font-weight: bold; border-radius: 6px;"
            )
            btn.clicked.connect(lambda _=False, c=code: self._seleccionar(c))
            row_patterns.addWidget(btn)
        layout.addLayout(row_patterns)

        row_bottom = QHBoxLayout()
        btn_none = QPushButton("Sin Patrón (Ninguno)")
        btn_none.clicked.connect(lambda: self._seleccionar(""))
        row_bottom.addWidget(btn_none)

        row_bottom.addStretch()

        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setObjectName("DangerBtn")
        btn_cancel.setMinimumWidth(95)
        btn_cancel.clicked.connect(self.reject)
        row_bottom.addWidget(btn_cancel)
        layout.addLayout(row_bottom)

    def _seleccionar(self, valor: str) -> None:
        self.resultado = valor
        self.accept()


class ParafraseoDialog(QDialog):
    """Modal dialog shown when a generated .osu filename exceeds osu!'s safe length limit."""

    def __init__(
        self,
        parent: QWidget | None,
        prefix_base: str,
        version_original: str,
        max_len: int = MAX_OSU_FILENAME_LEN,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("⚠️ Nombre Demasiado Largo")
        self.setMinimumSize(540, 340)
        self.prefix_base = prefix_base
        self.max_len = max_len
        self.resultado: str | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(10)

        title = QLabel("⚠️ Nombre de Archivo Demasiado Largo")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color: {COLOR_WARNING}; font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        desc = QLabel(
            "El nombre sumado al prefijo del pack supera los 125 caracteres seguros para osu!.\n"
            "Por favor, parafrasea o acorta el nombre de esta dificultad."
        )
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #9CA3AF; font-size: 12px;")
        layout.addWidget(desc)

        card = QFrame()
        card.setObjectName("PanelCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 12, 14, 12)
        card_layout.setSpacing(6)

        lbl_prefix = QLabel(f"Prefijo del pack ({len(self.prefix_base)} chars): {self.prefix_base}")
        lbl_prefix.setWordWrap(True)
        lbl_prefix.setStyleSheet("color: #9CA3AF; font-size: 11px;")
        card_layout.addWidget(lbl_prefix)

        lbl_field = QLabel("Nombre de la dificultad / versión a acortar:")
        lbl_field.setStyleSheet("font-weight: bold;")
        card_layout.addWidget(lbl_field)

        self.entry_version = QLineEdit(version_original)
        self.entry_version.textChanged.connect(self._actualizar_contador)
        card_layout.addWidget(self.entry_version)

        self.lbl_contador = QLabel("")
        self.lbl_contador.setStyleSheet("font-weight: bold;")
        card_layout.addWidget(self.lbl_contador)
        layout.addWidget(card)

        actions = QHBoxLayout()
        self.btn_guardar = QPushButton("✓ Usar este Nombre")
        self.btn_guardar.setObjectName("SuccessBtn")
        self.btn_guardar.setMinimumHeight(36)
        self.btn_guardar.clicked.connect(self._confirmar)
        actions.addWidget(self.btn_guardar, 1)

        btn_skip = QPushButton("Omitir (dejar largo)")
        btn_skip.setMinimumHeight(36)
        btn_skip.clicked.connect(lambda: self._finalizar(version_original))
        actions.addWidget(btn_skip)
        layout.addLayout(actions)

        self._actualizar_contador()

    def _actualizar_contador(self) -> None:
        val = self.entry_version.text().strip()
        total_len = len(f"{self.prefix_base} [{val}].osu")
        if total_len <= self.max_len:
            self.lbl_contador.setText(
                f"✓ Longitud total: {total_len} / {self.max_len} caracteres (Seguro para osu!)"
            )
            self.lbl_contador.setStyleSheet(f"color: {COLOR_SUCCESS}; font-weight: bold;")
            self.btn_guardar.setEnabled(True)
        else:
            exceso = total_len - self.max_len
            self.lbl_contador.setText(
                f"⚠️ Longitud total: {total_len} / {self.max_len} (+{exceso} exceso, ¡acorta!)"
            )
            self.lbl_contador.setStyleSheet(f"color: {COLOR_ERROR_TEXT}; font-weight: bold;")
            self.btn_guardar.setEnabled(False)

    def _confirmar(self) -> None:
        val = self.entry_version.text().strip()
        if not val:
            QMessageBox.warning(self, "Atención", "El nombre no puede estar vacío.")
            return
        self._finalizar(val)

    def _finalizar(self, valor: str) -> None:
        self.resultado = valor
        self.accept()


class EditMapDialog(QDialog):
    """Modal dialog for editing an existing map's difficulty (.osu), pattern, and custom version."""

    def __init__(
        self,
        parent: QWidget | None,
        indice: str,
        current_osu_name: str,
        available_osus: list[Path],
        current_pattern: str = "",
        current_custom_version: str = "",
        suggested_version: str = "",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Editar Mapa #{indice}")
        self.setMinimumSize(520, 340)

        self._available_osus = available_osus
        self._had_custom = bool(current_custom_version.strip())
        self._initial_suggested = suggested_version.strip()
        self.resultado: tuple[Path | None, str, str] | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(10)

        title = QLabel(f"✎ Editar Mapa #{indice}")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        lbl_osu = QLabel("Dificultad (.osu) — actualiza audio e imagen automáticamente:")
        lbl_osu.setStyleSheet("font-weight: bold;")
        layout.addWidget(lbl_osu)

        self.combo_osu = QComboBox()
        if available_osus:
            osu_names = [p.name for p in available_osus]
            self.combo_osu.addItems(osu_names)
            if current_osu_name in osu_names:
                self.combo_osu.setCurrentText(current_osu_name)
        else:
            self.combo_osu.addItem(f"{current_osu_name} (carpeta no disponible)")
            self.combo_osu.setEnabled(False)
        layout.addWidget(self.combo_osu)

        lbl_pat = QLabel("Tipo de patrón:")
        lbl_pat.setStyleSheet("font-weight: bold;")
        layout.addWidget(lbl_pat)

        self.pattern_group = QButtonGroup(self)
        self.pattern_group.setExclusive(True)
        row_pat = QHBoxLayout()
        row_pat.setSpacing(6)
        norm = normalize_pattern(current_pattern) or "Ninguno"
        for opt in ("DJ", "CJ", "SJ", "ANCHOR", "Ninguno"):
            btn = QPushButton(opt)
            btn.setObjectName("SegmentedBtn")
            btn.setCheckable(True)
            btn.setChecked(opt == norm)
            self.pattern_group.addButton(btn)
            row_pat.addWidget(btn)
        layout.addLayout(row_pat)

        lbl_ver = QLabel("Versión parafraseada (opcional):")
        lbl_ver.setStyleSheet("font-weight: bold;")
        layout.addWidget(lbl_ver)

        self.entry_custom = QLineEdit()
        self.entry_custom.setPlaceholderText("Vacío = automático, o escribe un nombre corto...")
        prefill = current_custom_version.strip() or self._initial_suggested
        if prefill:
            self.entry_custom.setText(prefill)
        layout.addWidget(self.entry_custom)

        actions = QHBoxLayout()
        btn_save = QPushButton("✓ Guardar Cambios")
        btn_save.setObjectName("SuccessBtn")
        btn_save.setMinimumHeight(36)
        btn_save.clicked.connect(self._guardar)
        actions.addWidget(btn_save, 1)

        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setMinimumHeight(36)
        btn_cancel.setMinimumWidth(100)
        btn_cancel.clicked.connect(self.reject)
        actions.addWidget(btn_cancel)
        layout.addLayout(actions)

    def _guardar(self) -> None:
        selected_osu: Path | None = None
        if self._available_osus:
            chosen_name = self.combo_osu.currentText()
            selected_osu = next(
                (p for p in self._available_osus if p.name == chosen_name),
                None,
            )
        checked_btn = self.pattern_group.checkedButton()
        patron = normalize_pattern(checked_btn.text() if checked_btn else "")
        entered = self.entry_custom.text().strip()
        custom_version = "" if not self._had_custom and entered == self._initial_suggested else entered
        self.resultado = (selected_osu, patron, custom_version)
        self.accept()


class TitleCutterScopeDialog(QDialog):
    """Modal dialog asking whether the title cutter applies to all maps or only auto-named ones."""

    def __init__(self, parent: QWidget | None, selection_label: str, manual_count: int) -> None:
        super().__init__(parent)
        self.setWindowTitle("Aplicar Cortador de Título")
        self.setFixedSize(460, 210)
        self.resultado: str | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(10)

        title = QLabel(f"Aplicar cortador: '{selection_label}'")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 15px; font-weight: bold;")
        layout.addWidget(title)

        desc = QLabel(
            f"Hay {manual_count} mapa(s) con versión parafraseada manual.\n"
            "¿Cómo deseas aplicar este recorte?"
        )
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setStyleSheet("color: #9CA3AF; font-size: 12px;")
        layout.addWidget(desc)

        btn_all = QPushButton("Parafrasear TODOS los mapas según el cortador")
        btn_all.setObjectName("PrimaryBtn")
        btn_all.setMinimumHeight(34)
        btn_all.clicked.connect(lambda: self._select("all"))
        layout.addWidget(btn_all)

        btn_auto = QPushButton("Solo recortar los que NO tienen versión manual")
        btn_auto.setObjectName("SuccessBtn")
        btn_auto.setMinimumHeight(34)
        btn_auto.clicked.connect(lambda: self._select("auto_only"))
        layout.addWidget(btn_auto)

        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setMinimumHeight(28)
        btn_cancel.clicked.connect(self.reject)
        layout.addWidget(btn_cancel, alignment=Qt.AlignmentFlag.AlignCenter)

    def _select(self, mode: str) -> None:
        self.resultado = mode
        self.accept()


class GuideDialog(QDialog):
    """Step-by-step beginner guide explaining init_file and pack creation."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Guía: Cómo crear tu Beatmap Pack")
        self.setMinimumSize(580, 520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(10)

        title = QLabel("📖 Guía paso a paso — Cómo crear tu Beatmap Pack")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        browser = QTextBrowser()
        browser.setStyleSheet(
            "background-color: #1C1F24; color: #EAECEF; border: 1px solid #2B303A; "
            "border-radius: 8px; padding: 12px; font-size: 13px;"
        )
        browser.setHtml(
            """
            <h3 style="color:#4DA3E8; margin-top:0;">¿Qué es el <code>init_file</code> (Carpeta Base)?</h3>
            <p>Es un mapa plantilla en tu carpeta de osu! que define el <b>Título del Pack,
            Artista, Creador, Tags</b> y la <b>carpeta destino</b> donde se guardarán
            todas las dificultades del pack.</p>

            <h3 style="color:#2FA572;">Paso 1 — Crear tu <code>init_file</code> en osu!</h3>
            <ol>
              <li>Pulsa <b>⬇ MARATHON.mp3 (10m)</b> en la sección 1 y guarda el audio.</li>
              <li>Arrastra ese <code>MARATHON.mp3</code> dentro de <b>osu!</b> para crear un mapa nuevo.</li>
              <li>En el editor, llena los metadatos del pack (<i>Title, Artist, Creator, Tags</i>),
                  pon una dificultad llamada por ejemplo <code>delete</code> y guarda (<b>Ctrl+S</b>).</li>
            </ol>

            <h3 style="color:#2FA572;">Paso 2 — Seleccionar la Carpeta Base</h3>
            <ol>
              <li>En <b>1. Carpeta Base (init_file)</b>, busca esa carpeta en <i>Songs</i>
                  (o usa <b>Examinar...</b>).</li>
              <li>Si tiene varios archivos <code>.osu</code>, selecciona tu plantilla.</li>
            </ol>

            <h3 style="color:#2FA572;">Paso 3 — Añadir y organizar tus mapas</h3>
            <ol>
              <li>En <b>2. Buscar y Añadir Mapas</b>, busca canciones en <i>Songs</i>
                  (o arrastra la carpeta del mapa directamente al panel).</li>
              <li>Elige la dificultad <code>.osu</code>, selecciona el patrón
                  (<b>DJ</b>, <b>CJ</b>, <b>SJ</b>, <b>ANCHOR</b>) y pulsa
                  <b>+ Añadir Dificultad al Pack</b>.</li>
              <li>Usa las fichas de la derecha para editar (<b>✎</b>), quitar (<b>✕</b>)
                  o filtrar por patrón, y ajusta el <b>Cortador de Nombre</b> si lo deseas.</li>
            </ol>

            <h3 style="color:#2FA572;">Paso 4 — Generar el Pack</h3>
            <ol>
              <li>Pulsa <b>⚡ Generar Pack de Mapas Final</b>.</li>
              <li>Si algún nombre supera los 125 caracteres seguros para osu!,
                  se abrirá un cuadro para acortarlo.</li>
              <li>Al terminar, abre <b>osu!</b> (pulsa <b>F5</b> si hace falta) y borra
                  la dificultad plantilla <code>delete</code> dentro del juego.</li>
            </ol>
            """
        )
        layout.addWidget(browser, 1)

        btn_close = QPushButton("Entendido")
        btn_close.setObjectName("PrimaryBtn")
        btn_close.setMinimumHeight(34)
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close, alignment=Qt.AlignmentFlag.AlignRight)
