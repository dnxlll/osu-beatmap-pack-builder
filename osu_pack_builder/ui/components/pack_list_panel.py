"""Right-column panel displaying registered pack maps as a responsive card grid."""

from collections import Counter
from collections.abc import Callable
from pathlib import Path

import customtkinter as ctk

from osu_pack_builder.domain.models import AUDIO_EXTENSIONS, IMAGE_EXTENSIONS
from osu_pack_builder.domain.naming import (
    build_version_name,
    limpiar_bpm_od,
    normalize_pattern,
    parse_osu_filename,
)
from osu_pack_builder.domain.osu_file import extract_background_filename
from osu_pack_builder.infrastructure.media_processor import load_thumbnail
from osu_pack_builder.ui.theme import (
    COLOR_DANGER,
    COLOR_DANGER_HOVER,
    COLOR_MUTED,
    COLOR_MUTED_HOVER,
    COLOR_PRIMARY,
    COLOR_PRIMARY_HOVER,
    COLOR_SURFACE_CARD,
    COLOR_SURFACE_DARK,
    COLOR_TEXT_SUBTLE,
    PATTERN_META,
)

_THUMB_SIZE = (96, 60)


class PackListPanel(ctk.CTkFrame):
    """Interactive responsive grid of maps currently registered in pack.json."""

    def __init__(
        self,
        parent: ctk.CTkBaseClass,
        on_remove_map: Callable[[str], None],
        on_clear_pack: Callable[[], None],
        on_edit_map: Callable[[str], None] | None = None,
        get_songs_dir: Callable[[], Path] | None = None,
    ) -> None:
        super().__init__(parent)
        self._on_remove_map = on_remove_map
        self._on_edit_map = on_edit_map
        self._get_songs_dir = get_songs_dir
        self._thumb_cache: dict[str, ctk.CTkImage | None] = {}

        self._last_pack: dict[str, dict] = {}
        self._active_filter: str = ""
        self._title_words: int | None = 1
        self._cards: list[ctk.CTkFrame] = []
        self._wrap_labels: list[ctk.CTkLabel] = []
        self._current_cols: int = 1
        self._current_wrap: int = 235
        self._resize_after_id: str | None = None

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=14, pady=(10, 4))

        self.lbl_title = ctk.CTkLabel(
            header,
            text="Pack Actual (0 mapas)",
            font=ctk.CTkFont(size=15, weight="bold"),
        )
        self.lbl_title.pack(side="left")

        self.btn_clear = ctk.CTkButton(
            header,
            text="Vaciar",
            width=70,
            height=26,
            fg_color=COLOR_DANGER,
            hover_color=COLOR_DANGER_HOVER,
            command=on_clear_pack,
        )
        self.btn_clear.pack(side="right")

        self.filter_bar = ctk.CTkFrame(self, fg_color="transparent")
        self.filter_bar.pack(fill="x", padx=14, pady=(0, 4))

        self.scroll_list = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_list.pack(fill="both", expand=True, padx=8, pady=(2, 8))
        self.scroll_list.bind("<Configure>", self._on_scroll_configure)

    @staticmethod
    def _compute_columns(width: int) -> int:
        if width >= 1080:
            return 3
        if width >= 700:
            return 2
        return 1

    def _compute_wraplength(self, width: int, cols: int) -> int:
        col_width = max(280, (width - 24 * cols) // cols)
        return max(190, col_width - 140)

    def _on_scroll_configure(self, event) -> None:
        if self._resize_after_id is not None:
            self.after_cancel(self._resize_after_id)
        self._resize_after_id = self.after(100, self._apply_responsive_layout)

    def _apply_responsive_layout(self) -> None:
        self._resize_after_id = None
        if not self._cards:
            return
        width = max(320, self.scroll_list.winfo_width())
        new_cols = self._compute_columns(width)
        new_wrap = self._compute_wraplength(width, new_cols)

        if new_cols != self._current_cols:
            self._current_cols = new_cols
            self._relayout_cards()

        if abs(new_wrap - self._current_wrap) >= 12:
            self._current_wrap = new_wrap
            for lbl in self._wrap_labels:
                lbl.configure(wraplength=new_wrap)

    def _relayout_cards(self) -> None:
        for col in range(3):
            self.scroll_list.grid_columnconfigure(
                col,
                weight=1 if col < self._current_cols else 0,
                uniform="pack_cards" if col < self._current_cols else "",
            )

        for idx, card in enumerate(self._cards):
            row = idx // self._current_cols
            col = idx % self._current_cols
            card.grid(row=row, column=col, sticky="nsew", padx=4, pady=4)


    def set_title_words(self, title_words: int | None) -> None:
        """Update the title word-count setting and refresh difficulty previews."""
        self._title_words = title_words
        if self._last_pack:
            self.render_pack(self._last_pack)
    def _toggle_filter(self, pattern: str) -> None:
        self._active_filter = "" if self._active_filter == pattern else pattern
        self.render_pack(self._last_pack)

    def _render_filter_bar(self, valid_entries: list[tuple[str, dict]]) -> None:
        for child in self.filter_bar.winfo_children():
            child.destroy()

        if not valid_entries:
            return

        counts = Counter(
            normalize_pattern(m.get("__pattern__") or m.get("patron"))
            for _, m in valid_entries
        )

        is_all = self._active_filter == ""
        ctk.CTkButton(
            self.filter_bar,
            text=f"Todos ({len(valid_entries)})",
            height=22,
            width=70,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=COLOR_PRIMARY if is_all else COLOR_MUTED,
            hover_color=COLOR_MUTED_HOVER,
            command=lambda: self._toggle_filter(""),
        ).pack(side="left", padx=(0, 4))

        for pattern, (_, color) in PATTERN_META.items():
            cnt = counts.get(pattern, 0)
            if cnt == 0:
                continue
            active = self._active_filter == pattern
            ctk.CTkButton(
                self.filter_bar,
                text=f"{pattern}: {cnt}",
                height=22,
                width=62,
                font=ctk.CTkFont(size=11, weight="bold"),
                fg_color=color if active or is_all else COLOR_MUTED,
                border_width=2 if active else 0,
                border_color="#FFFFFF",
                command=lambda p=pattern: self._toggle_filter(p),
            ).pack(side="left", padx=(0, 4))

    def render_pack(self, pack: dict[str, dict]) -> None:
        """Rebuild the card grid from the current pack dictionary."""
        self._last_pack = pack
        for child in self.scroll_list.winfo_children():
            child.destroy()
        self._cards.clear()
        self._wrap_labels.clear()

        valid_entries = [(idx, m) for idx, m in pack.items() if isinstance(m, dict)]
        count = len(valid_entries)
        label_word = "mapa" if count == 1 else "mapas"
        self.lbl_title.configure(text=f"Pack Actual ({count} {label_word})")
        self.btn_clear.configure(state="normal" if count > 0 else "disabled")

        if self._active_filter and not any(
            normalize_pattern(m.get("__pattern__") or m.get("patron")) == self._active_filter
            for _, m in valid_entries
        ):
            self._active_filter = ""

        self._render_filter_bar(valid_entries)

        if count == 0:
            self.scroll_list.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(
                self.scroll_list,
                text="El pack está vacío.\nAñade mapas desde el panel izquierdo.",
                text_color="gray",
                justify="center",
            ).grid(row=0, column=0, pady=40)
            return

        filtered = [
            (idx, m)
            for idx, m in valid_entries
            if not self._active_filter
            or normalize_pattern(m.get("__pattern__") or m.get("patron")) == self._active_filter
        ]

        width = max(320, self.scroll_list.winfo_width())
        self._current_cols = self._compute_columns(width)
        self._current_wrap = self._compute_wraplength(width, self._current_cols)

        for indice, mapa in filtered:
            self._create_map_card(indice, mapa)

        self._relayout_cards()

    def _resolve_image_path(self, mapa: dict) -> Path | None:
        """Pick the beatmap background path, checking [Events] and active Songs fallback."""
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

    def _get_thumbnail(self, image_path: Path | None) -> ctk.CTkImage | None:
        """Return a cached CTkImage thumbnail for the given path, or None."""
        if not image_path:
            return None
        cache_key = str(image_path)
        if cache_key not in self._thumb_cache:
            pil_img = load_thumbnail(image_path, size=_THUMB_SIZE)
            self._thumb_cache[cache_key] = (
                ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=_THUMB_SIZE)
                if pil_img is not None
                else None
            )
        return self._thumb_cache[cache_key]

    def _create_map_card(self, indice: str, mapa: dict) -> None:
        card = ctk.CTkFrame(self.scroll_list, fg_color=COLOR_SURFACE_CARD, corner_radius=8)
        self._cards.append(card)

        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=8, pady=8)

        img_path = self._resolve_image_path(mapa)
        thumb_img = self._get_thumbnail(img_path)
        if thumb_img is not None:
            thumb_widget = ctk.CTkLabel(
                body,
                text="",
                image=thumb_img,
                width=_THUMB_SIZE[0],
                height=_THUMB_SIZE[1],
                corner_radius=6,
            )
        else:
            thumb_widget = ctk.CTkLabel(
                body,
                text="No hallada" if img_path is not None else "Sin BG",
                width=_THUMB_SIZE[0],
                height=_THUMB_SIZE[1],
                fg_color=COLOR_SURFACE_DARK,
                text_color=COLOR_TEXT_SUBTLE,
                font=ctk.CTkFont(size=10),
                corner_radius=6,
            )
        thumb_widget.pack(side="left", anchor="n", padx=(0, 10))

        info = ctk.CTkFrame(body, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True)

        top_row = ctk.CTkFrame(info, fg_color="transparent")
        top_row.pack(fill="x", pady=(0, 2))

        ctk.CTkLabel(
            top_row,
            text=f"#{indice}",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLOR_TEXT_SUBTLE,
        ).pack(side="left", padx=(0, 6))

        patron = normalize_pattern(mapa.get("__pattern__") or mapa.get("patron"))
        if patron:
            badge_color = PATTERN_META.get(patron, ("", COLOR_MUTED))[1]
            ctk.CTkLabel(
                top_row,
                text=patron,
                font=ctk.CTkFont(size=10, weight="bold"),
                fg_color=badge_color,
                corner_radius=4,
                padx=6,
                pady=1,
            ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            top_row,
            text="✕",
            width=26,
            height=22,
            fg_color="transparent",
            hover_color=COLOR_DANGER,
            text_color=COLOR_TEXT_SUBTLE,
            command=lambda i=indice: self._on_remove_map(i),
        ).pack(side="right")

        if self._on_edit_map is not None:
            ctk.CTkButton(
                top_row,
                text="✎",
                width=26,
                height=22,
                fg_color="transparent",
                hover_color=COLOR_PRIMARY_HOVER,
                text_color=COLOR_TEXT_SUBTLE,
                command=lambda i=indice: self._on_edit_map(i),
            ).pack(side="right", padx=(0, 2))

        osu_name = next((k for k in mapa if k.endswith(".osu")), "Desconocido")
        clean_name = limpiar_bpm_od(osu_name)
        lbl_title = ctk.CTkLabel(
            info,
            text=clean_name,
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w",
            wraplength=self._current_wrap,
            justify="left",
        )
        lbl_title.pack(fill="x", pady=(0, 2))
        self._wrap_labels.append(lbl_title)

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

        lbl_preview = ctk.CTkLabel(
            info,
            text=preview_text,
            font=ctk.CTkFont(size=11),
            text_color=preview_color,
            anchor="w",
            wraplength=self._current_wrap,
            justify="left",
        )
        lbl_preview.pack(fill="x")
        self._wrap_labels.append(lbl_preview)

        audio_name = next(
            (k for k in mapa if k.lower().endswith(AUDIO_EXTENSIONS)),
            "Sin audio",
        )
        ctk.CTkLabel(
            info,
            text=f"🎵 {audio_name}",
            font=ctk.CTkFont(size=11),
            text_color=COLOR_TEXT_SUBTLE,
            anchor="w",
        ).pack(fill="x")
