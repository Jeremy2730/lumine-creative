# Auditoría: conservación de tamaño y resolución (17-nov-2026)

Alcance: Lumine completo, sin Tk ni rembg real (sandbox). Todo lo marcado **WINDOWS** requiere tu máquina.

## 1. Cómo se representa hoy la imagen (preguntas 1–4, 9)
| Aspecto | Dónde / cómo |
|---|---|
| Imagen principal | `ProcessingState.current`: un `PIL.Image` RGBA (`core/models/processing_state.py`); toda carga se convierte a RGBA (`tools/image_loader.py`). No hay otro modelo de documento con tamaño/PPI. |
| Píxeles | `image.size` (ancho × alto). |
| PPI | `image.info["dpi"]` (par horizontal, vertical). El guardado lo escribe (`ImageLoader._prepare`) y la interfaz lo lee (`ImageSnapshot.dpi`, solo el horizontal). |
| Perfil de color | `image.info["icc_profile"]` (los no‑RGB se descartan al cargar). |
| Tamaño físico | **No se guarda: se deriva** (px / PPI × 2,54). Si se conservan píxeles y PPI, el tamaño físico se conserva; no puede quedar incoherente. |
| Tamaño y resolución | Con remuestreo cambia píxeles **y** metadatos; sin remuestreo cambia **solo** `info["dpi"]` (`tools/size_resolution/core.py`). Escribe un PPI cuadrado. |
| Entrada/salida de una herramienta | Todas pasan por `ImagePipeline.run` (única ruta: `preview`, `apply`, `run_pipeline`) y se confirman con `DesignEngine.commit`. Remove usa `run_preview` + `commit_preview`: la **misma** ruta. |

## 2. Qué pasa en Remove (preguntas 5–8)
`BackgroundRemover` codifica la imagen a PNG, rembg devuelve un PNG **nuevo** (sin PPI ni perfil), se decodifica y **se traspasan `dpi` e `icc_profile` de la entrada** (`_PRESERVED_INFO`). El resultado se confirma tal cual en el documento. No hay archivos temporales ni NumPy en esa ruta. Se exige que el resultado tenga el tamaño de la entrada.

## 3. Dónde se pierde realmente (ejecutado)
Recorrido con el código real (rembg sustituido por un devolutor de PNG nuevo, como rembg): abrir 800×600 @150 → Tamaño y resolución 30×40 cm @300 → Remove → Nitidez → Semitono.

| Paso | Tamaño | PPI |
|---|---|---|
| Tamaño y resolución | 3543 × 4724 | 300 |
| Remove (preview y commit) | 3543 × 4724 | 300 ✔ |
| Nitidez | 3543 × 4724 | 300 ✔ |
| **Semitono** | 3543 × 4724 | **ninguno (perdido)** |

- **Semitono pierde PPI e ICC**: `Image.fromarray` (NumPy) crea una imagen sin `info` (`tools/comic_effect.py:46`). Es el único punto de pérdida que he podido **reproducir**.
- **Remove NO pierde el PPI en mi ejecución.** No he podido reproducir tu síntoma con Remove (rembg real no está instalado aquí). Hipótesis que no puedo descartar sin tu equipo: una diferencia con el rembg real, o que el efecto observado viniera de otra herramienta de la cadena. Por eso añadí un **registro de diagnóstico** (ver §5): si en tu Windows alguna herramienta devuelve una imagen sin PPI, quedará en el log («La operación '…' no conservó dpi…»).
- **Debilidad de diseño (la causa de fondo):** la conservación dependía de que **cada herramienta** se acordara de traspasar los metadatos (Remove sí lo hacía; Semitono no; una herramienta futura tampoco tendría por qué). No había contrato ni nada que lo hiciera cumplir.
- **Redondeo inherente al PNG (no es un fallo de Lumine):** un PNG guarda el PPI como píxeles por metro (entero). Al **cargar** un PNG de 300 PPI sale 299,9994 (y 150 → 150,0124); tras Tamaño y resolución vuelve a ser exactamente 300. Las pruebas de guardar/cargar admiten ese redondeo y nada más.
- `ImageSnapshot.dpi` y el diálogo de Tamaño y resolución usan solo el PPI horizontal y ofrecen un 72 de reserva (marcado como «no fiable») cuando la imagen no trae PPI. Es solo para cálculos de la interfaz; no se escribe en la imagen. No se tocó.

