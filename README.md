# Herramienta para Diseño

Aplicación de escritorio (CustomTkinter) para preparar imágenes para impresión DTF: **quitar fondo**, **semitono** (efecto cómic), **tamaño y resolución** (cm/mm/pulgadas/píxeles y PPI, con o sin remuestreo) y **dar nitidez**. Los procesos se acumulan sobre la imagen actual, en el orden en que los apliques. Se abre y se guarda en **PNG y JPG/JPEG** desde el menú **Archivos**.

## Requisitos

- Python 3.10 – 3.13 (con Tkinter; en Linux: `sudo apt install python3-tk`)
- Dependencias en `requirements.txt` (versiones fijadas). La primera vez que se quita un fondo, `rembg` descarga su modelo (~170 MB).

## Instalación

```bash
python -m venv .venv
# Windows:      .venv\Scripts\activate
# Linux / macOS: source .venv/bin/activate
pip install -r requirements.txt
```

## Ejecución

```bash
python main.py
```

## Archivos: abrir y guardar

Todo está en el menú **Archivos** (y en sus atajos). Ya no hay botones grandes de abrir/guardar.

| Acción | Atajo | Qué hace |
|---|---|---|
| Abrir… | `Ctrl+O` | Abre una imagen PNG o JPG/JPEG. |
| Guardar | `Ctrl+S` | Escribe en el destino del documento; si aún no tiene, equivale a Guardar como. |
| Guardar como… | `Ctrl+Mayús+S` | Siempre pregunta ruta, nombre y formato (PNG o JPG). |
| Salir | — | Cierra la aplicación (igual que la X de la ventana). |

El menú **Herramientas** es el único acceso a las herramientas (Quitar fondo, Semitono, Tamaño y resolución…, Dar nitidez): la ventana ya no tiene botones por herramienta y esa área la ocupa la imagen. Debajo de la imagen solo queda el historial de procesos aplicados. El título de la ventana muestra el documento actual y un `*` si tiene cambios sin guardar.

**Abrir**
- Se corrige la orientación EXIF antes de convertir a RGBA (una foto de celular se abre ya girada correctamente).
- Si el archivo no se puede abrir, se muestra un error y se conserva el documento actual.
- El cargador sigue aceptando `.webp`, `.bmp` y `.tiff` porque ya los abría antes de esta versión; no se añadió ningún formato nuevo ni se garantiza su guardado (solo se guarda PNG y JPG).

**Guardar y Guardar como**
- **El archivo original nunca se sobrescribe en silencio**: un archivo recién abierto no tiene destino, así que el primer Guardar abre Guardar como (nombre sugerido `<original>_editada.<ext>` en la carpeta del original, sin pisar archivos existentes).
- El formato lo decide la extensión elegida (`.png` → PNG; `.jpg`/`.jpeg` → JPEG). Una extensión no admitida se rechaza sin escribir nada.
- Si cancelas un diálogo, o si guardar falla, el documento no se marca como guardado y su destino no cambia.
- La escritura es atómica: se escribe un archivo temporal en la misma carpeta y solo al terminar bien sustituye al destino. Un fallo no deja un archivo final a medias ni daña uno existente.

**Transparencia**
- PNG conserva el canal alfa. La imagen de trabajo siempre conserva su transparencia.
- JPG no admite transparencia. Si la imagen tiene píxeles transparentes (se comprueba el canal alfa, no solo el modo de color), la aplicación pregunta si quieres aplanarla sobre fondo blanco. Si aceptas, se guarda una **copia** compuesta sobre blanco; si cancelas, no se escribe nada.
- El formato sugerido en Guardar como es PNG si hay transparencia real; si no, el del último guardado o el del archivo de origen.

**Calidad y metadatos**
- Calidad JPG explícita de 95 (`Settings.jpg_quality`; el valor por defecto de Pillow es 75).
- Se conservan el DPI y el perfil ICC cuando es posible. Solo se conservan perfiles **RGB**: tras convertir a RGBA, un perfil CMYK o de grises ya no describiría los colores, y se descarta.
- **No se conservan** el resto de metadatos del original (EXIF, XMP, comentarios, miniaturas).
- En PNG el DPI se guarda como píxeles/metro y puede releerse con una deriva mínima (300 → 299.9994); en JPG es exacto.

**Cambios pendientes**
- Se compara la lista de operaciones aplicadas con la que había al abrir o guardar por última vez. Al abrir una imagen el documento queda limpio; al aplicar una herramienta, modificado; al guardar bien, limpio.
- Si abres otro archivo o cierras con cambios pendientes, se ofrece **Guardar**, **Descartar** o **Cancelar**. Si Guardar se cancela o falla, no se continúa con la apertura ni el cierre.
- No se cierra la aplicación mientras hay un proceso en curso (se avisa y hay que esperar).

