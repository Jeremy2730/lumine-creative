# Tamaño y resolución

Herramienta inspirada en el cuadro "Tamaño de imagen" de Photoshop (sin ser un clon): fija el tamaño físico y la resolución de la imagen, con o sin remuestreo real de píxeles.

## Archivos

| Archivo | Responsabilidad |
|---|---|
| `core.py` | El algoritmo: `SizeResolutionAdjuster` (una `ImageOperation`) y las fórmulas puras cm↔px↔DPI/proporción. No conoce GUI ni unidades de interfaz. |
| `controller.py` | `SizeResolutionController`: valida, calcula la vista previa y traduce unidades de interfaz (mm/in/px, px/cm) hacia/desde la referencia interna (cm, PPI). Envuelve al `DesignController` genérico para validar y despachar. |
| `dialog.py` | `SizeResolutionDialog`: la ventana (CustomTkinter), estilo Photoshop — cada campo con su desplegable de unidad al lado. No contiene ningún cálculo propio; todo pasa por `controller`. |
| `__init__.py` | Expone `SizeResolutionAdjuster`, `SizeResolutionController` y las funciones de `core.py`. **No** reexporta `dialog.py`, para que importar este paquete nunca exija CustomTkinter (se importa aparte: `from tools.size_resolution.dialog import SizeResolutionDialog`). |

## Referencia interna

Toda la lógica trabaja siempre en **centímetros** y **PPI**, sin importar qué unidad esté viendo el usuario en pantalla. Las unidades de interfaz son una capa de presentación que convierte justo antes de calcular y justo después de mostrar — nunca se acumula una conversión sobre otra.

## Unidades disponibles en el diálogo

- **Medida** (ancho/alto, un solo selector sincronizado entre los dos campos): Centímetros (predeterminado), Milímetros, Pulgadas, Píxeles.
- **Resolución**: PPI — píxeles por pulgada (predeterminado), px/cm.

La conversión px↔cm de la medida usa la resolución (PPI) vigente en ese momento; la de PPI↔px/cm es `px/cm = PPI / 2.54`.

## Remuestrear: ON vs OFF

- **ON** (remuestrea de verdad): ancho, alto y resolución son independientes entre sí. Al aplicar, se recalculan los píxeles con `Image.resize` (método LANCZOS por defecto; también BICUBIC, BILINEAR, NEAREST) y se actualiza el DPI guardado.
- **OFF** (solo metadatos): los píxeles de la imagen **no cambian**. Editar ancho/alto recalcula la resolución efectiva manteniendo el píxel fijo; editar la resolución recalcula ancho/alto. Por eso "Mantener proporción" se deshabilita en este modo — no hay margen para deformar sin tocar píxeles.

"Mantener proporción" (con remuestrear activado) usa la proporción de **píxeles de la imagen original**, no una cadena de conversiones entre unidades, para evitar arrastrar error de redondeo.

## Transparencia y DPI al guardar

La imagen conserva su modo (RGBA incluido) en ambos modos de remuestreo. Al guardar, el DPI efectivo se escribe en los metadatos del PNG (vía el parámetro `dpi=` de Pillow, no solo `image.info`), así vuelve a leerse correctamente si se reabre el archivo.

## Usarla sin la GUI

```python
from tools.size_resolution import SizeResolutionAdjuster

# Con remuestreo: cambia los píxeles de verdad.
op = SizeResolutionAdjuster(width_cm=10, height_cm=15, dpi=300, resample=True)
nueva_imagen = op.apply(imagen)

# Sin remuestreo: solo actualiza el DPI guardado; los píxeles no cambian.
op = SizeResolutionAdjuster(width_cm=10, height_cm=15, dpi=150, resample=False)
```

## Limitación conocida

Si después de aplicar "Tamaño y resolución" se aplica "Quitar fondo" o "Semitono", el DPI configurado se pierde: esas dos herramientas regeneran los píxeles desde cero (`rembg`, `numpy`) y no conservan los metadatos de la imagen. No es un bug de esta herramienta — es el orden del pipeline. Si el DPI importa, aplica "Tamaño y resolución" **después** de fondo/semitono, no antes.

## Tests

`tests/test_size_resolution.py` (algoritmo y conversiones puras), `tests/test_size_resolution_dialog.py` y `tests/test_size_resolution_dialog_dpi.py` (diálogo, requieren un display — se auto-saltan sin uno; correr con `xvfb-run` para ejecutarlos de verdad en un servidor sin pantalla).
