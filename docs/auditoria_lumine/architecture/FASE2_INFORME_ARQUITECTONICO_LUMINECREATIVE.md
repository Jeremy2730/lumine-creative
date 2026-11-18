# FASE 2 — Informe arquitectónico de LumineCreative

**Naturaleza:** investigación y diseño. No se modificó ni creó nada en el proyecto. No se ejecutó ninguna prueba de Lumine (aquí no hay Tk); la línea base conocida sigue siendo **791 passed, 4 skipped, 0 failed** en tu Windows.
**Código leído:** `luminecreative/` (el mismo estado de la Fase 1) y `photocraft-main/`.
**Cambio de dirección incorporado:** la *Actualización de continuidad arquitectónica* del 16-nov-2026 sustituye el requisito de "visor único". Este informe parte de ella (ver §0).

**Etiquetas:** `HECHO` comprobado en código o documento (con ruta y línea) · `HIPÓTESIS` inferido, no comprobado · `RECOMENDACIÓN` mi propuesta, no aprobada · `DECISIÓN PENDIENTE` la tomas tú.

---

## 0. Qué cambió y qué consecuencia tiene

| Antes (brief de Fase 2) | Ahora (actualización) | Efecto en este informe |
|---|---|---|
| Un único `ImagePanel`/`ViewportModel`/`ViewportRenderer` | Visor principal + visor especializado de la herramienta; modelo documental compartido | P11 se replantea: ya no es "cómo fusionar dos visores" sino "cómo justificar dos y evitar inconsistencias" |
| Remove integrada en la ventana única | Remove puede usar espacio de trabajo propio; Lumine queda abierto y en "pausa visual" | **El diseño actual (Toplevel modal + visor propio) ya coincide con la dirección aprobada** |
| Reescritura posible | No hay reescritura ni migración prematura | El plan es evolutivo |

**HECHO (importante):** `RemoveDialog` ya es una ventana propia (`tools/remove/dialog.py:119`), con visor propio (`:148`), modal (`:143`, `:311`), mientras `MainWindow` sigue abierta con su documento intacto. Es decir, la actualización **no exige reconstruir nada**: exige formalizar lo que ya existe y cerrar sus cabos.

**HECHO:** la actualización **no autoriza implementar**. Este informe sigue siendo solo diseño.

**HIPÓTESIS sobre "pausa visual":** puede significar (a) la ventana principal queda visible pero inerte (como hoy), (b) oscurecida con una capa (como hace PhotoCraft, §2.3) o (c) oculta. **DECISIÓN PENDIENTE D1** (ver §7, P1).

---

## 1. Resumen de la arquitectura actual

(Detalle completo en `FASE1_AUDITORIA_LUMINECREATIVE.md`; aquí solo lo necesario.)

- **HECHO:** capas GUI → controladores → servicios → motor; vistas por `Protocol` (`RemoveView`, `DesignView`, `FileView`).
- **HECHO:** una raíz Tk (`MainWindow`, `gui/main_window.py:82`) y dos `CTkToplevel` (Remove `tools/remove/dialog.py:119`, Tamaño y resolución `tools/size_resolution/dialog.py:51`).
- **HECHO:** dos instancias de `ImagePanel` hoy (principal `main_window.py:111`; Remove `dialog.py:148`), cada una con su modelo y su renderizador.
- **HECHO:** el documento vive en el motor (`DesignEngine._state: ProcessingState`, `core/design_engine.py:64`), no en la GUI.
- **HECHO:** dos caminos de aplicación de herramientas:
  1. **Aplicar directo** (`DesignController.run_tool`): Semitono, Nitidez, Tamaño y resolución. Internamente `DesignEngine.apply` = `preview` + `commit` seguidos (`design_engine.py:79-83`, `118-134`).
  2. **Previsualizar y confirmar** (`run_preview` `design_controller.py:209`, `commit_preview` `:191`): **solo Remove**.
- **HECHO (hallazgo menor):** `DesignController.remove_background()` (`design_controller.py:188-189`) sigue existiendo y aplica RMBG **directo** (`run_tool`), sin vista previa. El menú **no** lo usa (`main_window.py:142` → `_on_remove`). Es un camino heredado que evita preview/commit; conviene decidir si se conserva (**D11**).

---

## 2. Estudio de PhotoCraft

**Alcance:** leí `docs/architecture.md` (§4, §5, §6, §11), `docs/ui-design.md`, `crates/ui-egui/src/camera_raw_ui.rs` (partes citadas), `canvas.rs`, `workspace_ui.rs`, `Cargo.toml` y el listado de `crates/`. **No** leí el motor completo ni el compositor. **VectorCraft llegó después de redactar el borrador; lo estudié en §2.4** (modelo de documento, nodos, herramientas, README/ROADMAP/CLAUDE.md), no su renderizado ni el motor completo.

### 2.1 Respuestas a los 10 puntos

| # | Punto | Qué hace PhotoCraft | Estado |
|---|---|---|---|
| 1 | Ventana principal | Una ventana eframe/egui (`Cargo.toml`: `eframe 0.36`). Dibuja ella misma su barra de título en Windows/Linux (`docs/ui-design.md`). Cerrar = Archivo ▸ Salir | HECHO (doc) |
| 2 | Espacios de trabajo | Paneles acoplados en la misma ventana (Layers, History, Properties…) alimentados por *view-models* leídos de un snapshot (`architecture.md` §4.5) | HECHO (doc); implementación no leída |
| 3 | Herramientas especializadas | **Dos modos coexisten:** diálogos in-window (`egui::Window`) y, para las pesadas, **una ventana de sistema propia**: Camera Raw `ViewportBuilder … with_inner_size([1360, 900])`, `camera_raw_ui.rs:853` | **HECHO (código)** |
| 4 | Cambio general ↔ herramienta | Camera Raw es **modal**: la ventana principal se oscurece con una capa (`scrim`, `camera_raw_ui.rs:845-851`) y no recibe entrada mientras está abierta. La herramienta se abre con `show_viewport_immediate` (`:855`) | **HECHO (código)** |
| 5 | Visor | Camera Raw **no reutiliza el visor del documento**: trabaja sobre un *proxy CPU de la capa* de ≤900 px (`PROXY_SIDE = 900`, `camera_raw_ui.rs:25`, cabecera `:4-6`) y tiene su propio estado de navegación (`CameraRawPreviewState`, `state.rs:50`, con su propio `zoom`) | **HECHO (código)** |
| 6 | Estado visual | El del lienzo principal es independiente del de Camera Raw (estructuras distintas: `View` `state.rs:378` vs `CameraRawPreviewState` `state.rs:50`) | HECHO |
| 7 | Imágenes y datos | `Document` con árbol de capas; píxeles en `TiledSurface` de teselas 256×256 con `Arc` y copia-al-escribir (`architecture.md` §5) | HECHO (doc) |
| 8 | Entrega del resultado | OK ejecuta un **comando con id de capa**: `app.run("filter.cameraRaw", p)` con `p["layer"] = d.layer.0` (`camera_raw_ui.rs:718-726`). El resultado es **un paso de historial** (cabecera `:4-6`), reproducible | **HECHO (código)** |
| 9 | Contexto del documento | `LayerId(u64)` y `DocId(u64)` estables (`crates/doc/src/lib.rs:59,74`); el diálogo guarda `layer: LayerId` (`camera_raw_ui.rs:30`). Los lectores usan snapshots `Arc<DocSnapshot>` sin bloqueo (`architecture.md` §4.1, §6) | HECHO (doc) + HECHO (código del `LayerId`) |
| 10 | Patrones aprovechables | Ver §2.3 | RECOMENDACIÓN |