## Quitar fondo y Semitono

Son dos herramientas independientes:

- **Quitar fondo:** solo `rembg`.
- **Semitono (cómic):** vuelve transparente el negro puro y mezcla una trama en relieve. No depende de `rembg` y se puede aplicar antes o después.

Los parámetros del semitono (`comic_black_threshold`, `comic_pattern_contrast`, `comic_blend_alpha`) están en `config/settings.py`.

## Tamaño y resolución

Herramienta propia con su documentación en [`tools/size_resolution/README.md`](tools/size_resolution/README.md). Con ella ya no existe una herramienta "Redimensionar" aparte.

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

- Las pruebas de lógica (cargador, servicios, controladores, herramientas) no necesitan pantalla ni `rembg`.
- Las pruebas de ventana (menú, atajos, título, cierre, diálogo de tamaño y resolución) necesitan un display: **sin él se omiten** (`skipped`). En un servidor sin pantalla: `xvfb-run -a pytest`.
- Resultado de referencia: 193 pasan con display; sin display, 166 pasan y 27 se omiten.
- Los diálogos nativos de archivo y de confirmación son modales y no se pueden automatizar: las pruebas los sustituyen por funciones falsas. Esa parte exige la prueba manual descrita más abajo.

## Usar el motor sin GUI

```python
from pathlib import Path
from app.application import build_processing_service

service = build_processing_service()
service.open_image(Path("foto.jpg"))
service.run_pipeline([
    ("remove_background", {}),
    ("comic_effect", {}),
    ("size_resolution", {"width_cm": 10, "height_cm": 15, "dpi": 300,
                         "resample": True, "method": "LANCZOS"}),
    ("sharpen", {}),
])
print(service.save_result())  # escribe un PNG "_editada" en Descargas (ruta heredada, sin documento)
```

Para guardar con las reglas de la aplicación (formato por extensión, aplanado de JPG, escritura atómica) usa `ImageLoader.save(image, ruta)` o `FileService.write`.

## Estructura

```
HerramientaDiseno/
├── main.py                     # arranca la app (nada más)
├── app/
│   ├── application.py          # raíz de composición: crea y conecta piezas
│   ├── controllers/
│   │   ├── design_controller.py   # herramientas + compuerta de tareas (run_task)
│   │   └── file_controller.py     # Abrir / Guardar / Guardar como / Salir, cambios pendientes
│   └── services/
│       ├── processing_service.py  # casos de uso: abrir, aplicar, pipeline
│       ├── file_service.py        # abrir y escribir archivos, sugerir destino y formato
│       ├── document_state.py      # ficha del documento: origen, destino, cambios pendientes
│       ├── tool_registry.py       # nombre -> fábrica de herramienta
│       └── task_runner.py         # ÚNICO lugar con threads
├── core/                       # motor genérico (sin GUI ni archivos)
├── tools/
│   ├── image_loader.py         # cargar (EXIF), guardar por formato real, aplanado, escritura atómica
│   ├── background_remover.py, comic_effect.py, image_sharpener.py
│   └── size_resolution/        # herramienta con core, controller y dialog propios
├── gui/
│   ├── main_window.py          # ventana: paneles, menú, atajos, título, cierre
│   ├── panels/                 # image_panel, tools_panel (historial de procesos), status_panel
│   └── components/             # buttons, dialogs (archivo y confirmación), menu_bar
├── config/                     # settings.py, logging_config.py
└── tests/
```

## Arquitectura

```
GUI ─► DesignController ─► ProcessingService ─► DesignEngine ─► ImagePipeline ─► Tools
GUI ─► FileController ───► FileService ───────► ProcessingService / ImageLoader
            └──── comparten la misma compuerta de tareas: DesignController.run_task ────┘
```

- **Una sola compuerta de tareas.** `DesignController.run_task` es la única exclusión de "ocupado" y el único runner: herramientas, abrir y guardar pasan por ahí y nunca se solapan. `FileController` no tiene hilo ni bandera propios.
- **Documento vs imagen.** `DocumentState` solo guarda metadatos del archivo (origen, destino, formato, operaciones vistas al guardar); la imagen de trabajo vive solo en el motor.
- **Diálogos.** `FileController` decide cuándo preguntar; la ventana solo muestra el diálogo (`FileView`). El hilo de trabajo nunca toca la GUI.
- **Sondeo resistente.** La ventana procesa los resultados de los hilos cada 50 ms y sigue haciéndolo aunque un callback lance una excepción.
- **Errores.** Las herramientas lanzan excepciones de `core/exceptions.py`; el controlador muestra un mensaje amigable y registra el detalle en `logs/herramienta_diseno.log`.