## 4. Qué está bien diseñado / qué cambia / qué se reutiliza
- **Bien:** una única ruta de ejecución (`ImagePipeline`); `commit` atómico; Remove, Nitidez y Tamaño y resolución ya traspasaban los metadatos; el guardado ya escribe PPI e ICC; el tamaño físico es derivado.
- **Cambia:** el contrato no existía. **Se reutiliza** `ImagePipeline` y `ImageOperation` (sin crear un modelo de documento nuevo: sería una refactorización sin justificar).
- **Fuente de verdad (decisión):** `image.info` de la imagen del documento, con la **política en `ImagePipeline`**, el único sitio por el que pasan todas las herramientas. Un modelo de documento aparte (con ancho/alto/PPI propios) duplicaría lo que ya está en la imagen y abriría la posibilidad de que diverjan; lo dejo anotado para cuando exista documento multiobjeto.

## 5. Solución global (implementada)
1. `core/image_metadata.py` (nuevo): qué se protege (`dpi`, `icc_profile`) y `restore_metadata`. Nunca inventa valores: si la entrada no tenía PPI, la salida tampoco (se retira un 72/96 puesto por la herramienta).
2. `core/operation.py`: contrato con dos declaraciones, `changes_geometry` y `changes_resolution` (ambas `False` por omisión).
3. `core/image_pipeline.py`: tras **cada** operación: (a) si cambia el tamaño en píxeles sin declararlo → `ProcessingError` claro y el documento no cambia; (b) si no declara `changes_resolution` → restituye PPI e ICC de la entrada; (c) registra en el log (INFO) cuando una herramienta no los conservó.
4. `tools/size_resolution/core.py`: declara ambas excepciones (única herramienta que hoy cambia píxeles y PPI a propósito).
- **Remove no se modificó** (su traspaso propio queda redundante pero inocuo). **No se editó `comic_effect.py`**.

### Efecto en Semitono (hay que saberlo)
Semitono **no se modificó**, pero ahora sale del pipeline con el PPI y el perfil de la entrada, porque la política es global. Es el comportamiento correcto según la regla que pides, y lo que se pidió en la fase de Semitono pendiente (P1-2) queda cubierto sin tocar su archivo. Si prefieres que Semitono se trate aparte, basta con que declare `changes_resolution = True` (decisión tuya).

## 6. Herramientas afectadas
| Herramienta | Antes | Ahora |
|---|---|---|
| Remove | conservaba (por su cuenta) | conservado por contrato |
| Nitidez | conservaba (Pillow lo propaga en `filter`) | por contrato |
| Semitono | **perdía PPI e ICC** | conservado por contrato |
| Tamaño y resolución | cambia a propósito | igual, declarado |
| Futuras (ruido, mejora, recorte…) | dependían de acordarse | cubiertas por defecto; las que cambien píxeles deben declararlo |

## 7. Pruebas (`tests/test_metadata_preservation.py`, 30 pruebas, sin Tk ni rembg)
Comparan antes y después (tamaño, PPI x/y, tamaño físico, ICC): Remove a 300 y 150 PPI; PPI distinto en horizontal y vertical; transparencia previa; 5 tamaños y proporciones; el caso 30×40 cm @300; herramientas que crean imágenes nuevas con Pillow/NumPy/PNG en bytes o que fijan 72/96; metadatos nunca inventados; ninguna herramienta rutinaria restablece el PPI (Remove, Nitidez, Semitono); cadena de herramientas; guardar y volver a cargar (PNG y JPG); Tamaño y resolución sigue cambiando píxeles y PPI (con y sin remuestreo) y conserva el ICC; el contrato de tamaño en píxeles; registro de diagnóstico.
Mutaciones: sin la restitución fallan 8 pruebas (incluida la de Semitono); sin la comprobación de tamaño fallan 2.

## 8. Ejecutado / pendiente
- **Ejecutado aquí:** suite `702 passed, 4 skipped, 5 errors` (los mismos 5 módulos que necesitan `customtkinter`); importación con Tk simulado OK.
- **Pendiente en Windows:** con rembg real, repetir tu caso (Tamaño y resolución → Remove → OK → reabrir Tamaño y resolución) y mirar el log si el PPI no se conserva.
- **No considero resuelto el problema hasta tu comprobación.**
