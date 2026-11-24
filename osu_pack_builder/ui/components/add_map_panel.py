"""Step 2 panel: search beatmaps, select difficulty/pattern, and add to pack."""

from collections.abc import Callable
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from osu_pack_builder.domain.naming import detectar_patron_sugerido
from osu_pack_builder.infrastructure.songs_scanner import filter_song_folders
from osu_pack_builder.ui.theme import (
    COLOR_ACCENT_BLUE,
    COLOR_BORDER,
    COLOR_RESULT_HOVER_ALT,
    COLOR_SUCCESS,
    COLOR_SUCCESS_HOVER,
    COLOR_SURFACE_DARK,
    COLOR_TEXT_LIGHT,
)


class AddMapPanel(ctk.CTkFrame):
    """Panel for searching songs, selecting a .osu difficulty, pattern, and adding to pack."""

    def __init__(
        self,
        parent: ctk.CTkBaseClass,
        get_folders: Callable[[], list[Path]],
        on_add_map: Callable[[Path, Path, str, str], bool],
    ) -> None:
        super().__init__(parent)
        self._get_folders = get_folders
        self._on_add_map = on_add_map

        self.carpeta_actual: Path | None = None
        self.archivos_osu: list[Path] = []

        ctk.CTkLabel(
            self,
            text="2. Buscar y Añadir Mapas",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(anchor="w", padx=14, pady=(10, 4))

        search_row = ctk.CTkFrame(self, fg_color="transparent")
        search_row.pack(fill="x", padx=14, pady=4)

        self.entry_buscar = ctk.CTkEntry(
            search_row,
            placeholder_text="🔍 Buscar canción (ej. goreshit, Zhanulka, 2272322)...",
        )
        self.entry_buscar.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.entry_buscar.bind("<KeyRelease>", self._on_buscar)
        self.entry_buscar.bind("<Return>", self._on_enter)

        ctk.CTkButton(
            search_row,
            text="Examinar...",
            width=92,
            command=self._seleccionar_manual,
        ).pack(side="right")

        self.frame_resultados = ctk.CTkFrame(
            self, fg_color=COLOR_SURFACE_DARK, border_width=1, border_color=COLOR_BORDER
        )

        self.lbl_folder = ctk.CTkLabel(
            self,
            text="Busca una canción arriba o examina manualmente",
            text_color="gray",
            anchor="w",
        )
        self.lbl_folder.pack(fill="x", padx=14, pady=(2, 2))

        ctk.CTkLabel(self, text="Dificultad (.osu):").pack(anchor="w", padx=14, pady=(4, 0))

        self.combo_osus = ctk.CTkOptionMenu(
            self,
            values=["(Primero busca y selecciona un mapa)"],
            command=self._on_cambio_osu,
        )
        self.combo_osus.pack(fill="x", padx=14, pady=4)

        ctk.CTkLabel(
            self,
            text="Tipo de patrón:",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(anchor="w", padx=14, pady=(6, 2))

        self.seg_patron = ctk.CTkSegmentedButton(
            self, values=["DJ", "CJ", "SJ", "ANCHOR", "Ninguno"], height=32
        )
        self.seg_patron.set("Ninguno")
        self.seg_patron.pack(fill="x", padx=14, pady=(2, 6))

        ctk.CTkLabel(
            self,
            text="Versión parafraseada (opcional):",
            font=ctk.CTkFont(size=11),
        ).pack(anchor="w", padx=14, pady=(4, 0))

        self.entry_custom_version = ctk.CTkEntry(
            self,
            placeholder_text="Vacío = automático, o escribe un nombre corto...",
        )
        self.entry_custom_version.pack(fill="x", padx=14, pady=(2, 8))

        self.btn_add = ctk.CTkButton(
            self,
            text="+ Añadir Dificultad al Pack",
            fg_color=COLOR_SUCCESS,
            hover_color=COLOR_SUCCESS_HOVER,
            height=36,
            command=self._handle_add,
            state="disabled",
        )
        self.btn_add.pack(fill="x", padx=14, pady=(2, 12))

    def _on_buscar(self, event=None) -> None:
        query = self.entry_buscar.get().strip().lower()
        for w in self.frame_resultados.winfo_children():
            w.destroy()

        if not query:
            self.frame_resultados.pack_forget()
            return

        coincidencias = filter_song_folders(self._get_folders(), query, limit=6)
        self.frame_resultados.pack(fill="x", padx=14, pady=(0, 4))

        if not coincidencias:
            ctk.CTkLabel(
                self.frame_resultados,
                text="No se encontraron mapas en Songs",
                text_color="gray",
            ).pack(padx=8, pady=3)
            return

        for carpeta in coincidencias:
            ctk.CTkButton(
                self.frame_resultados,
                text=f"📁 {carpeta.name}",
                anchor="w",
                fg_color="transparent",
                hover_color=COLOR_RESULT_HOVER_ALT,
                text_color=COLOR_TEXT_LIGHT,
                height=26,
                command=lambda c=carpeta: self._elegir_desde_busqueda(c),
            ).pack(fill="x", padx=2, pady=1)

    def _on_enter(self, event=None) -> None:
        query = self.entry_buscar.get().strip().lower()
        coincidencias = filter_song_folders(self._get_folders(), query, limit=1)
        if coincidencias:
            self._elegir_desde_busqueda(coincidencias[0])

    def _elegir_desde_busqueda(self, carpeta: Path) -> None:
        self.entry_buscar.delete(0, "end")
        self.frame_resultados.pack_forget()
        self._cargar_carpeta(carpeta)

    def _seleccionar_manual(self) -> None:
        ruta = filedialog.askdirectory(title="Selecciona la Carpeta del Mapa")
        if ruta:
            self._cargar_carpeta(Path(ruta))

    def _cargar_carpeta(self, carpeta: Path) -> None:
        archivos_osu = [f for f in carpeta.iterdir() if f.is_file() and f.suffix == ".osu"]
        if not archivos_osu:
            messagebox.showwarning(
                "Atención", f"La carpeta '{carpeta.name}' no contiene archivos .osu."
            )
            return

        self.carpeta_actual = carpeta
        self.archivos_osu = archivos_osu
        self.lbl_folder.configure(text=f"✓ {carpeta.name}", text_color=COLOR_ACCENT_BLUE)

        nombres = [f.name for f in archivos_osu]
        self.combo_osus.configure(values=nombres)
        self.combo_osus.set(nombres[0])
        self._on_cambio_osu(nombres[0])
        self.btn_add.configure(state="normal")

    def _on_cambio_osu(self, valor_osu: str) -> None:
        sugerido = detectar_patron_sugerido(valor_osu)
        self.seg_patron.set(sugerido if sugerido else "Ninguno")

    def _handle_add(self) -> None:
        if not self.carpeta_actual or not self.archivos_osu:
            return

        nombre_elegido = self.combo_osus.get()
        osu_elegido = next((f for f in self.archivos_osu if f.name == nombre_elegido), None)
        if not osu_elegido:
            messagebox.showerror("Error", "No se encontró el archivo .osu seleccionado.")
            return

        patron = self.seg_patron.get()
        custom_version = self.entry_custom_version.get().strip()

        added = self._on_add_map(self.carpeta_actual, osu_elegido, patron, custom_version)
        if added:
            self.reset_selection()

    def reset_selection(self) -> None:
        """Reset panel inputs after successfully adding a map."""
        self.combo_osus.configure(values=["(Busca otra canción arriba para continuar)"])
        self.combo_osus.set("(Busca otra canción arriba para continuar)")
        self.seg_patron.set("Ninguno")
        self.entry_custom_version.delete(0, "end")
        self.btn_add.configure(state="disabled")
        self.lbl_folder.configure(
            text="Escribe arriba para buscar y agregar el siguiente mapa...",
            text_color="gray",
        )
        self.carpeta_actual = None
        self.archivos_osu = []
