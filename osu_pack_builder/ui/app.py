"""Main CustomTkinter application window with 2-column split-view layout."""

import logging
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

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
from osu_pack_builder.ui.theme import COLOR_PRIMARY, COLOR_PRIMARY_HOVER

logger = logging.getLogger(__name__)

_TITLE_WORD_OPTIONS: dict[str, int | None] = {
    "1 palabra": 1,
    "2 palabras": 2,
    "3 palabras": 3,
    "Completo": None,
}


class BeatmapPackApp(ctk.CTk):
    """Main GUI orchestrating the 2-column split-view beatmap pack workflow."""

    def __init__(self, repository: PackRepository, default_creator: str = "") -> None:
        super().__init__()

        self.repository = repository
        self.default_creator = default_creator

        self.title("osu! BeatmapPack Builder")
        self.geometry("980x700")
        self.minsize(860, 600)
        self.resizable(True, True)

        self.songs_dir: Path = detect_songs_dir()
        self._current_title_words_label: str = "1 palabra"
        self.carpetas_songs: list[Path] = []
        self._cargar_indice_songs()

        self._build_layout()
        self._refresh_pack_list()

    def _cargar_indice_songs(self) -> None:
        try:
            self.carpetas_songs = list_song_folders(self.songs_dir)
        except OSError as exc:
            logger.error("No se pudo leer el directorio Songs: %s", exc)
            messagebox.showwarning(
                "Error al leer Songs",
                f"No se pudo leer el directorio Songs:\n{exc}\n\n"
                "Usa 'Cambiar Songs...' para seleccionar otro.",
            )
            self.carpetas_songs = []

    def _build_layout(self) -> None:
        self.header = SongsHeader(
            self,
            songs_dir=self.songs_dir,
            map_count=len(self.carpetas_songs),
            on_change_songs=self._cambiar_directorio_songs,
        )
        self.header.pack(fill="x", padx=16, pady=(6, 8))

        workspace = ctk.CTkFrame(self, fg_color="transparent")
        workspace.pack(fill="both", expand=True, padx=16, pady=(0, 12))
        workspace.grid_columnconfigure(0, weight=0, minsize=430)
        workspace.grid_columnconfigure(1, weight=1)
        workspace.grid_rowconfigure(0, weight=1)

        # Left column: fixed comfortable width; Right column expands in fullscreen
        left_col = ctk.CTkScrollableFrame(workspace, fg_color="transparent", width=430)
        left_col.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        self.base_panel = BaseMapPanel(left_col, get_folders=lambda: self.carpetas_songs)
        self.base_panel.pack(fill="x", pady=(0, 10))

        self.add_panel = AddMapPanel(
            left_col,
            get_folders=lambda: self.carpetas_songs,
            on_add_map=self._handle_add_map,
        )
        self.add_panel.pack(fill="x", pady=(0, 10))

        cutter_frame = ctk.CTkFrame(left_col)
        cutter_frame.pack(fill="x")

        ctk.CTkLabel(
            cutter_frame,
            text="3. Cortador de Nombre de Dificultad",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(anchor="w", padx=14, pady=(10, 4))

        self.seg_title_words = ctk.CTkSegmentedButton(
            cutter_frame,
            values=list(_TITLE_WORD_OPTIONS.keys()),
            height=30,
            command=self._on_title_words_change,
        )
        self.seg_title_words.set("1 palabra")
        self.seg_title_words.pack(fill="x", padx=14, pady=(0, 12))

        # Right column: Pack list + Generate button
        right_col = ctk.CTkFrame(workspace, fg_color="transparent")
        right_col.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        self.pack_panel = PackListPanel(
            right_col,
            on_remove_map=self._handle_remove_map,
            on_edit_map=self._handle_edit_map,
            on_clear_pack=self._handle_clear_pack,
            get_songs_dir=lambda: self.songs_dir,
        )
        self.pack_panel.pack(fill="both", expand=True, pady=(0, 10))

        ctk.CTkButton(
            right_col,
            text="⚡ Generar Pack de Mapas Final",
            font=ctk.CTkFont(size=15, weight="bold"),
            height=46,
            fg_color=COLOR_PRIMARY,
            hover_color=COLOR_PRIMARY_HOVER,
            command=self._generar_pack_final,
        ).pack(fill="x")

    def _on_title_words_change(self, selection: str) -> None:
        pack = self.repository.load()
        manual_count = sum(
            1 for m in pack.values() if isinstance(m, dict) and m.get("__custom_version__")
        )
        if manual_count > 0:
            dialogo = TitleCutterScopeDialog(self, selection_label=selection, manual_count=manual_count)
            self.wait_window(dialogo)
            if dialogo.resultado is None:
                self.seg_title_words.set(self._current_title_words_label)
                return
            if dialogo.resultado == "all":
                pack = clear_custom_versions(self.repository)

        self._current_title_words_label = selection
        self.pack_panel.set_title_words(_TITLE_WORD_OPTIONS.get(selection, 1))
        if pack:
            self.pack_panel.render_pack(pack)

    def _cambiar_directorio_songs(self) -> None:
        nueva_ruta = filedialog.askdirectory(title="Selecciona tu carpeta Songs de osu!")
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
            self.wait_window(dialogo)
            if dialogo.resultado is None:
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
            messagebox.showinfo(
                "Éxito", f"Dificultad{tag_msg} agregada al pack con índice '{indice}'."
            )
            self.pack_panel.render_pack(pack)
            return True
        except Exception as exc:
            logger.exception("Error al agregar mapa al pack")
            messagebox.showerror(
                "Error al guardar", f"Ocurrió un error al procesar el mapa:\n{exc}"
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
            candidate_osu = Path(mapa[osu_key])
            candidate_dir = candidate_osu.parent
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
        self.wait_window(dialogo)
        if dialogo.resultado is None:
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
            messagebox.showerror("Error al editar", f"No se pudo actualizar el mapa:\n{exc}")

    def _handle_remove_map(self, indice: str) -> None:
        try:
            pack = remove_map_from_pack(indice, self.repository)
            self.pack_panel.render_pack(pack)
        except OSError as exc:
            logger.exception("Error al eliminar mapa #%s", indice)
            messagebox.showerror("Error", f"No se pudo eliminar el mapa:\n{exc}")

    def _handle_clear_pack(self) -> None:
        if not messagebox.askyesno("Confirmar", "¿Seguro que deseas vaciar pack.json?"):
            return
        try:
            self.repository.clear()
            self._refresh_pack_list()
            messagebox.showinfo("Listo", "pack.json ha sido reseteado.")
        except OSError as exc:
            messagebox.showerror("Error", f"No se pudo vaciar pack.json:\n{exc}")

    def _refresh_pack_list(self) -> None:
        self.pack_panel.render_pack(self.repository.load())

    def _solicitar_parafraseo(
        self,
        indice: str,
        clave_osu: str,
        version_original: str,
        prefix_base: str,
    ) -> str:
        dialogo = ParafraseoDialog(
            self,
            prefix_base=prefix_base,
            version_original=version_original,
            max_len=MAX_OSU_FILENAME_LEN,
        )
        self.wait_window(dialogo)
        return dialogo.resultado if dialogo.resultado is not None else version_original

    def _generar_pack_final(self) -> None:
        init_file = self.base_panel.init_file
        if not init_file or not init_file.exists():
            messagebox.showerror(
                "Falta Archivo Base",
                "Debes completar el Paso 1 y seleccionar una carpeta base válida que contenga init_file.",
            )
            return

        if not self.repository.load():
            messagebox.showerror(
                "Pack Vacío",
                "Debes agregar al menos un mapa antes de generar el pack.",
            )
            return

        try:
            carpeta_generada, cantidad = generate_pack(
                init_file,
                repository=self.repository,
                callback_parafraseo=self._solicitar_parafraseo,
                default_creator=self.default_creator,
                title_words=_TITLE_WORD_OPTIONS.get(self.seg_title_words.get(), 1),
            )
            messagebox.showinfo(
                "¡Pack Generado con Éxito!",
                f"Se generaron {cantidad} archivo(s) .osu correctamente en tu carpeta de canciones:\n"
                f"{carpeta_generada.resolve()}",
            )
            self._refresh_pack_list()
        except Exception as exc:
            logger.exception("Error inesperado al generar el pack")
            messagebox.showerror(
                "Error al generar", f"Ocurrió un error inesperado al generar el pack:\n{exc}"
            )