### 2.2 Lo que PhotoCraft hace de verdad y lo que solo dice

| Afirmación | Estado |
|---|---|
| Camera Raw: ventana propia, modal, con capa oscura | **HECHO (código)** `camera_raw_ui.rs:845-862` |
| Cerrar esa ventana con la X **cancela** | **HECHO (código)** `:856-863` (`close_requested()` → `cancel(app)`) |
| OK aplica por id de capa y crea un paso de historial | **HECHO (código)** `:718-726` y cabecera |
| Existe un crate `photocraft-viewport` independiente del toolkit (`architecture.md` §4.4) | **La documentación lo describe, pero no existe `crates/viewport/`** (el listado de `crates/` no lo incluye). La cámara y la vista están en `ui-egui` (`canvas.rs:545 ViewXform`, `gpu_canvas.rs:52 ViewParams`, `state.rs:378 View`). **HECHO:** doc y código divergen en este punto. (Además `crates/vector/` contiene solo un `Cargo.toml` en esta copia.) |
| "Un trabajo que quedó obsoleto se *rebasa* sobre el mismo id de capa" (`architecture.md` §6) | No encontré `rebase` en `crates/engine/src/*.rs` (no revisé subcarpetas). **HIPÓTESIS:** es diseño declarado, no comprobado |
| Cancelación cooperativa con `CancelToken` en cada trabajo (§11) | Diseño declarado. Lumine **ya lo cita y lo descarta**: `core/progress.py:14-16` ("La cancelación cooperativa de ese diseño NO se implementa aquí") |

### 2.3 Qué conviene adaptar y qué no copiar

**Adaptar (RECOMENDACIÓN):**
1. **Identidad por id estable** del objeto y entrega del resultado como "comando con id" (no "reemplaza la imagen actual").
2. Herramienta pesada = **ventana propia + vista previa propia sobre un proxy**, con OK/Cancelar, y con **la X equivalente a Cancelar**.
3. Capa oscura sobre la ventana principal mientras la herramienta es modal (resuelve D1 sin ocultar nada).
4. Separar *view-model* (lo que se pinta) de *documento* (lo que se guarda).

**No copiar:**
- El modo inmediato de egui, el stack Rust/wgpu ni la documentación como si fuera el código (hay divergencias, §2.2).
- Teselado y GPU: es una escala de documento (PSD de gigapíxeles) que Lumine no tiene hoy.
- Historial de transacciones con `Arc` de teselas: depende de teselado.

**Lo que PhotoCraft confirma para tu nueva dirección:** una aplicación seria **sí** usa visor general + visor especializado, con la herramienta pesada en ventana propia. No hace falta un visor único. (HECHO, `camera_raw_ui.rs`).

### 2.4 Estudio de VectorCraft

**Alcance real:** leí `README.md`, `CLAUDE.md`, `ROADMAP.md` (cabecera), `docs/control-protocol.md` (cabecera), `crates/doc/src/lib.rs` y `node.rs` (partes citadas), `crates/tools/src/lib.rs` (cabecera y `Action`), y el listado de `crates/`. **No** leí el renderizador, el motor completo, los importadores ni el motor de texto.

| Aspecto | Qué hace VectorCraft | Estado |
|---|---|---|
| Qué es | Reimplementación *clean-room* de un editor vectorial, en Rust puro, escritorio y WebAssembly, licencia `MIT OR Apache-2.0` | HECHO (`README.md`, `CLAUDE.md`) |
| Madurez declarada | "Infraestructura ~90 %"; paridad funcional ~69-75 % **autoevaluada** por sus agentes; ellos mismos piden tratar las cifras como cotas superiores | HECHO (`ROADMAP.md:9-31`). No verificado de forma independiente |
| **Identidad de objeto** | `NodeId(pub u64)`: "Stable per-document object id. **Never reused.**" | **HECHO (código)** `crates/doc/src/node.rs:17-19` |
| **Árbol del documento** | `Document` con `artboards: Vec<Artboard>` y `layers: Vec<Arc<Node>>` (árbol persistente: los hijos son `Arc<Node>`) | **HECHO (código)** `crates/doc/src/lib.rs:525`, `340` (`Artboard`), cabecera `:3-4` |
| **Tipos de objeto** | `NodeKind`: `Layer`, `Group`, `Path`, `Compound`, `Text`, `Image`, `SymbolInstance`, `Blend`, `Envelope`… (variantes vivas como efectos "en vivo") | **HECHO (código)** `node.rs:344-…` |
| **Imagen como objeto** | `ImageObject { key, width, height, xf: Affine, link, placement }`. Los **píxeles no están en el nodo**: están en `Document.images: BTreeMap<String, ImageBlob>` por clave. `xf` mapea el espacio de píxeles al documento (posición, escala, rotación) | **HECHO (código)** `node.rs:326-340`; `lib.rs` campo `images` |
| Mesa de trabajo | Varias `Artboard` con `rect` en puntos del documento | HECHO `lib.rs:340-348` |
| **Herramientas** | "Los tools nunca mutan el documento directamente": emiten `Action::Begin / Preview / Commit / Cancel`; `Begin` hace snapshot, cada `Preview` se reaplica sobre ese snapshot **reemplazando el anterior**, `Commit` registra **un solo paso de deshacer**, `Cancel` restaura el snapshot | **HECHO (código)** `crates/tools/src/lib.rs:1-6`, `Action` `:134-142` |
| "Todo es un comando" | Comportamiento visible = comando en `crates/engine/src/cmd/*`; la interfaz es "delgada" y actúa vía `app.run(id, params)` | HECHO (`CLAUDE.md`) |
| Robustez | Sin `unwrap/panic` en producción (lints de clippy); `guard` captura pánicos y **revierte el documento** | HECHO (`CLAUDE.md`) |
| Canal de control / MCP | Puerto loopback JSON-lines (`--control`), servidor MCP; permite capturas de pantalla y ejecutar comandos | HECHO (`docs/control-protocol.md`, `CLAUDE.md`) |
| Efectos | Los efectos "en vivo" (envelope, blend…) viven **en el árbol** como nodos con su especificación (parámetros), no como píxeles ya cocinados | HECHO (`node.rs`, variantes `Blend`/`Envelope`) |

