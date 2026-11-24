"""Step 1 panel: base pack folder and init_file selection."""

from collections.abc import Callable
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from osu_pack_builder.infrastructure.songs_scanner import filter_song_folders
from osu_pack_builder.ui.theme import (
    COLOR_BORDER,
    COLOR_ERROR_TEXT,
    COLOR_RESULT_HOVER,
    COLOR_SUCCESS,
    COLOR_SURFACE_DARK,
    COLOR_TEXT_LIGHT,
)


class BaseMapPanel(ctk.CTkFrame):
    """Panel for searching or browsing the base beatmap folder (init_file)."""

    def __init__(
        self,
        parent: ctk.CTkBaseClass,
        get_folders: Callable[[], list[Path]],
    ) -> None:
        super().__init__(parent)
        self._get_folders = get_folders
        self.init_file: Path | None = None
        self.archivos_base_disponibles: list[Path] = []

        ctk.CTkLabel(
            self,
            text="1. Carpeta Base (init_file)",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(anchor="w", padx=14, pady=(10, 4))

        search_row = ctk.CTkFrame(self, fg_color="transparent")
        search_row.pack(fill="x", padx=14, pady=4)

        self.entry_buscar = ctk.CTkEntry(
            search_row,
            placeholder_text="🔍 Buscar carpeta base en Songs (ej. ScriptTest)...",
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

        self.combo_init = ctk.CTkOptionMenu(
            self,
            values=["(Selecciona una carpeta base primero)"],
            command=self._cambiar_init_file,
        )

        self.lbl_status = ctk.CTkLabel(
            self,
            text="⚠️ Ninguna carpeta base seleccionada",
            text_color="gray",
            anchor="w",
        )
        self.lbl_status.pack(fill="x", padx=14, pady=(4, 10))

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
                self.frame_resultados, text="Sin coincidencias", text_color="gray"
            ).pack(padx=8, pady=3)
            return

        for carpeta in coincidencias:
            ctk.CTkButton(
                self.frame_resultados,
                text=f"📁 {carpeta.name}",
                anchor="w",
                fg_color="transparent",
                hover_color=COLOR_RESULT_HOVER,
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
        ruta = filedialog.askdirectory(title="Selecciona la Carpeta Base (con init_file)")
        if ruta:
            self._cargar_carpeta(Path(ruta))

    def _cargar_carpeta(self, carpeta: Path) -> None:
        archivos_osu = list(carpeta.glob("*.osu"))
        if not archivos_osu:
            messagebox.showerror(
                "Error",
                f"No se encontró ningún archivo .osu en:\n{carpeta.name}\n"
                "Asegúrate de que contenga el archivo base .osu.",
            )
            self.init_file = None
            self.lbl_status.configure(
                text="Error: no se encontró archivo .osu", text_color=COLOR_ERROR_TEXT
            )
            return

        self.archivos_base_disponibles = archivos_osu
        nombres = [f.name for f in archivos_osu]
        archivos_delete = [f for f in archivos_osu if "delete" in f.name.lower()]
        predeterminado = archivos_delete[0] if archivos_delete else archivos_osu[0]
        self.init_file = predeterminado

        if len(archivos_osu) > 1:
            self.combo_init.configure(values=nombres)
            self.combo_init.set(predeterminado.name)
            self.combo_init.pack(fill="x", padx=14, pady=(2, 6))
            self.lbl_status.configure(
                text=f"✓ Base seleccionada: {predeterminado.name}",
                text_color=COLOR_SUCCESS,
            )
        else:
            self.combo_init.pack_forget()
            self.lbl_status.configure(
                text=f"✓ Archivo base: {self.init_file.name}",
                text_color=COLOR_SUCCESS,
            )

    def _cambiar_init_file(self, nombre_elegido: str) -> None:
        for f in self.archivos_base_disponibles:
            if f.name == nombre_elegido:
                self.init_file = f
                self.lbl_status.configure(
                    text=f"✓ Base seleccionada: {self.init_file.name}",
                    text_color=COLOR_SUCCESS,
                )
                break
