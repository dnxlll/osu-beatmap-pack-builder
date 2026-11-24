"""Modal dialogs for pattern selection and filename paraphrasing."""

import tkinter as tk
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk

from osu_pack_builder.domain.models import MAX_OSU_FILENAME_LEN
from osu_pack_builder.domain.naming import limpiar_bpm_od, normalize_pattern
from osu_pack_builder.ui.theme import (
    COLOR_ACCENT_BLUE,
    COLOR_BORDER,
    COLOR_COUNTER_ERROR,
    COLOR_DANGER,
    COLOR_DANGER_HOVER,
    COLOR_MUTED,
    COLOR_MUTED_HOVER,
    COLOR_PRIMARY,
    COLOR_PRIMARY_HOVER,
    COLOR_SUCCESS,
    COLOR_SUCCESS_HOVER,
    COLOR_SURFACE_DARK,
    COLOR_WARNING,
    PATTERN_META,
)


def centrar_ventana(
    ventana: ctk.CTkToplevel,
    parent: ctk.CTk,
    ancho: int,
    alto: int,
) -> None:
    """Center a modal dialog relative to its parent window."""
    ventana.update_idletasks()
    try:
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (ancho // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (alto // 2)
        ventana.geometry(f"+{max(0, x)}+{max(0, y)}")
    except tk.TclError:
        pass


class PatronModalDialog(ctk.CTkToplevel):
    """Modal dialog asking the user to select a pattern type (DJ, CJ, SJ, ANCHOR, or None)."""

    def __init__(self, parent: ctk.CTk, map_name: str, sugerido: str = "") -> None:
        super().__init__(parent)
        self.title("Tipo de Patrón")
        self.geometry("460x260")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        centrar_ventana(self, parent, 460, 260)

        self.resultado: str | None = None

        ctk.CTkLabel(
            self,
            text="🎯 Selecciona el Tipo de Patrón",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(pady=(16, 4), padx=20)

        ctk.CTkLabel(
            self,
            text=f"¿Qué tipo de patrón corresponde a este mapa?\n{limpiar_bpm_od(map_name)}",
            font=ctk.CTkFont(size=12),
            text_color=COLOR_ACCENT_BLUE,
            wraplength=420,
            justify="center",
        ).pack(pady=(0, 14), padx=20)

        frame_patrones = ctk.CTkFrame(self, fg_color="transparent")
        frame_patrones.pack(pady=4, padx=20, fill="x")

        for code, (desc, color) in PATTERN_META.items():
            ctk.CTkButton(
                frame_patrones,
                text=f"{code}\n({desc})",
                font=ctk.CTkFont(size=12, weight="bold"),
                fg_color=COLOR_SUCCESS if code == sugerido else color,
                height=52,
                command=lambda c=code: self._seleccionar(c),
            ).pack(side="left", fill="both", expand=True, padx=3)

        frame_inferior = ctk.CTkFrame(self, fg_color="transparent")
        frame_inferior.pack(pady=(16, 12), padx=20, fill="x")

        ctk.CTkButton(
            frame_inferior,
            text="Sin Patrón (Ninguno)",
            fg_color=COLOR_MUTED,
            hover_color=COLOR_MUTED_HOVER,
            height=30,
            command=lambda: self._seleccionar(""),
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            frame_inferior,
            text="Cancelar",
            fg_color=COLOR_DANGER,
            hover_color=COLOR_DANGER_HOVER,
            height=30,
            width=90,
            command=self._cancelar,
        ).pack(side="right", padx=5)

    def _seleccionar(self, valor: str) -> None:
        self.resultado = valor
        self.destroy()

    def _cancelar(self) -> None:
        self.resultado = None
        self.destroy()


class ParafraseoDialog(ctk.CTkToplevel):
    """Modal dialog shown when a generated .osu filename exceeds osu!'s safe length limit."""

    def __init__(
        self,
        parent: ctk.CTk,
        prefix_base: str,
        version_original: str,
        max_len: int = MAX_OSU_FILENAME_LEN,
    ) -> None:
        super().__init__(parent)
        self.title("⚠️ Nombre Demasiado Largo")
        self.geometry("580x400")
        self.minsize(500, 340)
        self.transient(parent)
        self.grab_set()
        centrar_ventana(self, parent, 580, 400)

        self.prefix_base = prefix_base
        self.max_len = max_len
        self.resultado: str | None = None

        ctk.CTkLabel(
            self,
            text="⚠️ Nombre de Archivo Demasiado Largo",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLOR_WARNING,
        ).pack(pady=(16, 4), padx=20)

        ctk.CTkLabel(
            self,
            text=(
                "El nombre ya fue recortado a la primera palabra y se limpiaron BPM y OD,\n"
                "pero sumado al prefijo del pack aún supera los 125 caracteres seguros para osu!.\n"
                "Por favor, parafrasea o acorta el nombre de esta dificultad."
            ),
            font=ctk.CTkFont(size=12),
            text_color="gray",
            justify="center",
        ).pack(pady=(0, 10), padx=20)

        frame_editor = ctk.CTkFrame(
            self, fg_color=COLOR_SURFACE_DARK, border_width=1, border_color=COLOR_BORDER
        )
        frame_editor.pack(fill="x", padx=20, pady=6)

        ctk.CTkLabel(
            frame_editor,
            text=f"Prefijo del pack ({len(self.prefix_base)} chars): {self.prefix_base}",
            font=ctk.CTkFont(size=11),
            text_color="gray",
            anchor="w",
        ).pack(fill="x", padx=12, pady=(8, 2))

        ctk.CTkLabel(
            frame_editor,
            text="Nombre de la dificultad / versión a acortar:",
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w",
        ).pack(fill="x", padx=12, pady=(6, 2))

        self.entry_version = ctk.CTkEntry(frame_editor, font=ctk.CTkFont(size=12), height=34)
        self.entry_version.insert(0, version_original)
        self.entry_version.pack(fill="x", padx=12, pady=(2, 6))
        self.entry_version.bind("<KeyRelease>", self._actualizar_contador)

        self.lbl_contador = ctk.CTkLabel(
            frame_editor, text="", font=ctk.CTkFont(size=12, weight="bold")
        )
        self.lbl_contador.pack(anchor="w", padx=12, pady=(2, 8))

        frame_acciones = ctk.CTkFrame(self, fg_color="transparent")
        frame_acciones.pack(fill="x", padx=20, pady=(12, 10))

        self.btn_guardar = ctk.CTkButton(
            frame_acciones,
            text="✓ Usar este Nombre",
            fg_color=COLOR_SUCCESS,
            hover_color=COLOR_SUCCESS_HOVER,
            height=36,
            command=self._confirmar,
        )
        self.btn_guardar.pack(side="left", fill="x", expand=True, padx=(0, 6))

        ctk.CTkButton(
            frame_acciones,
            text="Omitir (dejar largo)",
            fg_color=COLOR_MUTED,
            hover_color=COLOR_MUTED_HOVER,
            height=36,
            command=lambda: self._finalizar(version_original),
        ).pack(side="right", padx=(6, 0))

        self._actualizar_contador()

    def _actualizar_contador(self, event=None) -> None:
        val = self.entry_version.get().strip()
        total_len = len(f"{self.prefix_base} [{val}].osu")
        if total_len <= self.max_len:
            self.lbl_contador.configure(
                text=f"✓ Longitud total: {total_len} / {self.max_len} caracteres (Seguro para osu!)",
                text_color=COLOR_SUCCESS,
            )
            self.btn_guardar.configure(state="normal")
        else:
            exceso = total_len - self.max_len
            self.lbl_contador.configure(
                text=f"⚠️ Longitud total: {total_len} / {self.max_len} (+{exceso} exceso, ¡acorta!)",
                text_color=COLOR_COUNTER_ERROR,
            )
            self.btn_guardar.configure(state="disabled")

    def _confirmar(self) -> None:
        val = self.entry_version.get().strip()
        if not val:
            messagebox.showwarning("Atención", "El nombre no puede estar vacío.")
            return
        self._finalizar(val)

    def _finalizar(self, valor: str) -> None:
        self.resultado = valor
        self.destroy()


class EditMapDialog(ctk.CTkToplevel):
    """Modal dialog for editing an existing map's difficulty (.osu), pattern, and custom version."""

    def __init__(
        self,
        parent: ctk.CTk,
        indice: str,
        current_osu_name: str,
        available_osus: list[Path],
        current_pattern: str = "",
        current_custom_version: str = "",
        suggested_version: str = "",
    ) -> None:
        super().__init__(parent)
        self.title(f"Editar Mapa #{indice}")
        self.geometry("540x390")
        self.minsize(480, 360)
        self.transient(parent)
        self.grab_set()
        centrar_ventana(self, parent, 540, 390)

        self._available_osus = available_osus
        self._had_custom = bool(current_custom_version.strip())
        self._initial_suggested = suggested_version.strip()
        self.resultado: tuple[Path | None, str, str] | None = None

        ctk.CTkLabel(
            self,
            text=f"✎ Editar Mapa #{indice}",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(pady=(16, 8), padx=20, anchor="w")

        ctk.CTkLabel(
            self,
            text="Dificultad (.osu) — actualiza audio e imagen automáticamente:",
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w",
        ).pack(fill="x", padx=20, pady=(4, 2))

        if available_osus:
            osu_names = [p.name for p in available_osus]
            self.combo_osu = ctk.CTkOptionMenu(self, values=osu_names)
            self.combo_osu.set(
                current_osu_name if current_osu_name in osu_names else osu_names[0]
            )
            self.combo_osu.pack(fill="x", padx=20, pady=(0, 10))
        else:
            self.combo_osu = ctk.CTkOptionMenu(
                self,
                values=[f"{current_osu_name} (carpeta no disponible)"],
                state="disabled",
            )
            self.combo_osu.pack(fill="x", padx=20, pady=(0, 10))

        ctk.CTkLabel(
            self,
            text="Tipo de patrón:",
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w",
        ).pack(fill="x", padx=20, pady=(4, 2))

        self.seg_patron = ctk.CTkSegmentedButton(
            self, values=["DJ", "CJ", "SJ", "ANCHOR", "Ninguno"], height=32
        )
        norm = normalize_pattern(current_pattern)
        self.seg_patron.set(norm if norm else "Ninguno")
        self.seg_patron.pack(fill="x", padx=20, pady=(0, 10))

        ctk.CTkLabel(
            self,
            text="Versión parafraseada (opcional):",
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w",
        ).pack(fill="x", padx=20, pady=(4, 2))

        self.entry_custom = ctk.CTkEntry(
            self,
            placeholder_text="Vacío = automático, o escribe un nombre corto...",
            height=34,
        )
        prefill = current_custom_version.strip() or self._initial_suggested
        if prefill:
            self.entry_custom.insert(0, prefill)
        self.entry_custom.pack(fill="x", padx=20, pady=(0, 14))

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(fill="x", padx=20, pady=(4, 12))

        ctk.CTkButton(
            actions,
            text="✓ Guardar Cambios",
            fg_color=COLOR_SUCCESS,
            hover_color=COLOR_SUCCESS_HOVER,
            height=36,
            command=self._guardar,
        ).pack(side="left", fill="x", expand=True, padx=(0, 6))

        ctk.CTkButton(
            actions,
            text="Cancelar",
            fg_color=COLOR_MUTED,
            hover_color=COLOR_MUTED_HOVER,
            height=36,
            width=110,
            command=self._cancelar,
        ).pack(side="right")

    def _guardar(self) -> None:
        selected_osu: Path | None = None
        if self._available_osus:
            chosen_name = self.combo_osu.get()
            selected_osu = next(
                (p for p in self._available_osus if p.name == chosen_name),
                None,
            )
        patron = normalize_pattern(self.seg_patron.get())
        entered = self.entry_custom.get().strip()
        custom_version = "" if not self._had_custom and entered == self._initial_suggested else entered
        self.resultado = (selected_osu, patron, custom_version)
        self.destroy()

    def _cancelar(self) -> None:
        self.resultado = None
        self.destroy()


class TitleCutterScopeDialog(ctk.CTkToplevel):
    """Modal dialog asking whether the title cutter applies to all maps or only auto-named ones."""

    def __init__(self, parent: ctk.CTk, selection_label: str, manual_count: int) -> None:
        super().__init__(parent)
        self.title("Aplicar Cortador de Título")
        self.geometry("460x220")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        centrar_ventana(self, parent, 460, 220)

        self.resultado: str | None = None

        ctk.CTkLabel(
            self,
            text=f"Aplicar cortador: '{selection_label}'",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(pady=(16, 6), padx=20)

        ctk.CTkLabel(
            self,
            text=(
                f"Hay {manual_count} mapa(s) con versión parafraseada manual.\n"
                "¿Cómo deseas aplicar este recorte?"
            ),
            font=ctk.CTkFont(size=12),
            text_color="gray",
            justify="center",
        ).pack(pady=(0, 14), padx=20)

        ctk.CTkButton(
            self,
            text="Parafrasear TODOS los mapas según el cortador",
            fg_color=COLOR_PRIMARY,
            hover_color=COLOR_PRIMARY_HOVER,
            height=34,
            command=lambda: self._select("all"),
        ).pack(fill="x", padx=24, pady=(0, 6))

        ctk.CTkButton(
            self,
            text="Solo recortar los que NO tienen versión manual",
            fg_color=COLOR_SUCCESS,
            hover_color=COLOR_SUCCESS_HOVER,
            height=34,
            command=lambda: self._select("auto_only"),
        ).pack(fill="x", padx=24, pady=(0, 8))

        ctk.CTkButton(
            self,
            text="Cancelar",
            fg_color=COLOR_MUTED,
            hover_color=COLOR_MUTED_HOVER,
            height=28,
            width=90,
            command=self.destroy,
        ).pack(pady=(0, 10))

    def _select(self, mode: str) -> None:
        self.resultado = mode
        self.destroy()