**Lo que VectorCraft aporta al problema de Remove (lo más relevante):**
1. **Modelo de objeto ya resuelto en el mismo lenguaje de diseño que queremos:** `NodeId` estable + `xf` de posición/escala/rotación + píxeles aparte por clave. Es casi exactamente el `DocObject` de §4.2, con una diferencia clave: **los píxeles no viven dentro del objeto**.
2. **Patrón *Begin/Preview/Commit/Cancel*:** es el mismo que Lumine ya tiene (`DesignEngine.preview`/`commit` + `PreviewResult`) pero generalizado a toda interacción. Valida que la dirección de `preview/commit` es correcta.
3. **Preview que reemplaza al anterior sobre un snapshot fijo:** equivalente al `base_revision` de Lumine, pero con una diferencia: aquí no se invalida por cambios ajenos porque el snapshot es del documento *entero* y se restaura entero.

**Diferencias a no ignorar (HECHO):**
- VectorCraft es un editor **vectorial**: no tiene un flujo de "herramienta de imagen con ventana propia" como Remove. Para eso la referencia relevante es **Camera Raw de PhotoCraft** (§2.1).
- No hay una noción de *visor especializado* en lo leído; no puedo afirmar nada sobre cómo trata imágenes grandes más allá de `ImageBlob`/`proxy` (el `proxy` de un enlace es una vista previa de baja resolución para guardar, `lib.rs`, campo `proxy`).

**Código reutilizable, bibliotecas, patrones e inspiración (RECOMENDACIÓN, sin evaluar a fondo):**

| Categoría | Candidatos | Por qué |
|---|---|---|
| **Patrón arquitectónico** (adoptar) | id estable que nunca se reutiliza; transformación separada del píxel; píxeles por clave; `Begin/Preview/Commit/Cancel` | Encaja con Lumine y no exige Rust |
| **Código reutilizable directamente** | **Ninguno en Python.** Son crates Rust; usarlos exigiría un puente (p. ej. extensión nativa) | HECHO: no hay Python en ninguno de los dos repos |
| **Biblioteca candidata (si algún día hay Rust parcial)** | `pathops` (operaciones booleanas de trazados), `geom`, `trace` (raster→vector), `text`, `render` | **HIPÓTESIS:** no evalué calidad, API ni dependencias; solo vi los nombres en `crates/` |
| **Solo inspiración** | Paridad con un editor comercial, canal MCP/control, XTask de CI | No aplica ahora |
| **No copiar** | La política *clean-room*, `ASSETS.md`, la marca ArtCraft (`docs/brand/` es marca registrada, no open source) | HECHO (`CLAUDE.md`) |

**Licencia (HECHO):** ambos repos incluyen `LICENSE-MIT` y `LICENSE-APACHE` y `NOTICE`; el código es `MIT OR Apache-2.0`. Reutilizar código exigiría conservar sus avisos. **No soy asesor legal**; si se llegara a incorporar código, conviene que lo revises tú.

---

## 3. Análisis del almacenamiento de datos de Lumine

### 3.1 Dónde vive cada dato (A)

| Pregunta | Respuesta | Evidencia |
|---|---|---|
| ¿Dónde está la imagen original? | **En ningún sitio, una vez confirmada una operación.** En disco está el archivo de origen (`DocumentState.origin_path`). En memoria solo hay **una** imagen de trabajo: `ProcessingState.current` | `processing_state.py:87`, `106` (`commit` hace `self.current = image`) |
| ¿Dónde está la procesada? | La misma: `current`. No hay pila de versiones | `processing_state.py:13` ("Pensado para Deshacer… bastaría con guardar aquí una pila") |
| ¿Qué contiene `ProcessingState`? | `source_path`, `current` (PIL), `operations: list[AppliedOperation]`, `status`, `revision: int` | `processing_state.py:83-90` |
| ¿Qué es `AppliedOperation`? | Solo `name` y `label` (texto). **No guarda parámetros**: el historial son etiquetas | `processing_state.py:39-43` |
| ¿Qué contiene `DocumentState`? | **Ficha del archivo**: `display_name`, `origin_path`, `save_path`, `save_format`, `saved_operations`. No guarda píxeles | `document_state.py:41-47` |
| ¿Qué mantiene `DesignEngine`? | El único `ProcessingState` y el puerto de E/S. Sabe de `preview`/`commit` | `design_engine.py:62-64`, `85-116` |
| ¿Qué conserva `DesignController`? | La compuerta de tareas (`run_task`), `InteractionState`, el runner y la vista. **No guarda la imagen**: la pide al servicio (`current_snapshot`, `:205`) | `design_controller.py:191-207` |
| ¿Quién guarda cada `DocumentState`? | `FileController` | Fase 1 §5 |

### 3.2 Referencias frente a copias

| Caso | ¿Copia? | Evidencia |
|---|---|---|
| `snapshot()` | **Referencia**: `ImageSnapshot(image=self.current)` | `processing_state.py:113-114` |
| `ImagePanel.show` / `ViewportRenderer.set_image` | **Referencia**; el renderizador solo lee y construye niveles reducidos propios | `image_panel.py:225-237`, `viewport_renderer.py:118-125` |
| Remove guarda la original | **Referencia** (`self._original = snapshot.image`) | `remove/controller.py:179` |
| Contrato de `ImageOperation.apply` | Devuelve **una imagen nueva**; no debe mutar la entrada | `core/operation.py:106-107` |
| Tamaño y resolución sin remuestrear | Copia explícita (`image.copy()`) | `size_resolution/core.py:123` |
| Guardar a JPG con alfa | Copia compuesta sobre blanco; la de trabajo no se toca | `image_loader.py:75-77`, `file_service.py:123-125` |

**HECHO:** con dos visores no se duplica la imagen: ambos apuntan al **mismo objeto PIL**. Lo único que cada visor duplica es su **pirámide de niveles reducidos** (`ViewportRenderer._levels`). **HIPÓTESIS:** el coste de memoria de una segunda pirámide es modesto, pero no lo medí (R4 de la Fase 1).

### 3.3 Dimensiones, resolución y transparencia

- **Dimensiones:** solo en píxeles, implícitas en la imagen (`ImageSnapshot.size`, `processing_state.py:56-57`). El tamaño físico se **deriva** con `core/units.py` (cm↔px según DPI). No existe "dimensión del objeto en el documento" porque el documento *es* la imagen.
- **Resolución:** metadato dentro de la propia imagen, `image.info["dpi"]` (`processing_state.py:60-65`; escrita por `size_resolution/core.py:125`; usada al guardar `image_loader.py:185-186`).
- **Transparencia:** **toda imagen se carga como RGBA** (`image_loader.py:150`, `.convert("RGBA")` tras aplicar EXIF). Se guarda PNG con alfa o JPG aplanado (`has_transparency`, `image_loader.py:65`).
- **Perfil ICC:** se conserva si es RGB; si no, se descarta (`image_loader.py` tras `:150`).

### 3.4 Qué se conserva y qué se pierde en una operación (comprobado)

Ejecuté las herramientas reales en el sandbox (Pillow 12.3.0) con una imagen que traía `dpi` e `icc_profile`:

| Herramienta | `dpi` | `icc_profile` | Evidencia |
|---|---|---|---|
| Nitidez (`ImageSharpener`) | ✅ conserva | ✅ conserva | prueba ejecutada; `image.filter()` copia `info` |
| Quitar fondo | ✅ | ✅ | `background_remover.py:69, 275-277` (se traspasan expresamente) |
| Tamaño y resolución | ✅ (y fija `dpi`) | ✅ (copia `info`) | `size_resolution/core.py:123-125` |
| **Semitono (`ComicEffect`)** | ❌ **pierde** | ❌ **pierde** | **prueba ejecutada: `info == {}`**. Causa: `Image.fromarray(...)` (`comic_effect.py:46`) crea una imagen sin `info` |

**HECHO (hallazgo nuevo):** **Semitono hoy descarta el DPI y el perfil ICC.** No hay prueba que lo detecte: `grep` de `dpi`, `info` e `icc` en `tests/test_comic_effect.py` no devuelve nada. Es un fallo de conservación de metadatos **independiente de esta fase**. **RECOMENDACIÓN:** registrarlo como pendiente; no tocarlo ahora.

**HECHO:** el motor no tiene contrato que *obligue* a una herramienta a conservar metadatos; cada una lo hace (o no) por su cuenta.

### 3.5 Revisión del documento y obsolescencia

- **HECHO:** `ProcessingState.revision` es **un entero global**; sube con cada `load` y `commit` (`processing_state.py:102,108`). `PreviewResult.base_revision` lo recuerda; `DesignEngine.commit` lanza `StalePreviewError` si no coincide (`design_engine.py:112-113`).
- **Consecuencia para varios objetos (HIPÓTESIS razonada):** con una revisión global, **cualquier** cambio en otro objeto invalidaría la previsualización de Remove. Contradice "los demás objetos no deben afectar". Se necesitaría revisión **por objeto** (§4).

---

## 4. Propuesta de modelo documental futuro

**RECOMENDACIÓN, no implementar, no aprobada.** Principio: **evolucionar, no reescribir** (D. de dirección §1).

### 4.1 Qué es hoy cada pieza, y en qué se convertiría

| Hoy | Equivale a | Evolución propuesta |
|---|---|---|
| `ProcessingState` (`current`, `revision`, `operations`) | Un documento con **un solo objeto raster** | Pasa a ser el contenido de un `RasterObject` dentro de un `Document` |
| `DocumentState` | Ficha del archivo de origen/guardado | Se mantiene como metadatos del *proyecto*; el guardado de imagen única sigue siendo un caso |
| `DesignEngine` (`preview`/`commit`) | Motor de un objeto | Se mantiene; `commit` recibe un **objetivo** (id) |
| `PreviewResult(base_revision, image, applied)` | Resultado pendiente | Añade `target_id` y la revisión **del objeto** |
| `ImageSnapshot` | Vista inmutable de la imagen | Pasa a ser la vista inmutable de **un objeto** (y otra del documento) |

### 4.2 Modelo conceptual (diagrama, no código)

```
Document
 ├─ id, nombre, unidades, mesa de trabajo (tamaño), revisión_estructura
 ├─ objects: lista ordenada (orden de apilado = organización)
 │    └─ DocObject  ← base común
 │         ├─ object_id          (estable, nunca se reutiliza)
 │         ├─ kind               (raster | vector | text | shape)
 │         ├─ name, visible, locked
 │         ├─ transform          (x, y, escala, rotación, en unidades del documento)
 │         ├─ revision           (sube solo cuando cambia ESTE objeto)
 │         └─ effects[]          (parámetros, no solo etiquetas)
 └─ selection: object_id | None
```

| Tipo | Contenido específico | Notas |
|---|---|---|
| Imagen (raster) | píxeles RGBA (PIL), `dpi`, `icc`, tamaño px | Es lo que hoy ya existe (§3) |
| Vector | geometría (nodos, curvas), relleno, contorno | **No existe nada hoy** |
| Texto | contenido, fuente, tamaño, runs, formato | **No existe nada hoy** |
| Forma | geometría, dimensiones, relleno, contorno | **No existe nada hoy** |
| Efectos | nombre + **parámetros** + referencia al objeto | Hoy son destructivos: solo `name/label` en el historial |
| Transformaciones | posición, escala, rotación | Hoy no existen; el documento es la imagen |

**Apoyo de VectorCraft para este diseño (HECHO, §2.4):** `NodeId` estable y nunca reutilizado (`node.rs:17-19`), posición/escala/rotación en una transformación `xf` aparte del píxel (`node.rs:326-340`) y píxeles en un almacén por clave (`Document.images`). PhotoCraft aporta `LayerId` estable (`crates/doc/src/lib.rs:59`) y la entrega por id (`camera_raw_ui.rs:718-726`). Ambos confirman la forma de §4.2; **no** confirman que Lumine deba llegar ahí de golpe.

### 4.3 Qué se aprovecha del proyecto actual (HECHO) y qué falta (HECHO)

**Aprovechable sin cambios:** `ImageOperation` (imagen→imagen), `ImagePipeline` atómico, `preview`/`commit` con rechazo de obsoletos, `InteractionState`/`Scope`, `BackgroundTaskRunner`, `units.py`, `ImageLoader`, y la pareja `ViewportModel`/`ViewportRenderer`.

**Falta (no existe hoy):** `object_id`, revisión por objeto, transformaciones, parámetros de efectos persistidos, más de un objeto, y deshacer/rehacer (`processing_state.py:13` lo deja anotado como idea).

### 4.4 Decisiones que este modelo deja abiertas

- **D2.** ¿Efectos **destructivos** (como hoy) o **no destructivos** (parámetros que se reaplican)? Cambia profundamente el modelo y el coste de memoria.
- **D3.** Al confirmar una herramienta que **cambia el tamaño en píxeles** (p. ej. Tamaño y resolución), ¿se mantiene el tamaño físico del objeto en el documento (se reescala la transformación) o cambia?
- **D4.** ¿Remove debe **exigir** que el resultado conserve el tamaño? Hoy sí lo valida (`background_remover.py:281`).

### 4.5 Relación documento ↔ visor (C)

**RECOMENDACIÓN:**
- El **documento** guarda datos y propiedades; **no** guarda zoom, paneo ni área visible.
- Cada **visor** guarda solo estado visual. HECHO hoy: `ViewportModel` guarda `zoom`, posición, `fit_mode` y tamaños (`viewport.py:164-192`); ninguno es dato del motor.
- "Enfocar un objeto" = que **el visor especializado reciba una referencia de solo lectura** al objeto; **no** se cambia el documento ni el visor principal.
- "Regresar a la composición" es **gratis** con dos visores: el principal nunca dejó de mostrarla.

---

## 5. Arquitectura de visores (con dos visores)

### 5.1 Principio

**RECOMENDACIÓN:** dos visores **justificados por función**:

| Visor | Función | Opciones |
|---|---|---|
| Principal | Componer y revisar el documento completo | por omisión: sin `fit_min_zoom`, sin tablero |
| Especializado (Remove, Halftone, Mejorador…) | Ver **un objeto** con su vista previa, comparar y confirmar | `fit_min_zoom=True`, tablero de transparencia (ya existen, `image_panel.py:145-153`) |

