# osu! BeatmapPack Builder

Aplicación de escritorio en **Python + CustomTkinter** para buscar, organizar y empaquetar beatmaps de **osu!** en un único pack listo para jugar o compartir, manteniendo consistencia en los nombres de dificultad, optimización de fondos y compatibilidad con los límites internos de osu!.

![Vista previa de osu! BeatmapPack Builder](docs/preview.jpg)

---

## Funcionalidades principales

- **Detección y búsqueda en tiempo real:**
  - Detecta automáticamente tu carpeta `Songs` de osu! (con opción manual **"Cambiar Songs..."**).
  - Buscador instantáneo multi-palabra para seleccionar tanto la carpeta base (`init_file`) como los mapas que quieres añadir al pack.
- **Clasificación por patrón (Jacks / Anchor):**
  - Etiquetado por patrón: **DJ** (Dense Jack), **CJ** (Chordjack), **SJ** (Speedjack) y **ANCHOR**.
  - Sugerencia automática basada en el nombre de la dificultad y diálogo modal rápido si no se ha seleccionado ninguno.
- **Galería visual de fichas (Split-View responsivo):**
  - Panel derecho adaptable de **1 a 3 columnas** según el tamaño de la ventana, mostrando la miniatura del fondo (`.jpg`, `.jpeg`, `.png`, `.webp`), el audio asociado, el patrón y una vista previa del nombre final.
  - Barra superior con contadores y **filtro rápido por patrón**.
- **Edición y gestión directa del pack:**
  - Botón **`✎`** en cada ficha para cambiar la dificultad `.osu` (actualizando automáticamente el audio y la imagen), el patrón o la versión parafraseada sin tener que borrar y volver a añadir el mapa.
  - Botón **`✕`** para quitar mapas individuales o **"Vaciar"** para reiniciar `pack.json`.
- **Cortador de nombre de dificultad:**
  - Permite elegir cuántas palabras del título conservar (**1 palabra**, **2 palabras**, **3 palabras** o **Completo**) con vista previa en vivo (`→ ...`) y opción para aplicarlo a todo el pack o solo a los mapas sin versión manual.
- **Generación segura y optimizada del pack:**
  - Limpieza automática de menciones de BPM y OD conservando rates (ej. `1.1x`, `0.95x`).
  - Diálogo interactivo de **parafraseo** si el nombre del archivo `.osu` supera los 160 caracteres seguros para osu!.
  - Truncado automático de `Tags:` (>850 caracteres) y `BeatmapID: 0`.
  - Conversión y redimensionado de imágenes de fondo a JPEG optimizado (máx. `1920x1080`, calidad `85`) con Pillow y renombrado sin colisiones para audios e imágenes.
  - Persistencia atómica en `pack.json` para evitar corrupción de datos.

---

## Instalación y uso

### 1. Clonar e instalar dependencias
```powershell
git clone https://github.com/dnxlll/osu-beatmap-pack-builder.git
cd osu-beatmap-pack-builder

python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Ejecutar la aplicación
```powershell
python main.py
```

### 3. Flujo básico dentro de la app
1. **Carpeta Base (`init_file`):** busca o examina la carpeta destino donde se generará el pack y selecciona el `.osu` base.
2. **Buscar y Añadir Mapas:** busca canciones en `Songs`, elige la dificultad `.osu`, asigna el patrón y haz clic en **"+ Añadir Dificultad al Pack"**.
3. **Cortador de Nombre (opcional):** ajusta si quieres 1, 2, 3 palabras o el título completo.
4. **Generar Pack:** pulsa **"⚡ Generar Pack de Mapas Final"** para copiar audios, optimizar fondos y crear los archivos `.osu` adaptados en la carpeta base.

---

## Estructura del proyecto

```text
osu_pack_builder/
├── domain/          # Reglas puras (modelos, limpieza BPM/OD, parsing y generación de .osu)
├── application/     # Casos de uso (añadir, editar, eliminar y generar pack)
├── infrastructure/  # Persistencia atómica (pack.json), Pillow y escáner de Songs
└── ui/              # Interfaz gráfica en CustomTkinter (componentes, diálogos y tema)
main.py              # Composition root y punto de entrada
tests/               # Suite de pruebas unitarias y de integración (pytest)
```

---

## Desarrollo y pruebas

```powershell
pip install -r requirements-dev.txt
pytest -v
ruff check .
lint-imports
```

---

## Licencia

Este proyecto está bajo la licencia **GNU GPL v3.0** — consulta el archivo [LICENSE](LICENSE) para más detalles.
