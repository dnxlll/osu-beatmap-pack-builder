"""
osu! BeatmapPack Builder
Interfaz gráfica moderna con CustomTkinter para empaquetar beatmaps de osu!.
Incluye buscador en tiempo real para seleccionar canciones directamente desde la carpeta Songs de osu!.
"""

import json
import logging
import re
import shutil
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image

# ==============================================================================
# CONFIGURACIÓN GLOBAL
# ==============================================================================

PACK_FILE: Path = Path(__file__).parent / "pack.json"
DEFAULT_CREATOR: str = ""

logging.basicConfig(
    filename=str(Path(__file__).parent / "beatmappack.log"),
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8",
)

# CTK setup debe ir antes de crear cualquier widget
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


# ==============================================================================
# HELPERS DE PERSISTENCIA (pack.json)
# ==============================================================================

def _load_pack(pack_file: Path = PACK_FILE) -> dict:
    """Carga pack.json devolviendo un dict vacío si no existe o está corrupto."""
    try:
        with open(pack_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            return {k: v for k, v in data.items() if isinstance(v, dict)}
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        logging.warning("pack.json corrupto; se inicia con pack vacío.")
        return {}


def _save_pack(pack: dict, pack_file: Path = PACK_FILE) -> None:
    """Escribe pack.json propagando errores de I/O al llamador."""
    with open(pack_file, "w", encoding="utf-8") as f:
        json.dump(pack, f, indent=4)


def _next_index(pack: dict) -> str:
    """Calcula el próximo índice incremental sin colisiones aunque haya huecos."""
    numeric_keys = [int(k) for k in pack if k.isdigit()]
    return str(max(numeric_keys, default=0) + 1)


# ==============================================================================
# LÓGICA DE NEGOCIO
# ==============================================================================

def add_map_to_pack(
    folder: Path,
    selected_osu: Path,
    patron: str = "",
    custom_version: str = "",
    pack_file: Path = PACK_FILE,
) -> tuple[str, dict]:
    """
    Agrega un mapa seleccionado a pack.json extrayendo solo el audio correspondiente,
    los recursos (imágenes), el tipo de patrón (DJ, CJ, SJ, ANCHOR) y la versión parafraseada.
    """
    mapa: dict = {}

    for archivo in folder.iterdir():
        if archivo.is_file() and archivo.suffix != ".osu":
            mapa[archivo.name] = str(archivo.absolute())

    mapa[selected_osu.name] = str(selected_osu.absolute())

    if patron and patron.strip().upper() != "NINGUNO":
        mapa["__pattern__"] = patron.strip().upper()

    if custom_version and custom_version.strip():
        mapa["__custom_version__"] = custom_version.strip()

    cancion = ""
    for linea in selected_osu.read_text(encoding="utf-8", errors="ignore").splitlines():
        if linea.startswith("AudioFilename:"):
            cancion = linea.split(":", 1)[1].strip()
            break

    extensiones_audio = (".mp3", ".ogg", ".wav")
    for clave in list(mapa.keys()):
        if clave.endswith(extensiones_audio) and clave != cancion:
            del mapa[clave]

    pack = _load_pack(pack_file)
    nuevo_indice = _next_index(pack)
    pack[nuevo_indice] = mapa
    _save_pack(pack, pack_file)

    return nuevo_indice, pack


def limpiar_bpm_od(texto: str) -> str:
    """
    Elimina menciones de BPM y OD del nombre o dificultad del mapa,
    conservando rates (ej. 1.1x, 0.95x) y nombres propios de dificultad.
    """
    if not re.search(r'bpm|\bod\s*:?\s*\d', texto, flags=re.IGNORECASE):
        return texto

    # Eliminar paréntesis que contengan BPM y/u OD
    texto = re.sub(
        r'\(\s*(?:~?\s*\d+(?:\.\d+)?(?:\s*-\s*\d+(?:\.\d+)?)?\s*bpm|\bod\s*:?\s*\d+(?:\.\d+)?)[^)]*\)',
        '', texto, flags=re.IGNORECASE,
    )
    # Eliminar corchetes que contengan solo BPM y/u OD
    texto = re.sub(
        r'\[\s*(?:~?\s*\d+(?:\.\d+)?(?:\s*-\s*\d+(?:\.\d+)?)?\s*bpm|\bod\s*:?\s*\d+(?:\.\d+)?)[^\]]*\]',
        '', texto, flags=re.IGNORECASE,
    )
    # Menciones sueltas de BPM
    texto = re.sub(r'(?<!\w)~?\s*\d+(?:\.\d+)?(?:\s*-\s*\d+(?:\.\d+)?)?\s*bpm\b', '', texto, flags=re.IGNORECASE)
    # Menciones sueltas de OD
    texto = re.sub(r'\bod\s*:?\s*\d+(?:\.\d+)?\b', '', texto, flags=re.IGNORECASE)
    # Paréntesis vacíos residuales
    texto = re.sub(r'\(\s*[,;\s–—\-/|]*\)', '', texto)
    # Separadores huérfanos cerca de brackets
    texto = re.sub(r'[\s,;–—\-/|]+\]', ']', texto)
    texto = re.sub(r'[\s,;–—\-/|]+\)', ')', texto)
    texto = re.sub(r'\[[\s,;–—\-/|]+', '[', texto)
    texto = re.sub(r'\([\s,;–—\-/|]+', '(', texto)
    # Limpiar espacios y bordes
    texto = re.sub(r'[ \t]{2,}', ' ', texto)
    texto = re.sub(r'[\s,;–—\-/|]+$', '', texto).strip()
    texto = re.sub(r'^[\s,;–—\-/|]+', '', texto).strip()

    return texto


def init_create_map(
    init_file: Path,
    callback_parafraseo=None,
    pack_file: Path = PACK_FILE,
) -> tuple[Path, int]:
    """
    Genera los mapas en la carpeta de init_file, copia los audios/imágenes
    y crea los archivos .osu adaptados con BeatmapID: 0 y nombre de dificultad corto.
    """
    need_metadatas = [
        "Title", "TitleUnicode", "Artist", "ArtistUnicode",
        "Creator", "Source", "Tags", "BeatmapID", "BeatmapSetID",
    ]

    extracted_metadata: dict[str, str] = {}
    for linea in init_file.read_text(encoding="utf-8", errors="ignore").splitlines():
        for campo in need_metadatas:
            if linea.startswith(f"{campo}:"):
                extracted_metadata[campo] = linea.split(":", 1)[1].strip()

    carpeta_salida = init_file.resolve().parent

    pack_datos = _load_pack(pack_file)
    if not pack_datos:
        return carpeta_salida, 0

    total_generados = 0
    pack_dirty = False
    audios_usados: dict[str, Path] = {}
    imagenes_usadas: dict[str, Path] = {}

    for indice, archivos_mapa in pack_datos.items():
        if not isinstance(archivos_mapa, dict):
            continue

        clave_osu = next((k for k in archivos_mapa if k.endswith(".osu")), None)
        if not clave_osu:
            continue
        ruta_osu = Path(archivos_mapa[clave_osu])

        clave_audio = next((k for k in archivos_mapa if k.lower().endswith((".mp3", ".ogg", ".wav"))), None)
        ruta_audio = Path(archivos_mapa[clave_audio]) if clave_audio else None

        clave_imagen = next((k for k in archivos_mapa if k.lower().endswith((".jpg", ".jpeg", ".png"))), None)
        ruta_imagen = Path(archivos_mapa[clave_imagen]) if clave_imagen else None

        # Leer metadatos internos del .osu por si faltan datos en el nombre del archivo
        meta_original: dict[str, str] = {}
        if ruta_osu.exists():
            in_meta = False
            for linea in ruta_osu.read_text(encoding="utf-8", errors="ignore").splitlines():
                linea = linea.strip()
                if linea == "[Metadata]":
                    in_meta = True
                    continue
                if in_meta:
                    if linea.startswith("["):
                        break
                    if ":" in linea:
                        k, v = linea.split(":", 1)
                        meta_original[k.strip()] = v.strip()

        # ==============================================================================
        # EXTRACCIÓN DEL ARTISTA, PRIMERA PALABRA DEL TÍTULO Y DIFICULTAD
        # Prioridad a ' - ' con espacios para no dividir artistas con guion interno (ej. E-Type)
        # ==============================================================================
        m = re.match(r"^(.*?)\s+-\s+(\S+).*?((?:\([^)]*\)\s*)?\[.*\])\.osu$", clave_osu)
        if not m:
            m = re.match(r"^(.*?)\s*-\s*(\S+).*?((?:\([^)]*\)\s*)?\[.*\])\.osu$", clave_osu)

        if m:
            artista = m.group(1).strip()
            primera_palabra = m.group(2).strip()
            resto = m.group(3).strip()
        else:
            m2 = (
                re.match(r"^(.*?)\s+-\s+(\S+).*?(\([^)]*\))\s*\.osu$", clave_osu)
                or re.match(r"^(.*?)\s*-\s*(\S+).*?(\([^)]*\))\s*\.osu$", clave_osu)
            )
            if m2:
                artista = m2.group(1).strip()
                primera_palabra = m2.group(2).strip()
                resto = f"[{m2.group(3).strip('()')}]"
            else:
                m3 = re.match(r"^(.*?)\s*-\s*(\([^)]*\))\s*\.osu$", clave_osu)
                if m3:
                    artista = m3.group(1).strip()
                    diff = m3.group(2).strip("()")
                    primera_palabra = diff.split()[0] if diff else artista
                    resto = f"[{diff}]"
                else:
                    artista = meta_original.get("Artist", "").strip() or "Unknown"
                    title = meta_original.get("Title", "").strip()
                    primera_palabra = title.split()[0] if title else Path(clave_osu).stem.split()[0]
                    resto = f"[{meta_original.get('Version', Path(clave_osu).stem)}]"

        # Limpiar tags de patrón que pudieran estar en artista o primera palabra
        artista = re.sub(r"^\[(DJ|CJ|SJ|ANCHOR)\]\s*", "", artista, flags=re.IGNORECASE).strip()
        primera_palabra = re.sub(r"^\[(DJ|CJ|SJ|ANCHOR)\]\s*", "", primera_palabra, flags=re.IGNORECASE).strip()

        primera_palabra_limpia = re.sub(r'[\\/*?:"<>|]', "", primera_palabra)
        if not primera_palabra_limpia:
            primera_palabra_limpia = f"SONG_{indice}"

        patron_tag = archivos_mapa.get("__pattern__") or archivos_mapa.get("patron") or ""
        patron_tag = patron_tag.upper().strip() if patron_tag and patron_tag.upper() != "NINGUNO" else ""

        resto = limpiar_bpm_od(resto)

        if patron_tag:
            version_final = f"[{patron_tag}] {artista} - {primera_palabra} {resto}"
        else:
            version_final = f"{artista} - {primera_palabra} {resto}"

        version_final = limpiar_bpm_od(version_final)

        # ==============================================================================
        # GESTIÓN Y RENOMBRADO DEL AUDIO
        # ==============================================================================
        nombre_audio_destino = None
        if ruta_audio and ruta_audio.exists():
            ext_audio = ruta_audio.suffix.lower()
            nombre_audio_propuesto = f"{primera_palabra_limpia.upper()}{ext_audio}"

            if nombre_audio_propuesto in audios_usados and audios_usados[nombre_audio_propuesto] != ruta_audio:
                nombre_audio_propuesto = f"{primera_palabra_limpia.upper()}_{indice}{ext_audio}"

            audios_usados[nombre_audio_propuesto] = ruta_audio
            shutil.copyfile(ruta_audio, carpeta_salida / nombre_audio_propuesto)
            nombre_audio_destino = nombre_audio_propuesto

        # ==============================================================================
        # GESTIÓN Y OPTIMIZACIÓN DE LA IMAGEN DE FONDO
        # Convierte a JPG optimizado (max 1080p, calidad 85) para no exceder los 100 MB de osu!
        # ==============================================================================
        nombre_imagen_destino = None
        if ruta_imagen and ruta_imagen.exists():
            nombre_imagen_propuesto = f"{primera_palabra_limpia.upper()}_bg.jpg"
            if nombre_imagen_propuesto in imagenes_usadas and imagenes_usadas[nombre_imagen_propuesto] != ruta_imagen:
                nombre_imagen_propuesto = f"{primera_palabra_limpia.upper()}_bg_{indice}.jpg"

            imagenes_usadas[nombre_imagen_propuesto] = ruta_imagen
            destino_imagen = carpeta_salida / nombre_imagen_propuesto

            try:
                with Image.open(ruta_imagen) as im:
                    im_rgb = im.convert("RGB")
                    w, h = im_rgb.size
                    if w > 1920 or h > 1080:
                        im_rgb.thumbnail((1920, 1080), Image.Resampling.LANCZOS)
                    im_rgb.save(destino_imagen, format="JPEG", quality=85, optimize=True)
            except Exception as exc:
                logging.warning("No se pudo optimizar imagen %s: %s", ruta_imagen, exc)
                shutil.copyfile(ruta_imagen, destino_imagen)

            nombre_imagen_destino = nombre_imagen_propuesto

        # Construir prefijo base del nombre del archivo .osu generado
        prefix_base = re.sub(r"\s*\[.*\]$", "", init_file.stem).strip()
        if not prefix_base:
            artista_pack = re.sub(r'[\\/*?:"<>|]', "", extracted_metadata.get("Artist", "Various Artists")).strip()
            titulo_pack = re.sub(r'[\\/*?:"<>|]', "", extracted_metadata.get("Title", "Pack")).strip()
            creador_pack = re.sub(r'[\\/*?:"<>|]', "", extracted_metadata.get("Creator", DEFAULT_CREATOR)).strip()
            prefix_base = (
                f"{artista_pack} - {titulo_pack} ({creador_pack})"
                if creador_pack
                else f"{artista_pack} - {titulo_pack}"
            )

        prefix_base_limpio = re.sub(r'[\\/*?:"<>|]', "", prefix_base).strip()

        custom_version = archivos_mapa.get("__custom_version__")
        if custom_version and custom_version.strip():
            version_final = custom_version.strip()

        version_limpia_archivo = re.sub(r'[\\/*?:"<>|]', "", version_final).strip()
        nombre_nuevo = f"{prefix_base_limpio} [{version_limpia_archivo}].osu"

        # Invocar callback de parafraseo si el nombre excede el límite seguro de osu!
        if len(nombre_nuevo) > 125 and callback_parafraseo:
            version_parafraseada = callback_parafraseo(indice, clave_osu, version_final, prefix_base_limpio)
            if version_parafraseada and version_parafraseada.strip():
                version_final = version_parafraseada.strip()
                version_limpia_archivo = re.sub(r'[\\/*?:"<>|]', "", version_final).strip()
                nombre_nuevo = f"{prefix_base_limpio} [{version_limpia_archivo}].osu"
                archivos_mapa["__custom_version__"] = version_final
                pack_dirty = True

        simple = carpeta_salida / nombre_nuevo

        if init_file.resolve() != simple.resolve():
            shutil.copyfile(init_file, simple)

        # ==============================================================================
        # CONSTRUCCIÓN DEL ARCHIVO .OSU SIMPLE
        # ==============================================================================
        datos_originales = {
            "BeatmapID": "0",
            "Version": version_final,
        }
        if nombre_audio_destino:
            datos_originales["AudioFilename"] = nombre_audio_destino

        # Encabezado (hasta [Events]) con metadatos actualizados
        lineas_encabezado: list[str] = []
        for linea in simple.read_text(encoding="utf-8", errors="ignore").splitlines():
            if linea.strip() == "[Events]":
                break

            # Proteger contra el error MySQL 'Data too long for column tags'
            if linea.startswith("Tags:") and len(linea) > 900:
                raw_tags = linea.split(":", 1)[1].split()
                cleaned_tags: list[str] = []
                cur_len = 0
                for t in raw_tags:
                    if cur_len + len(t) + 1 <= 850:
                        cleaned_tags.append(t)
                        cur_len += len(t) + 1
                linea = f"Tags:{' '.join(cleaned_tags)}"

            modificada = False
            for nombre_campo, valor in datos_originales.items():
                if linea.startswith(f"{nombre_campo}:"):
                    lineas_encabezado.append(f"{nombre_campo}: {valor}")
                    modificada = True
                    break
            if not modificada:
                lineas_encabezado.append(linea)

        # Cuerpo (desde [Events]) con imagen de fondo actualizada
        lineas_cuerpo: list[str] = []
        desde_events = False
        bg_actualizado = False
        if ruta_osu.exists():
            for linea in ruta_osu.read_text(encoding="utf-8", errors="ignore").splitlines():
                if linea.strip() == "[Events]":
                    desde_events = True
                    lineas_cuerpo.append(linea)
                    continue
                if desde_events:
                    if re.match(r'^\s*0\s*,\s*0\s*,', linea) and nombre_imagen_destino:
                        linea = re.sub(
                            r'^(\s*0\s*,\s*0\s*,\s*)"?[^",]+"?(.*)$',
                            rf'\1"{nombre_imagen_destino}"\2',
                            linea,
                        )
                        bg_actualizado = True
                    lineas_cuerpo.append(linea)

            if nombre_imagen_destino and not bg_actualizado and desde_events:
                try:
                    idx_events = lineas_cuerpo.index("[Events]")
                    lineas_cuerpo.insert(idx_events + 1, f'0,0,"{nombre_imagen_destino}",0,0')
                except ValueError:
                    pass

        # Usar \r\n para compatibilidad con el formato Windows de osu!
        contenido_final = "\r\n".join(lineas_encabezado + lineas_cuerpo)
        simple.write_text(contenido_final, encoding="utf-8")
        total_generados += 1

    # Persistir versiones parafraseadas en una sola escritura al final
    if pack_dirty:
        try:
            _save_pack(pack_datos, pack_file)
        except OSError as exc:
            logging.warning("No se pudo persistir versiones parafraseadas en pack.json: %s", exc)

    return carpeta_salida, total_generados


# ==============================================================================
# DETECCIÓN DE PATRONES
# ==============================================================================

def detectar_patron_sugerido(texto: str) -> str:
    """Detecta automáticamente patrones conocidos (DJ, CJ, SJ, ANCHOR) en un nombre."""
    texto_upper = texto.upper()
    if re.search(r"\b(ANCHOR|ANCHORS)\b", texto_upper) or "[ANCHOR]" in texto_upper:
        return "ANCHOR"
    if re.search(r"\b(SPEED\s*JACKS?|SJ)\b", texto_upper) or "[SJ]" in texto_upper:
        return "SJ"
    if re.search(r"\b(CHORD\s*JACKS?|CJ)\b", texto_upper) or "[CJ]" in texto_upper:
        return "CJ"
    if re.search(r"\b(DENSE\s*JACKS?|DJ)\b", texto_upper) or "[DJ]" in texto_upper:
        return "DJ"
    return ""


# ==============================================================================
# HELPERS DE UI
# ==============================================================================

def _centrar_ventana(ventana: ctk.CTkToplevel, parent: ctk.CTk, ancho: int, alto: int) -> None:
    """Centra una ventana modal respecto a su parent."""
    ventana.update_idletasks()
    try:
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (ancho // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (alto // 2)
        ventana.geometry(f"+{max(0, x)}+{max(0, y)}")
    except tk.TclError:
        pass


# ==============================================================================
# DIÁLOGOS MODALES
# ==============================================================================

class PatronModalDialog(ctk.CTkToplevel):
    """
    Ventana modal interactiva que pide al usuario seleccionar el tipo de patrón
    (DJ, CJ, SJ, ANCHOR o Ninguno) antes de registrar el mapa en pack.json.
    """
    def __init__(self, parent: ctk.CTk, map_name: str, sugerido: str = "") -> None:
        super().__init__(parent)
        self.title("Tipo de Patrón")
        self.geometry("460x260")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        _centrar_ventana(self, parent, 460, 260)

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
            text_color="#3B8ED0",
            wraplength=420,
            justify="center",
        ).pack(pady=(0, 14), padx=20)

        frame_patrones = ctk.CTkFrame(self, fg_color="transparent")
        frame_patrones.pack(pady=4, padx=20, fill="x")

        patrones = [
            ("DJ", "Dense Jack", "#1F6AA5"),
            ("CJ", "Chordjack", "#8E44AD"),
            ("SJ", "Speedjack", "#D35400"),
            ("ANCHOR", "Anchor", "#27AE60"),
        ]
        for code, desc, color in patrones:
            ctk.CTkButton(
                frame_patrones,
                text=f"{code}\n({desc})",
                font=ctk.CTkFont(size=12, weight="bold"),
                fg_color="#2FA572" if code == sugerido else color,
                height=52,
                command=lambda c=code: self._seleccionar(c),
            ).pack(side="left", fill="both", expand=True, padx=3)

        frame_inferior = ctk.CTkFrame(self, fg_color="transparent")
        frame_inferior.pack(pady=(16, 12), padx=20, fill="x")

        ctk.CTkButton(
            frame_inferior,
            text="Sin Patrón (Ninguno)",
            fg_color="#4A4A4A",
            hover_color="#333333",
            height=30,
            command=lambda: self._seleccionar(""),
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            frame_inferior,
            text="Cancelar",
            fg_color="#A52F2F",
            hover_color="#7A1E1E",
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
    """
    Ventana modal que se muestra cuando el nombre de un archivo .osu excede
    el límite seguro de osu! (evitando el error 'Data too long for column filename').
    """
    def __init__(self, parent: ctk.CTk, prefix_base: str, version_original: str, max_len: int = 125) -> None:
        super().__init__(parent)
        self.title("⚠️ Nombre Demasiado Largo")
        self.geometry("580x400")
        self.minsize(500, 340)
        self.transient(parent)
        self.grab_set()
        _centrar_ventana(self, parent, 580, 400)

        self.prefix_base = prefix_base
        self.max_len = max_len
        self.resultado: str | None = None

        ctk.CTkLabel(
            self,
            text="⚠️ Nombre de Archivo Demasiado Largo",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#FFB300",
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

        frame_editor = ctk.CTkFrame(self, fg_color="#1E1E1E", border_width=1, border_color="#333333")
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

        self.lbl_contador = ctk.CTkLabel(frame_editor, text="", font=ctk.CTkFont(size=12, weight="bold"))
        self.lbl_contador.pack(anchor="w", padx=12, pady=(2, 8))
        self._actualizar_contador()

        frame_acciones = ctk.CTkFrame(self, fg_color="transparent")
        frame_acciones.pack(fill="x", padx=20, pady=(12, 10))

        self.btn_guardar = ctk.CTkButton(
            frame_acciones,
            text="✓ Usar este Nombre",
            fg_color="#2FA572",
            hover_color="#1E7A52",
            height=36,
            command=self._confirmar,
        )
        self.btn_guardar.pack(side="left", fill="x", expand=True, padx=(0, 6))

        ctk.CTkButton(
            frame_acciones,
            text="Omitir (dejar largo)",
            fg_color="#4A4A4A",
            hover_color="#333333",
            height=36,
            command=lambda: self._finalizar(version_original),
        ).pack(side="right", padx=(6, 0))

    def _actualizar_contador(self, event=None) -> None:
        val = self.entry_version.get().strip()
        total_len = len(f"{self.prefix_base} [{val}].osu")
        if total_len <= self.max_len:
            self.lbl_contador.configure(
                text=f"✓ Longitud total: {total_len} / {self.max_len} caracteres (Seguro para osu!)",
                text_color="#2FA572",
            )
            self.btn_guardar.configure(state="normal")
        else:
            exceso = total_len - self.max_len
            self.lbl_contador.configure(
                text=f"⚠️ Longitud total: {total_len} / {self.max_len} caracteres (+{exceso} exceso, ¡acorta!)",
                text_color="#FF4D4D",
            )

    def _confirmar(self) -> None:
        val = self.entry_version.get().strip()
        if not val:
            messagebox.showwarning("Atención", "El nombre no puede estar vacío.")
            return
        self._finalizar(val)

    def _finalizar(self, valor: str) -> None:
        self.resultado = valor
        self.destroy()


# ==============================================================================
# INTERFAZ GRÁFICA PRINCIPAL
# ==============================================================================

class BeatmapPackApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()

        self.title("osu! BeatmapPack Builder")
        self.geometry("760x850")
        self.minsize(700, 650)
        self.resizable(True, True)

        # Estado
        self.songs_dir: Path = self._detectar_directorio_songs()
        self.carpetas_songs: list[Path] = []
        self.init_file: Path | None = None
        self.carpeta_mapa_actual: Path | None = None
        self.archivos_osu_encontrados: list[Path] = []
        self.archivos_base_disponibles: list[Path] = []

        # Atributos de UI — asignados en _crear_widgets
        self.seg_patron: ctk.CTkSegmentedButton | None = None
        self.entry_custom_version: ctk.CTkEntry | None = None

        self._cargar_indice_songs()
        self._crear_widgets()
        self._actualizar_lista_pack()

    # --------------------------------------------------------------------------
    # DIRECTORIO SONGS
    # --------------------------------------------------------------------------

    def _detectar_directorio_songs(self) -> Path:
        """Detecta automáticamente la carpeta Songs de osu!."""
        posibles_rutas = [
            Path.home() / "AppData" / "Local" / "osu!" / "Songs",
            Path(r"C:\osu!\Songs"),
            Path(r"D:\osu!\Songs"),
        ]
        for ruta in posibles_rutas:
            if ruta.exists() and ruta.is_dir():
                return ruta
        return Path.cwd()

    def _cargar_indice_songs(self) -> None:
        """Carga en memoria la lista de carpetas dentro del directorio Songs."""
        if not (self.songs_dir.exists() and self.songs_dir.is_dir()):
            self.carpetas_songs = []
            return
        try:
            self.carpetas_songs = [f for f in self.songs_dir.iterdir() if f.is_dir()]
        except OSError as exc:
            logging.error("No se pudo leer el directorio Songs: %s", exc)
            messagebox.showwarning(
                "Error al leer Songs",
                f"No se pudo leer el directorio Songs:\n{exc}\n\nUsa 'Cambiar Songs...' para seleccionar otro.",
            )
            self.carpetas_songs = []

    # --------------------------------------------------------------------------
    # CONSTRUCCIÓN DE UI
    # --------------------------------------------------------------------------

    def _crear_widgets(self) -> None:
        self._crear_cabecera()

        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_frame.pack(fill="both", expand=True, padx=15, pady=(0, 6))

        self._crear_seccion_paso1()
        self._crear_seccion_paso2()
        self._crear_seccion_paso3()
        self._crear_footer()

    def _crear_cabecera(self) -> None:
        ctk.CTkLabel(
            self, text="osu! BeatmapPack Builder", font=ctk.CTkFont(size=22, weight="bold")
        ).pack(pady=(10, 2))

        frame_songs_bar = ctk.CTkFrame(self, fg_color="transparent")
        frame_songs_bar.pack(fill="x", padx=20, pady=(0, 4))

        self.lbl_songs_dir = ctk.CTkLabel(
            frame_songs_bar,
            text=f"📁 Directorio Songs: {self.songs_dir} ({len(self.carpetas_songs)} mapas)",
            text_color="#3B8ED0",
            font=ctk.CTkFont(size=12),
        )
        self.lbl_songs_dir.pack(side="left", padx=5)

        ctk.CTkButton(
            frame_songs_bar, text="Cambiar Songs...", width=110, height=24,
            command=self._cambiar_directorio_songs,
        ).pack(side="right", padx=5)

    def _crear_seccion_paso1(self) -> None:
        frame_init = ctk.CTkFrame(self.scroll_frame)
        frame_init.pack(fill="x", pady=6)

        ctk.CTkLabel(
            frame_init, text="Paso 1: Carpeta Base (init_file)", font=ctk.CTkFont(size=15, weight="bold")
        ).pack(anchor="w", padx=15, pady=(8, 2))

        frame_init_search = ctk.CTkFrame(frame_init, fg_color="transparent")
        frame_init_search.pack(fill="x", padx=15, pady=4)

        self.entry_buscar_init = ctk.CTkEntry(
            frame_init_search, placeholder_text="🔍 Buscar carpeta base en Songs (ej. ScriptTest)..."
        )
        self.entry_buscar_init.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.entry_buscar_init.bind("<KeyRelease>", self._on_buscar_init)
        self.entry_buscar_init.bind("<Return>", self._on_enter_init)

        ctk.CTkButton(
            frame_init_search, text="Examinar...", width=95, command=self._seleccionar_carpeta_base_manual
        ).pack(side="right")

        self.frame_res_init = ctk.CTkFrame(frame_init, fg_color="#1E1E1E", border_width=1, border_color="#333333")

        self.combo_init = ctk.CTkOptionMenu(
            frame_init, values=["(Selecciona una carpeta base primero)"],
            command=self._cambiar_init_file,
        )

        self.lbl_init_status = ctk.CTkLabel(
            frame_init, text="Ninguna carpeta base seleccionada", text_color="gray"
        )
        self.lbl_init_status.pack(anchor="w", padx=15, pady=(2, 8))

    def _crear_seccion_paso2(self) -> None:
        frame_mapas = ctk.CTkFrame(self.scroll_frame)
        frame_mapas.pack(fill="x", pady=6)

        ctk.CTkLabel(
            frame_mapas, text="Paso 2: Buscar y Añadir Mapas al Pack", font=ctk.CTkFont(size=15, weight="bold")
        ).pack(anchor="w", padx=15, pady=(8, 2))

        frame_mapas_search = ctk.CTkFrame(frame_mapas, fg_color="transparent")
        frame_mapas_search.pack(fill="x", padx=15, pady=4)

        self.entry_buscar_mapa = ctk.CTkEntry(
            frame_mapas_search,
            placeholder_text="🔍 Escribe para buscar (ej. goreshit, Zhanulka, 2272322)...",
        )
        self.entry_buscar_mapa.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.entry_buscar_mapa.bind("<KeyRelease>", self._on_buscar_mapa)
        self.entry_buscar_mapa.bind("<Return>", self._on_enter_mapa)

        ctk.CTkButton(
            frame_mapas_search, text="Examinar...", width=95, command=self._seleccionar_carpeta_mapa_manual
        ).pack(side="right")

        self.frame_res_mapas = ctk.CTkFrame(
            frame_mapas, fg_color="#1E1E1E", border_width=1, border_color="#333333"
        )

        self.lbl_mapa_folder = ctk.CTkLabel(
            frame_mapas, text="Busca una canción arriba o examina manualmente", text_color="gray"
        )
        self.lbl_mapa_folder.pack(anchor="w", padx=15, pady=(2, 2))

        ctk.CTkLabel(frame_mapas, text="Seleccionar dificultad (.osu):").pack(anchor="w", padx=15, pady=(4, 0))

        self.combo_osus = ctk.CTkOptionMenu(
            frame_mapas, values=["(Primero busca y selecciona un mapa)"],
            command=self._on_cambio_osu_elegido,
        )
        self.combo_osus.pack(fill="x", padx=15, pady=4)

        ctk.CTkLabel(
            frame_mapas,
            text="Tipo de patrón (clasificación del jack):",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(anchor="w", padx=15, pady=(6, 2))

        self.seg_patron = ctk.CTkSegmentedButton(
            frame_mapas, values=["DJ", "CJ", "SJ", "ANCHOR", "Ninguno"], height=32
        )
        self.seg_patron.set("Ninguno")
        self.seg_patron.pack(fill="x", padx=15, pady=(2, 6))

        ctk.CTkLabel(
            frame_mapas,
            text="Nombre / Versión parafraseada (opcional si es muy largo):",
            font=ctk.CTkFont(size=11),
        ).pack(anchor="w", padx=15, pady=(4, 0))

        self.entry_custom_version = ctk.CTkEntry(
            frame_mapas,
            placeholder_text="Déjalo vacío para usar el automático, o escribe un nombre corto...",
        )
        self.entry_custom_version.pack(fill="x", padx=15, pady=(2, 6))

        self.btn_add_to_pack = ctk.CTkButton(
            frame_mapas, text="Añadir Dificultad al Pack", fg_color="#2FA572", hover_color="#1E7A52",
            command=self._agregar_mapa_a_pack, state="disabled",
        )
        self.btn_add_to_pack.pack(anchor="w", padx=15, pady=(4, 10))

    def _crear_seccion_paso3(self) -> None:
        frame_resumen = ctk.CTkFrame(self.scroll_frame)
        frame_resumen.pack(fill="x", pady=6)

        ctk.CTkLabel(
            frame_resumen, text="Mapas registrados en pack.json:", font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", padx=15, pady=(8, 4))

        self.txt_pack = ctk.CTkTextbox(frame_resumen, height=120)
        self.txt_pack.pack(fill="x", padx=15, pady=4)

        ctk.CTkButton(
            frame_resumen, text="Vaciar / Resetear pack.json", fg_color="#A52F2F", hover_color="#7A1E1E",
            command=self._limpiar_pack,
        ).pack(anchor="e", padx=15, pady=(4, 8))

    def _crear_footer(self) -> None:
        frame_footer = ctk.CTkFrame(self, fg_color="transparent")
        frame_footer.pack(fill="x", padx=20, pady=(4, 10))

        ctk.CTkButton(
            frame_footer, text="⚡ Generar Pack de Mapas Final", font=ctk.CTkFont(size=16, weight="bold"),
            height=46, fg_color="#1F6AA5", hover_color="#144870",
            command=self._generar_pack_final,
        ).pack(fill="x")

    # --------------------------------------------------------------------------
    # BUSCADORES EN TIEMPO REAL
    # --------------------------------------------------------------------------

    def _filtrar_carpetas(self, query: str, limit: int = 8) -> list[Path]:
        """Filtra carpetas Songs por múltiples palabras clave (AND)."""
        palabras = query.strip().lower().split()
        if not palabras:
            return []
        return [f for f in self.carpetas_songs if all(p in f.name.lower() for p in palabras)][:limit]

    def _cambiar_directorio_songs(self) -> None:
        nueva_ruta = filedialog.askdirectory(title="Selecciona tu carpeta Songs de osu!")
        if nueva_ruta:
            self.songs_dir = Path(nueva_ruta)
            self._cargar_indice_songs()
            self.lbl_songs_dir.configure(
                text=f"📁 Directorio Songs: {self.songs_dir} ({len(self.carpetas_songs)} mapas)"
            )

    def _on_buscar_init(self, event=None) -> None:
        query = self.entry_buscar_init.get().strip().lower()
        for w in self.frame_res_init.winfo_children():
            w.destroy()

        if not query:
            self.frame_res_init.pack_forget()
            return

        coincidencias = self._filtrar_carpetas(query)
        self.frame_res_init.pack(fill="x", padx=15, pady=(0, 4))

        if not coincidencias:
            ctk.CTkLabel(self.frame_res_init, text="Sin coincidencias", text_color="gray").pack(padx=8, pady=3)
            return

        for carpeta in coincidencias:
            ctk.CTkButton(
                self.frame_res_init, text=f"📁 {carpeta.name}", anchor="w",
                fg_color="transparent", hover_color="#2A2D32", text_color="#E0E0E0", height=26,
                command=lambda c=carpeta: self._seleccionar_carpeta_base_desde_busqueda(c),
            ).pack(fill="x", padx=2, pady=1)

    def _on_enter_init(self, event=None) -> None:
        query = self.entry_buscar_init.get().strip().lower()
        coincidencias = self._filtrar_carpetas(query, limit=1)
        if coincidencias:
            self._seleccionar_carpeta_base_desde_busqueda(coincidencias[0])

    def _seleccionar_carpeta_base_desde_busqueda(self, carpeta: Path) -> None:
        self.entry_buscar_init.delete(0, "end")
        self.frame_res_init.pack_forget()
        self._cargar_carpeta_base(carpeta)

    def _seleccionar_carpeta_base_manual(self) -> None:
        ruta = filedialog.askdirectory(title="Selecciona la Carpeta Base (con init_file)")
        if ruta:
            self._cargar_carpeta_base(Path(ruta))

    def _cargar_carpeta_base(self, carpeta: Path) -> None:
        archivos_osu = list(carpeta.glob("*.osu"))

        if not archivos_osu:
            messagebox.showerror(
                "Error",
                f"No se encontró ningún archivo .osu en:\n{carpeta.name}\n"
                "Asegúrate de que contenga el archivo base .osu.",
            )
            self.init_file = None
            self.lbl_init_status.configure(text="Error: no se encontró archivo .osu", text_color="#E54D42")
            return

        self.archivos_base_disponibles = archivos_osu
        nombres = [f.name for f in archivos_osu]

        archivos_delete = [f for f in archivos_osu if "delete" in f.name.lower()]
        predeterminado = archivos_delete[0] if archivos_delete else archivos_osu[0]
        self.init_file = predeterminado

        if len(archivos_osu) > 1:
            self.combo_init.configure(values=nombres)
            self.combo_init.set(predeterminado.name)
            self.combo_init.pack(fill="x", padx=15, pady=(2, 6))
            self.lbl_init_status.configure(
                text=f"✓ Múltiples .osu. Base seleccionada: {predeterminado.name}",
                text_color="#2FA572",
            )
        else:
            self.combo_init.pack_forget()
            self.lbl_init_status.configure(
                text=f"✓ Archivo base detectado: {self.init_file.name}", text_color="#2FA572"
            )

    def _cambiar_init_file(self, nombre_elegido: str) -> None:
        for f in self.archivos_base_disponibles:
            if f.name == nombre_elegido:
                self.init_file = f
                self.lbl_init_status.configure(
                    text=f"✓ Base seleccionada: {self.init_file.name}", text_color="#2FA572"
                )
                break

    def _on_buscar_mapa(self, event=None) -> None:
        query = self.entry_buscar_mapa.get().strip().lower()
        for w in self.frame_res_mapas.winfo_children():
            w.destroy()

        if not query:
            self.frame_res_mapas.pack_forget()
            return

        coincidencias = self._filtrar_carpetas(query)
        self.frame_res_mapas.pack(fill="x", padx=15, pady=(0, 4))

        if not coincidencias:
            ctk.CTkLabel(self.frame_res_mapas, text="No se encontraron mapas en Songs", text_color="gray").pack(
                padx=8, pady=3
            )
            return

        for carpeta in coincidencias:
            ctk.CTkButton(
                self.frame_res_mapas,
                text=f"📁 {carpeta.name}",
                anchor="w",
                fg_color="transparent",
                hover_color="#1E3A5F",
                text_color="#E0E0E0",
                height=28,
                command=lambda c=carpeta: self._seleccionar_mapa_desde_busqueda(c),
            ).pack(fill="x", padx=2, pady=1)

    def _on_enter_mapa(self, event=None) -> None:
        query = self.entry_buscar_mapa.get().strip().lower()
        coincidencias = self._filtrar_carpetas(query, limit=1)
        if coincidencias:
            self._seleccionar_mapa_desde_busqueda(coincidencias[0])

    def _seleccionar_mapa_desde_busqueda(self, carpeta: Path) -> None:
        self.entry_buscar_mapa.delete(0, "end")
        self.frame_res_mapas.pack_forget()
        self._cargar_carpeta_mapa(carpeta)

    def _seleccionar_carpeta_mapa_manual(self) -> None:
        ruta = filedialog.askdirectory(title="Selecciona la Carpeta del Mapa")
        if ruta:
            self._cargar_carpeta_mapa(Path(ruta))

    def _cargar_carpeta_mapa(self, carpeta: Path) -> None:
        archivos_osu = [f for f in carpeta.iterdir() if f.is_file() and f.suffix == ".osu"]

        if not archivos_osu:
            messagebox.showwarning("Atención", f"La carpeta '{carpeta.name}' no contiene archivos .osu.")
            return

        self.carpeta_mapa_actual = carpeta
        self.archivos_osu_encontrados = archivos_osu
        self.lbl_mapa_folder.configure(text=f"✓ Carpeta: {carpeta.name}", text_color="#3B8ED0")

        nombres_osu = [f.name for f in archivos_osu]
        self.combo_osus.configure(values=nombres_osu)
        self.combo_osus.set(nombres_osu[0])
        self._on_cambio_osu_elegido(nombres_osu[0])
        self.btn_add_to_pack.configure(state="normal")

    def _on_cambio_osu_elegido(self, valor_osu: str) -> None:
        sugerido = detectar_patron_sugerido(valor_osu)
        self.seg_patron.set(sugerido if sugerido else "Ninguno")

    # --------------------------------------------------------------------------
    # ACCIONES DEL PACK
    # --------------------------------------------------------------------------

    def _agregar_mapa_a_pack(self) -> None:
        if not self.carpeta_mapa_actual or not self.archivos_osu_encontrados:
            return

        nombre_elegido = self.combo_osus.get()
        osu_elegido = next((f for f in self.archivos_osu_encontrados if f.name == nombre_elegido), None)

        if not osu_elegido:
            messagebox.showerror("Error", "No se encontró el archivo .osu seleccionado.")
            return

        patron_actual = self.seg_patron.get()

        if not patron_actual or patron_actual == "Ninguno":
            sugerido = detectar_patron_sugerido(osu_elegido.name)
            dialogo = PatronModalDialog(self, map_name=osu_elegido.name, sugerido=sugerido)
            self.wait_window(dialogo)
            if dialogo.resultado is None:
                return
            patron_actual = dialogo.resultado
            self.seg_patron.set(patron_actual if patron_actual else "Ninguno")

        patron_para_guardar = patron_actual if patron_actual != "Ninguno" else ""
        version_personalizada = self.entry_custom_version.get().strip()

        try:
            indice, _ = add_map_to_pack(
                self.carpeta_mapa_actual, osu_elegido,
                patron=patron_para_guardar, custom_version=version_personalizada,
            )
            tag_msg = f" [{patron_para_guardar}]" if patron_para_guardar else ""
            messagebox.showinfo("Éxito", f"Dificultad{tag_msg} agregada al pack con índice '{indice}'.")
            self._actualizar_lista_pack()

            # Reiniciar estado para el siguiente mapa
            self.combo_osus.configure(values=["(Busca otra canción arriba para continuar)"])
            self.combo_osus.set("(Busca otra canción arriba para continuar)")
            self.seg_patron.set("Ninguno")
            self.entry_custom_version.delete(0, "end")
            self.btn_add_to_pack.configure(state="disabled")
            self.lbl_mapa_folder.configure(
                text="Escribe arriba para buscar y agregar el siguiente mapa...", text_color="gray"
            )
            self.carpeta_mapa_actual = None
            self.archivos_osu_encontrados = []
        except Exception as e:
            messagebox.showerror("Error al guardar", f"Ocurrió un error al procesar el mapa:\n{e}")

    def _actualizar_lista_pack(self) -> None:
        self.txt_pack.delete("1.0", "end")
        pack = _load_pack(PACK_FILE)

        if not pack:
            self.txt_pack.insert("end", "El archivo pack.json está vacío.\n")
            return

        contador = 0
        for indice, mapa in pack.items():
            if not isinstance(mapa, dict):
                continue

            osu_name = next((k for k in mapa.keys() if k.endswith(".osu")), "Desconocido")
            audio_name = next(
                (k for k in mapa.keys() if k.lower().endswith((".mp3", ".ogg", ".wav"))), "Sin audio"
            )
            patron = mapa.get("__pattern__") or mapa.get("patron") or ""
            tag_patron = f"[{patron}] " if patron and patron.upper() != "NINGUNO" else ""
            patron_desc = f"Patrón: [{patron}] | " if patron and patron.upper() != "NINGUNO" else ""
            custom_v = mapa.get("__custom_version__")
            custom_desc = f"    └─ Parafraseado: {custom_v}\n" if custom_v else ""

            self.txt_pack.insert(
                "end",
                f"[{indice}] {tag_patron}{limpiar_bpm_od(osu_name)}\n"
                f"{custom_desc}    └─ {patron_desc}Audio: {audio_name}\n",
            )
            contador += 1

        if contador == 0:
            self.txt_pack.insert("end", "No hay mapas válidos registrados en pack.json.\n")

    def _limpiar_pack(self) -> None:
        if not messagebox.askyesno("Confirmar", "¿Seguro que deseas vaciar pack.json?"):
            return
        try:
            _save_pack({}, PACK_FILE)
            self._actualizar_lista_pack()
            messagebox.showinfo("Listo", "pack.json ha sido reseteado.")
        except OSError as exc:
            messagebox.showerror("Error", f"No se pudo vaciar pack.json:\n{exc}")

    def _solicitar_parafraseo(self, indice: str, clave_osu: str, version_original: str, prefix_base: str) -> str:
        dialogo = ParafraseoDialog(self, prefix_base=prefix_base, version_original=version_original, max_len=125)
        self.wait_window(dialogo)
        return dialogo.resultado or version_original

    def _generar_pack_final(self) -> None:
        if not self.init_file or not self.init_file.exists():
            messagebox.showerror(
                "Falta Archivo Base",
                "Debes completar el Paso 1 y seleccionar una carpeta base válida que contenga init_file.",
            )
            return

        if not _load_pack(PACK_FILE):
            messagebox.showerror(
                "Pack Vacío",
                "Debes agregar al menos un mapa en el Paso 2 antes de generar el pack.",
            )
            return

        try:
            carpeta_generada, cantidad = init_create_map(
                self.init_file, callback_parafraseo=self._solicitar_parafraseo
            )
            messagebox.showinfo(
                "¡Pack Generado con Éxito!",
                f"Se generaron {cantidad} archivo(s) .osu correctamente en tu carpeta de canciones:\n"
                f"{carpeta_generada.resolve()}",
            )
            self._actualizar_lista_pack()
        except Exception as e:
            messagebox.showerror("Error al generar", f"Ocurrió un error inesperado al generar el pack:\n{e}")


# ==============================================================================
# PUNTO DE ENTRADA PRINCIPAL
# ==============================================================================
if __name__ == "__main__":
    app = BeatmapPackApp()
    app.mainloop()