### 5.2 Qué comparten y qué no (HECHO hoy)

| Compartido (código y datos) | No compartido (estado visual) |
|---|---|
| Clases `ImagePanel`, `ViewportModel`, `ViewportRenderer`, `viewport_interaction` | Instancia de modelo (zoom, posición, ajuste) |
| **El mismo objeto PIL** (referencia) | Instancia de renderizador (pirámide, tablero) |
| `InteractionState` (permisos) | Tamaño del área, barras, botones |

### 5.3 Reglas para evitar inconsistencias (RECOMENDACIÓN)

1. **Ningún visor es dueño de píxeles.** Ambos leen la referencia del documento.
2. **Solo el documento cambia datos.** Un visor nunca llama a `commit`.
3. **El visor especializado nunca escribe en el principal.** Al confirmar, Lumine actualiza el documento y **luego** refresca el visor principal.
4. **La decisión de conservar el encuadre debe salir de la identidad** (mismo `object_id`, revisión +1), no de la heurística actual `_continues_document` (`main_window.py:68-79`), que compara `source_path` y la cantidad de operaciones.
5. **Un visor por cada herramienta abierta, destruido al cerrar** (ya es así).

### 5.4 Si algún día se quisiera un único visor (referencia, ya no requerido)

HECHO (por qué sería costoso): `ViewportModel` recibe sus opciones **solo en el constructor** (`viewport.py:164-192`; `_model_options` se usa solo en el primer `show`, `image_panel.py:225-235`); el renderizador guarda **un único `_source`** (`viewport_renderer.py:118`); `set_image_size` sin `keep_view` reinicia el ajuste (`viewport.py:315-336`); y **no existe API para guardar/restaurar el estado de la vista**. Habría que añadir un perfil mutable y `capture_view()/restore_view()`. **No se recomienda ahora.**

---

## 6. Flujo completo Lumine → Remove → Lumine

Hoy sin objetos (HECHO), y cómo sería con identidad (RECOMENDACIÓN).

```
HOY                                              CON IDENTIDAD DE OBJETO (propuesto)
Menú ▸ Quitar fondo                              Menú ▸ Quitar fondo (con objeto raster seleccionado)
 RemoveController.open()   controller.py:166      ToolSession.open(target = object_id)
   snapshot = current_snapshot()                    ref = document.get(object_id)        (solo lectura)
   enter_workspace("remove_background")             enter_workspace(...)  [bloquea Scope.MAIN]
   _original = snapshot.image   (referencia)        base_object_revision = ref.revision
 RemoveDialog(...)  visor propio                  Ventana de Remove, visor propio
 [Quitar fondo] → run_preview(sink=controller)    ídem; el resultado pendiente vive en la sesión
   hilo → PreviewResult(base_revision global)       PreviewResult(target_id, base_object_revision)
 [OK] → commit_preview                            [OK] → document.replace_raster(object_id, result,
   → engine.commit (rechaza si revision global      expected_revision)  → comprueba: existe, es raster,
     cambió)                                        misma revisión; conserva transform/nombre/orden
   → MainWindow.show_snapshot (keep_view por       → solo ESE objeto cambia; revisión del objeto +1
     heurística)                                    → visor principal se refresca por id
   → _close → leave_workspace                       → cerrar ventana → leave_workspace
 [Cancelar] → descarta, _close                    [Cancelar] → descarta; el documento no se tocó
```

**Garantías que ya se cumplen hoy (HECHO):** el resultado pendiente no toca el documento (`design_engine.py:91-101`); `commit` rechaza obsoletos (`:112-113`); `leave_workspace` va en `finally` (`controller.py:298-311`); un resultado tardío no puede aplicarse (`can_ok`, `:144-146`).

**Garantías que hoy no pueden existir (HECHO):** "actualizar solo el objeto B" y "conservar posición/organización" — no hay objetos.

---

## 7. Respuestas razonadas a P1–P12

> Las respuestas parten de la dirección de la actualización. Cuando una decisión es tuya, aparece como **DECISIÓN PENDIENTE**.

### P1 — ¿Ocultar la vista principal o conservarla?
- **Problema:** qué pasa con la ventana principal mientras se usa Remove.
- **Lumine hoy (HECHO):** la conserva visible y la bloquea por política (`Scope.MAIN`, `interaction.py:157-165`; `_refresh_controls`, `main_window.py:260-270`); Remove es un `Toplevel` modal.
- **PhotoCraft (HECHO):** conserva la principal y la **oscurece** con una capa mientras la herramienta es modal (`camera_raw_ui.rs:845-851`).
- **Opciones:** A) Toplevel modal sobre la principal visible (actual); B) A + capa/atenuación visual; C) cambiar de vista dentro de la misma ventana (plan original); D) ocultar la principal.
- **Ventajas/desventajas:** A: ya existe y está probado; elimina el riesgo de tamaño de lienzo oculto (R2 de la Fase 1). B: casi igual, pero "pausa visual" explícita; en Tk no hay transparencia por widget (`CTkToplevel` no la da por widget; habría que usar `-alpha` del toplevel o un marco opaco — **HIPÓTESIS**, no probado). C: más trabajo y riesgos de foco/atajos/tamaño. D: peor continuidad, parpadeo.
- **RECOMENDACIÓN:** **A ahora**; B solo si quieres la "pausa visual" literal. No hacer C mientras no haga falta.
- **DECISIÓN PENDIENTE D1:** ¿"pausa visual" = inerte (A) o atenuada (B)?
- **Archivos:** `gui/main_window.py` (solo si B), `tools/remove/dialog.py`.
- **Riesgos:** B: no hay forma comprobada en CustomTkinter de atenuar la ventana principal con fiabilidad en Windows (HIPÓTESIS).
- **Cómo comprobar:** prueba GUI real en Windows (§10, G1-G3).

### P2 — Menú y atajos durante Remove
- **Hoy (HECHO):** el menú se deshabilita por política (`main_window.py:265-269`); los atajos se enlazan a la raíz con `bind`, no `bind_all` (`menu_bar.py`, docstring).
- **HIPÓTESIS (conocimiento de Tk, no comprobada aquí):** un widget del `Toplevel` tiene como *bindtag* a su toplevel, no a la raíz, así que Ctrl+O/S no llegan a la raíz; y aunque llegaran, `can(OPEN_IMAGE)` es falso con un espacio abierto (`interaction.py:162-163`).
- **Opciones:** mantener; añadir atajos propios de Remove (Enter = OK, Esc = Cancelar).
- **RECOMENDACIÓN:** mantener, y **comprobarlo con una prueba GUI real** antes de darlo por cierto.
- **DECISIÓN PENDIENTE D5:** ¿Enter/Esc en Remove? (no está en el alcance pedido).
- **Archivos:** ninguno si se mantiene.
- **Comprobar:** G6.