### Decisión: menú nativo

Se usa `tkinter.Menu` nativo. CustomTkinter 5.2.2 no trae widget de menú; la alternativa de terceros `CTkMenuBar` añadiría una dependencia, y una barra propia de botones perdería la navegación con teclado y el comportamiento estándar. Los colores del tema se aplican al menú; en Windows la barra superior es nativa y su aspecto lo decide el sistema (no verificado allí). Los atajos se enlazan con `bind` en la ventana principal (no `bind_all`), así que no se disparan desde un diálogo abierto.

## Cómo agregar una nueva herramienta

Ejemplo: **contraste**.

1. Crear `tools/image_contrast.py` con una `ImageOperation`:
   ```python
   from PIL import Image, ImageEnhance
   from core.operation import ImageOperation

   class ImageContrast(ImageOperation):
       name = "contrast"

       def __init__(self, factor: float = 1.2) -> None:
           self.factor = factor

       @property
       def label(self) -> str:
           return f"Contraste x{self.factor:g}"

       def apply(self, image: Image.Image) -> Image.Image:
           return ImageEnhance.Contrast(image).enhance(self.factor)
   ```
2. Registrarla en `build_tool_registry` (`app/application.py`): `registry.register("contrast", lambda factor=1.2: ImageContrast(factor))`.
3. Añadir su mensaje en `_TOOL_MESSAGES` y un método (`def contrast(self): self.run_tool("contrast")`) en `DesignController`.
4. Añadir su entrada en `MainWindow._build_menu` (el menú Herramientas es el único acceso; ya no hay un botón por herramienta).
5. Añadir un test en `tests/`.

El motor, el pipeline y las demás herramientas no cambian.

## Cómo agregar un proceso al pipeline

Un "proceso" es cualquier `ImageOperation`:

```python
from core.image_pipeline import ImagePipeline

pipeline = ImagePipeline([BackgroundRemover(), ImageSharpener()])
pipeline.add(ComicEffect())                 # agregar después
engine.run_pipeline(pipeline)               # o service.run_pipeline([...nombres...])
```

## Prueba manual (PNG/JPG)

Los diálogos nativos no se automatizan; esta secuencia cubre lo que las pruebas no pueden:

1. `python main.py`. Debe verse la barra **Archivos / Herramientas** y la ventana sin botones: la imagen (con todo el espacio posible), el historial de procesos y la barra de estado.
2. **Archivos ▸ Abrir… (`Ctrl+O`)** y elige un PNG o JPG. El título muestra `nombre — Herramienta para Diseño`, sin `*`.
3. Aplica **Herramientas ▸ Dar nitidez**. El título pasa a `nombre * — …` y aparece el proceso "Nitidez".
4. **Archivos ▸ Guardar (`Ctrl+S`)**: como es la primera vez se abre **Guardar como**, con el nombre sugerido `<original>_editada.<ext>`. Elige una ruta distinta del original y confirma. El título pierde el `*` y el original no cambia.
5. Aplica otra herramienta desde el menú **Herramientas** y pulsa `Ctrl+S`: guarda en el mismo archivo **sin preguntar**.
6. **Guardar como… (`Ctrl+Mayús+S`)**: elige otro nombre. Verifica que el título adopta el nuevo nombre. Repite cancelando el diálogo: no debe cambiar nada.
7. **Transparencia:** abre un PNG con zonas transparentes (o aplica *Quitar fondo*), elige **Guardar como** con extensión `.jpg`. Debe preguntar si aplanar sobre blanco. *Cancelar*: no escribe nada. *Aceptar*: el JPG tiene fondo blanco y la imagen en pantalla sigue transparente (guárdala como PNG para comprobarlo).
8. **Cambios pendientes:** con la imagen modificada y sin guardar, abre otro archivo y comprueba **Guardar / Descartar / Cancelar**; repite cerrando la ventana con la X.
9. Si falla el guardado (p. ej. carpeta de solo lectura), debe mostrarse un error y el documento seguir marcado con `*`.

## Pendiente / fuera de alcance de esta versión

- **PDF** (abrir y generar), Drag & Drop, exportaciones especializadas y formatos adicionales de guardado: no implementados.
- `DesignController.open_image` y `save` son código heredado que la interfaz ya no usa; siguen porque hay pruebas que dependen de ellos. Pendiente retirarlos al migrarlas.
- Deshacer/Rehacer: no existe; los cambios pendientes se detectan comparando operaciones, no con un historial.
