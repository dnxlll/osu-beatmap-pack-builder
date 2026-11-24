"""Top header bar displaying the active osu! Songs directory."""

from collections.abc import Callable
from pathlib import Path

import customtkinter as ctk

from osu_pack_builder.ui.theme import COLOR_ACCENT_BLUE


class SongsHeader(ctk.CTkFrame):
    """Header bar with title, active Songs directory indicator, and folder picker button."""

    def __init__(
        self,
        parent: ctk.CTkBaseClass,
        songs_dir: Path,
        map_count: int,
        on_change_songs: Callable[[], None],
    ) -> None:
        super().__init__(parent, fg_color="transparent")

        top_row = ctk.CTkFrame(self, fg_color="transparent")
        top_row.pack(fill="x", pady=(6, 2))

        ctk.CTkLabel(
            top_row,
            text="osu! BeatmapPack Builder",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).pack(side="left")

        ctk.CTkButton(
            top_row,
            text="Cambiar Songs...",
            width=120,
            height=28,
            command=on_change_songs,
        ).pack(side="right")

        self.lbl_songs_dir = ctk.CTkLabel(
            self,
            text="",
            text_color=COLOR_ACCENT_BLUE,
            font=ctk.CTkFont(size=12),
            anchor="w",
        )
        self.lbl_songs_dir.pack(fill="x")
        self.update_songs_info(songs_dir, map_count)

    def update_songs_info(self, songs_dir: Path, map_count: int) -> None:
        """Refresh displayed Songs directory path and folder count."""
        self.lbl_songs_dir.configure(text=f"📁 Songs: {songs_dir} ({map_count} carpetas)")