### P3 — ¿Quién es propietario de la sesión Remove?
- **Hoy (HECHO):** `MainWindow` guarda `_remove` y `_remove_dialog` (`main_window.py:99-100, 235`); `_remove_dialog` no se limpia al cerrar (hallazgo A6). `InteractionState.enter_workspace` ya impide dos espacios a la vez (`interaction.py:191-197`).
- **Opciones:** (a) dejar en `MainWindow`; (b) un anfitrión de herramientas Tk-free (`ToolHost`) que guarde la sesión activa; (c) el documento.
- **RECOMENDACIÓN:** (a) ahora, **limpiando la referencia al cerrar**. (b) cuando exista una **segunda** herramienta de imagen con el mismo patrón (tu paso 3: "consolidar Remove como patrón"), no antes: abstraer con un solo caso suele salir mal.
- **Riesgo:** (b) prematuro.
- **Archivos:** `main_window.py` (limpiar `_remove_dialog`).
- **Comprobar:** prueba de que, tras Cancelar/OK, `ui.win._remove_dialog is None` (hoy no se cumple; ningún test lo exige).

### P4 — Comportamiento de la X
- **Hoy (HECHO):** la X se **rechaza** con aviso (`dialog.py:177` → `refuse_close`; `controller.py:236`) y en Windows se oculta con `ctypes` (`dialog.py:317-333`, `_hide_close_button`).
- **PhotoCraft (HECHO):** la X **cancela** (`camera_raw_ui.rs:856-863`).
- **Opciones:** (a) rechazar (actual); (b) X = Cancelar; (c) X = pedir confirmación si hay resultado pendiente.
- **Ventajas:** (b) es lo que esperaría el usuario; elimina el truco de `windll`. (a) evita cerrar por accidente pero es poco habitual. (c) añade un diálogo.
- **RECOMENDACIÓN:** (b) si hay resultado pendiente o no; con tarea en curso aplicar P5. Es un cambio de comportamiento y obliga a reescribir `test_closing_the_window_with_the_system_button_is_refused`.
- **DECISIÓN PENDIENTE D6:** (a) o (b).
- **Archivos:** `tools/remove/dialog.py`, `tools/remove/controller.py`, `gui/main_window.py` (`_on_close`), `tests/test_remove_dialog.py`.
- **Comprobar:** G10.

### P5 — Cerrar Remove mientras RMBG procesa
- **Hoy (HECHO):** Cancelar con tarea en curso solo **pide** descartar; la inferencia no se interrumpe y el resultado se descarta al llegar (`controller.py:224-234`, `_discard :290`). El diálogo queda abierto hasta entonces. No hay cancelación cooperativa (`core/progress.py:14-16`).
- **Opciones:** (a) mantener abierto hasta terminar (actual); (b) cerrar ya y descartar al llegar; (c) bloquear el cierre.
- **Análisis:** (b) exigiría que `FULL_LOCK` siga activo tras cerrar la ventana (el hilo sigue vivo y el runner admite una tarea a la vez), o dejaría la app bloqueada sin ventana visible.
- **RECOMENDACIÓN:** (a) por ahora. Es coherente y ya está probado.
- **Riesgo:** parecer "colgado" varios segundos. La barra ya informa.
- **Comprobar:** G9 (resultado tardío).

### P6 — Título, tamaño y propiedades de ventana
- **Hoy (HECHO):** título fijo "Quitar fondo", `geometry`, `minsize` y `transient` en `dialog.py:140-143`. La principal: título dinámico por `FileController.window_title` y `minsize(820, 640)` (`main_window.py:106`).
- **RECOMENDACIÓN:** conservar la ventana de Remove tal cual; **opcional** mostrar el nombre del objeto en el título ("Quitar fondo — nombre"), como hace PhotoCraft ("Camera Raw Filter (layer)", `camera_raw_ui.rs:868-873`). No tocar la ventana principal.
- **Archivos:** `tools/remove/dialog.py`.
- **Riesgo:** ninguno relevante.

### P7 — Cerrar una vista integrada sin destruir el visor compartido
- **Con la dirección aprobada ya no hay visor compartido que proteger.** Cerrar Remove destruye **su** visor; el principal no se toca. (HECHO: `RemoveDialog.destroy`, `dialog.py:335-345`.)
- **Cabo suelto (HECHO):** el `after` de preparación (`grab_set` diferido, `dialog.py:179`/`311`) no se cancela en `destroy` (termina en `if not self._alive: return`, `:308`).
- **RECOMENDACIÓN:** cancelar ese `after` en `destroy` (cambio mínimo, a hacer en la etapa de cierre de Remove).
- **Comprobar:** cerrar de inmediato tras abrir y verificar que no queda ningún callback pendiente.

### P8 — Barra de progreso
- **Hoy (HECHO):** vive **en Remove**, anclada con `place(in_=viewer.view_area)` sobre su propio canvas (`dialog.py:240-246`); `view_area` existe solo para esto (`image_panel.py:197`).
- **RECOMENDACIÓN:** mantener. Con visor propio la condición de Tk (el `in_` debe ser descendiente del maestro) se cumple. Cuando otra herramienta de imagen la necesite, extraer la barra (`wait_value`, `finish_value`, animación) a un componente común, junto con `STATUS_COLORS` (hallazgo A10).
- **Archivos hoy:** ninguno.

### P9 — ¿SizeResolutionDialog queda como está?
- **HECHO:** es otro `CTkToplevel` (`size_resolution/dialog.py:51`), **sin visor**, con política `LEGACY_LOCK` (`interaction.py:~113`) y aplica **directo** (`run_tool`, `size_resolution/controller.py:~139`), sin vista previa/confirmación.
- **Recomendación:** **sí, sin cambios en esta fase.** Es otro tipo de herramienta (paramétrica, sin vista previa de píxeles). Sí hay un punto a considerar después: al cambiar el tamaño en píxeles de un objeto, ver **D3** (§4.4).

### P10 — Foco y teclado
- **Hoy (HECHO):** `ImagePanel` toma el foco del canvas con `<Enter>` (`image_panel.py:~353`) y con clic izquierdo (`_on_left_press`); `grab_set` fija la entrada en Remove.
- **HIPÓTESIS:** con dos `Toplevel`/visores separados y modalidad no hay competencia por la barra espaciadora.
- **RECOMENDACIÓN:** mantener; **comprobar en Windows** que, tras cerrar Remove, el foco vuelve al canvas principal y que Espacio+arrastre funciona sin hacer clic (G6).

### P11 — "Un único visor" → dos visores justificados
- **Cambio:** el requisito deja de ser "una instancia"; es "no inconsistencias".
- **Procedimiento (RECOMENDACIÓN):**
  1. **Mantener dos instancias** de `ImagePanel` (ya existen).
  2. **Compartir clases, no estado** (ya ocurre).
  3. **Pasar el objeto por referencia** a ambos visores (ya ocurre); nunca copias.
  4. **Que el resultado pendiente solo lo vea el visor de la herramienta.**
  5. **Al confirmar, refrescar el principal por identidad** (§5.3.4).
  6. **Dar un nombre a "perfil de visor"** (opciones `fit_min_zoom`, tablero) en vez de parámetros sueltos: solo cuando haya un segundo consumidor (Halftone/Mejorador).
- **No hacer:** fusionar instancias ni añadir `capture_view/restore_view` ahora (§5.4).
- **Riesgos:** memoria de dos pirámides (no medida); divergencias si alguien añade lógica a un visor y no al otro (mitigación: ambos son la misma clase).
- **Comprobar:** G1, G4, G5 y una medición de memoria con imagen grande.

### P12 — Cómo demostrarlo con Tk real
Ver §10. Resumen: pruebas que **leen identidades y números** (id del visor, `zoom`, `position`, `image_size`, referencia de la imagen) antes y después de cada transición.

---

## 8. Responsabilidades de los componentes (RECOMENDACIÓN)

| Componente | Es dueño de | No debe |
|---|---|---|
| **Documento** (hoy `ProcessingState` vía motor) | Objetos, píxeles, propiedades, revisiones | Conocer visores ni ventanas |
| **Motor** (`DesignEngine`) | `preview` (sin tocar) y `commit` (con validación) | Saber qué herramienta es |
| **`DesignController`** | Compuerta de tareas, permisos | Guardar imágenes |
| **`InteractionState`** | Quién puede hacer qué (`MAIN`/`TOOL`) | Tkinter |
| **Sesión de herramienta** (hoy `RemoveController`) | Objetivo, resultado pendiente, estado de la sesión | Importar Tk |
| **Ventana de la herramienta** (`RemoveDialog`) | Presentación, botones, barra | Decidir reglas |
| **Visor** (`ImagePanel` + modelo + renderizador) | Estado visual | Modificar datos |
| **`MainWindow`** | Presentación del documento, menú, apertura de herramientas | Reglas de procesamiento |

---

## 9. Ciclo de vida de las sesiones

```
ABIERTA ──run──► PROCESANDO ──ok──► COMPLETADA ──OK──► CERRADA (commit)
   │                 │ │               │
   │                 │ └─error──► ERROR ├─Cancelar──► CERRADA (descarte)
   │                 └─Cancelar (pide) ► CANCELANDO ──llega resultado──► CANCELADA (descarta, sigue abierta)
   └─Cancelar──► CERRADA
```
(HECHO: estados reales `RemoveState` en `tools/remove/controller.py`; el diagrama es la lectura de `run/ok/cancel/_discard/_close`.)

**Invariantes (HECHO hoy):** `enter_workspace` al abrir y `leave_workspace` **siempre** al cerrar (`finally`); un resultado no se aplica más de una vez (`commit` rechaza revisión vieja); el hilo solo comunica por cola.
**Invariantes nuevos propuestos:** la sesión conoce su `object_id`; `commit` valida identidad y revisión **del objeto**.

---

## 10. Plan de pruebas (diseño; **nada de esto se ejecutó**)

Línea base: **791 passed, 4 skipped, 0 failed** (Windows, Fase 0).

### 10.1 Qué tipo de prueba demuestra qué

| Tipo | Corre sin ventana | Cubre |
|---|---|---|
| **Unitarias** | Sí | Reglas puras: revisión por objeto, `StalePreviewError`, estados de sesión, `ViewportModel` |
| **Integración** | Sí (con dobles) | `RemoveController` + `DesignController` + motor: cancelar, tardío, error, OK |
| **GUI real (Tk en Windows)** | **No** | Identidad de widgets, foco, atajos, redimensionado, minimizar/maximizar, X, barra |

### 10.2 Pruebas GUI reales (G) — lo que `pytest` con Tk debe afirmar

| # | Prueba | Cómo se demuestra (valores concretos) |
|---|---|---|
| G1 | **Identidad de visores** | `id(main._image_panel)` no cambia tras abrir y cerrar Remove; `dialog._viewer is not main._image_panel` |
| G2 | Lumine → Remove | El visor principal sigue con su `winfo_ismapped()` verdadero y `viewport.image_size` igual; `can(OPEN_IMAGE)` falso |
| G3 | Remove → Lumine | `leave_workspace`; menú rehabilitado; el visor principal responde a zoom |
| G4 | **Conservación del zoom/paneo** | Zoom manual (p. ej. 2.5×) + paneo → abrir/OK/cerrar → `viewport.zoom`, `position` y `fit_mode` iguales (tolerancia declarada) |
| G5 | **Dimensiones** | `image_size` antes = después con Remove (conserva tamaño); `viewport_size` coherente con `winfo_width/height` |
| G6 | Foco y atajos | Con Remove abierto: `event_generate("<Control-o>")` no abre diálogo; al cerrar, `focus_get()` está en el canvas principal; Espacio + arrastre funciona |
| G7 | Redimensionar | Cambiar tamaño de la ventana principal y de Remove: sin excepciones; el modelo ajusta `viewport_size` tras 80 ms |
| G8 | Minimizar/maximizar/restaurar | `iconify`/`deiconify`/`state("zoomed")` con Remove abierto: sigue `transient`, sin perder el `grab` (**HIPÓTESIS:** comportamiento de Windows no comprobado) |
| G9 | Barra / asíncrono / **resultado tardío** | Cancelar durante el procesamiento: la barra se oculta, no queda `after` vivo, el resultado no se aplica |
| G10 | **X** | Según D6: rechazada o equivalente a Cancelar; el documento no cambia |
| G11 | **Confirmación** | OK → `snapshot.image is not original` y `operations` crece en 1 |
| G12 | **Cancelación** | Cancelar → `snapshot.image is original` (misma referencia) |

### 10.3 Pruebas para el modelo con objetos (solo cuando exista; hoy no son posibles)

| Prueba | Afirmación |
|---|---|
| Conservación de objetos no seleccionados | Para cada `object_id ≠ objetivo`: misma referencia de píxeles y misma revisión |
| Actualización exclusiva del objeto procesado | Solo cambia el objetivo; su `transform`, `name` y orden se mantienen |
| Revisión por objeto | Un cambio en B no invalida un resultado pendiente sobre A |
| Objeto eliminado durante el procesamiento | `commit` lo rechaza con error claro |
| Recuperación del documento completo | El visor principal vuelve a la composición sin cambios de estado visual |

### 10.4 Lo que NO puedo afirmar
Nada de §10 se ejecutó. Los resultados reales solo salen de tu Windows. **Hoy no existe** ninguna prueba para: conservación de zoom tras OK, atajos con Remove abierto, ni `_remove_dialog is None` tras cerrar.

---

## 11. Riesgos y dependencias

| Id | Riesgo | Estado |
|---|---|---|
| K1 | **Perder metadatos** (DPI/ICC) en herramientas — **ya ocurre con Semitono** | HECHO |
| K2 | Revisión **global** impide aislar objetos | HECHO (diseño actual) |
| K3 | "Pausa visual" mal entendida (D1) | DECISIÓN PENDIENTE |
| K4 | X: cambiar de rechazo a Cancelar rompe pruebas existentes | HECHO (`test_remove_dialog.py`) |
| K5 | Memoria de dos pirámides | HIPÓTESIS, sin medir |
| K6 | Atajos y foco con dos ventanas | HIPÓTESIS, sin comprobar |
| K7 | Atenuar la ventana principal en CustomTkinter | HIPÓTESIS, sin comprobar |
| K8 | Abstraer demasiado pronto (`ToolHost`) | RECOMENDACIÓN de no hacerlo |
| K9 | Ruta Rust/otro framework: sin necesidad concreta identificada | Estudiar, no iniciar |
| K10 | VectorCraft estudiado solo en su modelo de documento y herramientas (§2.4); renderizado, texto y motor sin leer | HECHO (alcance limitado) |
| **Dependencias** | Pillow (info/ICC), `rembg` + ONNX, Tk real en Windows para G1-G12 | — |

### Sobre la ruta tecnológica (puntos 5 de la actualización)
- **HECHO:** nada en esta fase obliga a Rust ni a otro framework. Los cuellos de botella detectados son **de modelo** (objetos, revisión, metadatos), no de lenguaje.
- **HIPÓTESIS:** los límites de Python/CustomTkinter aparecerán con documentos grandes, vectores con muchos nodos o composición en tiempo real. **No medido.**
- **Qué podría migrarse a Rust por partes (HIPÓTESIS):** renderizado de composición, rasterizado de vectores y operaciones pesadas (vía extensión Python); la GUI y el modelo no. **No evaluado todavía**: corresponde a tu paso 6.

---

## 12. Plan de implementación por etapas (RECOMENDACIÓN, **no aprobado**)

Alineado con tu orden vigente. Cada etapa se entrega y se revisa antes de la siguiente.

| Etapa | Objetivo | Tipo de cambio |
|---|---|---|
| **E1. Cerrar Remove** (tu paso 1) | Resolver los cabos de §7 que **tú** decidas: D6 (X), limpiar `_remove_dialog` (P3), cancelar el `after` en `destroy` (P7), título (P6) | Pequeño, localizado |
| **E2. Validar conservación** (tu paso 2) | Escribir y ejecutar G1-G12 en Windows. Sin tocar producción | Solo pruebas |
| **E3. Remove como patrón** (tu paso 3) | Con una **segunda** herramienta de imagen, extraer lo común (sesión, barra, perfil de visor). Revisión por objeto como pre-requisito | Refactor guiado por 2 casos |
| **E4. Modelo documental mínimo** (tu paso 5) | `object_id` y revisión por objeto con **un** objeto; sin cambiar la GUI | Pequeño, compatible |
| **E5. Estudio PhotoCraft/VectorCraft** (tu paso 4) | Completar (VectorCraft, motor) | Investigación |
| **E6. Rust y GUI** (tu paso 6) | Medir antes de decidir | Investigación |
| **E7. Actualizar arquitectura** (tu paso 7) | Documento final | Documentación |

> Observación sobre el orden: tu paso 4 (estudiar PhotoCraft/VectorCraft) viene después del 3, pero **la forma de la identidad de objeto** (E4) condiciona E3. **DECISIÓN PENDIENTE D7:** ¿adelantar E4 antes de E3?

---

## 13. Archivos que se modificarían en cada etapa (si se aprueba)

| Etapa | Archivos (rutas dentro de `luminecreative/`) |
|---|---|
| E1 | `tools/remove/dialog.py`, `tools/remove/controller.py`, `gui/main_window.py`, `tests/test_remove_dialog.py`, `tests/test_file_menu_gui.py` |
| E2 | **Nuevos** archivos en `tests/` (p. ej. pruebas GUI de Remove); ningún archivo de producción |
| E3 | `tools/remove/*`, `gui/components/` (barra común), `gui/panels/status_panel.py` (`STATUS_COLORS`), `app/controllers/design_controller.py` |
| E4 | `core/models/processing_state.py`, `core/design_engine.py`, `app/services/processing_service.py`, `app/services/document_state.py`, tests asociados |
| E5-E7 | Solo documentación en `docs/` |

No tocar en ninguna etapa: `gui/`, `tools/` y `tests/` **de la raíz** (respaldos).

---

## 14. Criterios de aceptación (propuestos)

**Para cerrar la dirección actual (E1-E2):**
1. Con Remove abierto, el documento y el visor principal conservan identidad, `image_size`, `zoom`, `position` y `fit_mode` tras OK y tras Cancelar (G1, G4, G5).
2. Cancelar deja `snapshot.image` con la **misma referencia** que antes (G12).
3. OK actualiza solo la imagen y suma exactamente una operación (G11).
4. Cualquier cierre (OK, Cancelar, X según D6) ejecuta `leave_workspace` y rehabilita el menú (G3).
5. Un resultado tardío tras cerrar no modifica el documento ni deja `after` vivos (G9).
6. Con Remove abierto, los atajos de la principal no actúan y, al cerrar, el foco vuelve al visor principal (G6).
7. La suite completa mantiene **791 passed, 4 skipped, 0 failed** más las pruebas nuevas, **ejecutada en Windows y reportada con sus números reales**.

**Para el modelo con objetos (E4+):**
8. Cada objeto tiene `object_id` estable y `revision` propia.
9. Confirmar sobre el objeto B no cambia referencia ni revisión de ningún otro.
10. Un `PreviewResult` sobre B no se invalida por cambios en A.
11. El objetivo eliminado o cambiado de forma incompatible hace que `commit` falle sin modificar nada.

---

## 15. Decisiones pendientes (resumen)

| Id | Decisión | Mi inclinación |
|---|---|---|
| D1 | "Pausa visual": ¿inerte o atenuada? | Inerte (como hoy) |
| D2 | Efectos destructivos o no destructivos | Destructivos hasta tener varios objetos; reevaluar |
| D3 | Cambio de tamaño en px de un objeto: ¿se conserva el tamaño físico? | Sin recomendación firme |
| D4 | ¿Remove exige conservar tamaño? | Sí (ya lo valida) |
| D5 | Enter/Esc en Remove | Opcional |
| D6 | X de Remove: rechazar o Cancelar | Cancelar (como PhotoCraft) |
| D7 | ¿Adelantar E4 (identidad de objeto) a E3? | Sí |
| D8 | Semitono pierde DPI/ICC: ¿cuándo se corrige? | Anotarlo; no mezclarlo con esta fase |
| D9 | VectorCraft: ¿profundizo en su renderizado, texto y operaciones de trazados (`pathops`, `trace`) en la etapa E5? | Sí, solo cuando se aborde el modelo vectorial |
| D11 | ¿Se conserva `DesignController.remove_background()` (camino directo heredado, sin preview)? | Decidir en E1; no lo uso para nada más |
| D10 | Píxeles dentro del objeto (como hoy) o por clave aparte (como VectorCraft `Document.images`) | Por clave aparte si algún día hay varios objetos con la misma imagen; hoy no hace falta |

---

*Fin del informe. No se modificó código, no se crearon archivos en el proyecto y no se ejecutó ninguna prueba de Lumine. Todo lo marcado HIPÓTESIS requiere verificación en Windows con Tk real.*