# INFORME DE AUDITORÍA — LUMINECREATIVE (16-nov-2026)

**Alcance:** auditoría del ZIP `luminecreative.zip` recibido el 16-nov-2026 contra la arquitectura vigente. El ZIP original se conservó intacto como referencia (`new/`) y todo cambio se hizo sobre una copia (`fixed/`).
**Semitono / Halftone: no se tocó ningún archivo, configuración, algoritmo ni prueba** (ver §9).
**Entorno:** sandbox Linux **sin `tkinter` ni `customtkinter`**. Nada que requiera Tk real pudo ejecutarse aquí. **El arranque real con `python main.py` NO está verificado**; es la primera prueba pendiente en tu Windows.

**Nota sobre líneas:** las referencias a `tools/remove/dialog.py` usan la numeración de la versión restaurada **antes** de P1-1; tras ese cambio, lo situado después de la línea 128 está desplazado +1.

Etiquetas: **HECHO** comprobado en código o en una ejecución aquí · **HIPÓTESIS** inferido, no ejecutado · **PENDIENTE WINDOWS** requiere Tk real.

---

## 1. Estado general

| Pregunta | Respuesta |
|---|---|
| ¿Por qué no iniciaba Lumine? | **HECHO.** `tools/remove/dialog.py` del ZIP es **byte a byte idéntico** a `tests/test_remove_dialog.py` (MD5 `e322d71a0e0d4428abe053e61549bd8e` en ambos). El archivo de pruebas se copió encima del de producción: no existe la clase `RemoveDialog`, de ahí `ImportError` en `gui/main_window.py:61` |
| ¿Se reprodujo? | **HECHO.** Con Tk simulado, importar `gui.main_window` sobre el ZIP original produce exactamente `ImportError: cannot import name 'RemoveDialog' from 'tools.remove.dialog'` en la línea 61 |
| ¿Está corregido? | **Corregido en el código; arranque real PENDIENTE WINDOWS.** Con el archivo restaurado, la importación con Tk simulado funciona (`gui.main_window`, `app.application`). Eso **no** demuestra que la ventana se cree |
| ¿La suite lo detectaba? | **No.** En el original: `640 passed, 4 skipped, 5 errors` (los 5 errores son módulos que necesitan Tk). Ninguna prueba ejecutable aquí importa el diálogo. Se añadió una prueba estática que lo detecta (§7) |
| ¿Cómo ocurrió? | **No puedo determinarlo.** Evidencia: `dialog.py` tiene fecha 15-nov 21:09, el resto de `tools/remove/` 11:09; el contenido es el de la prueba. Es compatible con una copia manual al destino equivocado. Una de mis entregas anteriores incluía ambos archivos con nombres parecidos, así que **no descarto una confusión de destino al instalarlos**; no tengo forma de verlo |
| Estado del resto | **HECHO.** `diff` contra la versión previa: solo difieren `dialog.py`, `test_remove_dialog.py` (solo el salto de línea final) y el log. Controlador, ventana principal, visor, motor y servicios son iguales |

---

## 2. Arquitectura encontrada

(Detalle en `FASE1_AUDITORIA_LUMINECREATIVE.md` y `FASE2_INFORME_ARQUITECTONICO_LUMINECREATIVE.md`.)

Capas: GUI (`gui/`) → controladores (`app/controllers/`, `tools/remove/controller.py`) → servicios (`app/services/`) → motor (`core/`) → herramientas (`tools/`). Vistas por `Protocol` (`RemoveView`, `DesignView`, `FileView`). Una raíz Tk (`MainWindow`, `gui/main_window.py:82`) y dos `CTkToplevel`: `RemoveDialog` y `SizeResolutionDialog`.

## 3. Comparación con la arquitectura vigente

| Regla vigente | Código | Estado |
|---|---|---|
| `MainWindow` es la ventana principal y raíz Tk | `class MainWindow(ctk.CTk)`, `main_window.py:82` | ✅ HECHO |
| Remove usa su propio `CTkToplevel` | `class RemoveDialog(ctk.CTkToplevel)`, `dialog.py:119` (restaurada) | ✅ HECHO (tras la corrección) |
| Remove tiene visor propio | `ImagePanel` propio en `dialog.py:148` | ✅ HECHO |
| Lumine conserva su visor principal | `ImagePanel` en `main_window.py:111` | ✅ HECHO |
| Dos visores independientes | dos instancias, cada una con su `ViewportModel` y `ViewportRenderer` | ✅ HECHO |
| Ventana principal abierta e inactiva durante Remove | `enter_workspace` + `_refresh_controls` (`interaction.py:191-203`, `main_window.py:260-270`) | ✅ HECHO (lectura); PENDIENTE WINDOWS |
| El documento pertenece a Lumine | `ProcessingState` en `DesignEngine` (`design_engine.py:64`) | ✅ HECHO |
| La previsualización no modifica el documento | `DesignEngine.preview` no toca el estado (`design_engine.py:91-101`) | ✅ HECHO |
| Confirmar actualiza el objetivo y rechaza obsoletos | `commit` + `StalePreviewError` (`design_engine.py:112-113`) | ✅ HECHO |
| Cancelar deja el documento intacto | solo `commit_preview` modifica; `cancel` no la llama | ✅ HECHO (lectura) |
| Sin visor único, sin ToolHost, sin multiobjeto | no existen | ✅ coherente |

---

## 4. Clasificación de componentes

### 4.1 ESTÁ BIEN
| Componente | Motivo (evidencia) |
|---|---|
| `RemoveController` (`tools/remove/controller.py`) | Sin Tk (`RemoveView` Protocol `:80-93`); cierre siempre libera el espacio de trabajo en `finally` (`_close`, `:298-311`); un resultado tardío o descartado no se aplica |
| `InteractionState` (`app/interaction.py`) | Lógica pura; políticas `FULL_LOCK`/`LEGACY_LOCK`; `enter/leave_workspace` |
| `DesignEngine.preview/commit` | `base_revision` + `StalePreviewError`; no toca el estado en `preview` |
| `BackgroundTaskRunner` + `_poll` | Un solo poller con `after` reprogramado en `finally` y detenido si `_closed` (`main_window.py:272-277`) |
| `ViewportModel` / `ViewportRenderer` | Geometría pura y píxeles separados; `set_image` reinicia la pirámide si la imagen es otra (`viewport_renderer.py:118-125`) |
| `ImagePanel` | Cancela sus `after` (`image_panel.py:364-378`) |
| Remove conserva DPI/ICC y valida el tamaño | `_PRESERVED_INFO` (`background_remover.py:274-278`), `result.size != image.size` (`:281`) |
| Barra de carga de Remove | Un solo `after`, cancelado al cerrar (`dialog.py:289-302`) |

### 4.2 NECESITA REVISIÓN (comprobación con Tk real o pruebas)
| Componente | Qué falta comprobar |
|---|---|
| Arranque real | **PENDIENTE WINDOWS:** `python main.py` y apertura de Remove |
| Conservación de zoom/paneo tras OK | `show_snapshot` decide `keep_view` con `_continues_document` (`main_window.py:68-79`, `168-175`). El modelo conserva zoom y centro relativo si no está en "ajustar" (`viewport.py:315-336`), pero **no hay prueba con Tk real** |
| `_continues_document` | Decide por `source_path` y número de operaciones, no por identidad del objeto. Funciona con un documento único; frágil a futuro |
| Atajos y foco con Remove abierto | Se asume que `bind` en la raíz no recibe teclas de un `Toplevel` (HIPÓTESIS de Tk); además `can()` las bloquea por política. Sin prueba |
| Modo de color | La carga convierte todo a RGBA (`image_loader.py:150`): se normaliza el modo (L/P/CMYK no se conservan) y el ICC solo si es RGB. Es una decisión de diseño, no un error, pero conviene confirmarla |
| Resolución de Remove | Lumine pasa la imagen completa a rembg sin reescalar y exige el mismo tamaño de salida. Cómo rembg redimensiona internamente **no lo inspeccioné** (HIPÓTESIS) |
| Memoria de dos pirámides | No medida |
| Pruebas de Tk simulado | `test_remove_dialog.py` usa `ctk.CTk()` real y se omite sin pantalla; no se ejecutó aquí |

### 4.3 NECESITA CAMBIOS
| Id | Componente | Estado |
|---|---|---|
| P0-1 | `tools/remove/dialog.py` sobrescrito | **CORREGIDO** |
| P1-1 | `after` diferido del diálogo (`_finish_window_setup`) no se cancelaba al destruir | **CORREGIDO** |
| P1-2 | Semitono pierde DPI/ICC | **NO INTERVENIDO por instrucción expresa** |
| P2-… | ver `PLAN_ARREGLOS_LUMINE.md` | pendientes |

### 4.4 SE PUEDE REUTILIZAR
| Componente | Para qué | Condición |
|---|---|---|
| `RemoveController` + `RemoveView` | Patrón de sesión para otras herramientas de imagen (mejorador, etc.) | Hacerlo cuando exista un **segundo** consumidor, no antes |
| `DesignController.run_preview(sink=…)` + `commit_preview` | Cualquier herramienta con vista previa y confirmación | El sumidero (`sink`) recibe estado y progreso |
| `InteractionState` (`Scope`, `enter/leave_workspace`) | Bloqueo de lo principal para cualquier herramienta modal | Registrar una política en `TOOL_POLICIES` |
| `ImagePanel` / `ViewportModel` / `ViewportRenderer` | Visor de cualquier herramienta (opciones `fit_min_zoom`, tablero, `view_area`) | Una instancia por ventana |
| `PreviewResult` + `base_revision` | Base para revisión por objeto en el futuro | Hoy la revisión es global |
| Barra de carga (`wait_value`, `finish_value`) | Otras herramientas con inferencia lenta | Extraerla a un componente común cuando haya un segundo uso |
| `ImageOperation` (imagen → imagen nueva) | Herramientas y efectos | Contrato `core/operation.py:106-107` |

### 4.5 TODAVÍA NO IMPLEMENTADO (no son errores)
`object_id` y `asset_key` (cero apariciones en el código), documento multiobjeto, revisión por objeto, transformaciones/posición de objetos, efectos con parámetros persistidos, deshacer/rehacer (anotado como idea en `processing_state.py:13`), `ToolHost`, visor especializado compartido por perfil, entrega por id de capa.

---

## 5. Las 12 observaciones técnicas, contrastadas con el código

| # | Observación | Resultado | Evidencia |
|---|---|---|---|
| 1 | Las imágenes compartidas son inmutables | **Cumplido por convención, sin cumplimiento forzado.** No hay mutación en el sitio de imágenes compartidas en `app/`, `core/`, `gui/`, `tools/` (búsqueda de `paste`, `putalpha`, `putpixel`, `info[...]=`). Las únicas escrituras (`result.info[...]`, `putalpha`) son sobre imágenes recién creadas | `background_remover.py:277`, `size_resolution/core.py:125`; pruebas: `test_input_is_not_mutated` (Nitidez), `test_resample_off_does_not_mutate_the_original` (Tamaño). **No verifiqué** que cada herramienta tenga su prueba |
| 2 | Las operaciones producen imágenes nuevas | **Cumplido** | Contrato `core/operation.py:106-107`; Tamaño sin remuestreo hace `copy()` (`size_resolution/core.py:123`) |
| 3 | `object_id` y `asset_key` no se confunden | **No existen todavía** | `grep` sin resultados. Recomendación para cuando existan: `asset_key` = clave del recurso de píxeles; `object_id` = identidad del objeto (VectorCraft los separa: `NodeId` y `Document.images` por clave) |
| 4 | El commit actualiza el visor principal | **Cumplido en el código** | `commit_preview` → `_show` → `MainWindow.show_snapshot` → `ImagePanel.show` (`design_controller.py:191-207`, `main_window.py:168-175`). PENDIENTE WINDOWS |
| 5 | Se invalida la pirámide al cambiar la imagen | **Cumplido, con un límite** | `set_image` reinicia `_levels` si es otro objeto; si fuera **el mismo objeto** no invalida (`viewport_renderer.py:118-125`). Hoy ninguna herramienta devuelve la misma instancia (HIPÓTESIS por lectura) |
| 6 | Las revisiones impiden commits obsoletos | **Cumplido** | `design_engine.py:112-113` |
| 7 | Un cambio en otro objeto no invalida innecesariamente | **No aplicable aún** (la revisión es global; hay un solo objeto) | `processing_state.py:102,108` |
| 8 | Callbacks, `after`, pollers y resultados tardíos controlados | **Cumplido, con una excepción corregida y otras pendientes** | `_poll` correcto; barra correcta; **`_finish_window_setup` no se cancelaba → corregido (P1-1)**; `size_resolution/dialog.py:199` `after(150,…)` no se cancela (P2, no tocado) |
| 9 | Sin interacción con widgets destruidos | **Cumplido en Remove** | Guardas `_alive` en cada método de `RemoveDialog`; `RemoveController` suelta `_view` antes de destruir. Probado por tests que **no se ejecutaron aquí** |
| 10 | Se conservan DPI, ICC, alfa, modo y dimensiones | **Parcial** | Remove, Nitidez y Tamaño conservan DPI/ICC (comprobado ejecutándolas); **Semitono los pierde (no intervenido)**; el modo de color se normaliza a RGBA al cargar |
| 11 | El procesamiento definitivo respeta la resolución original | **Cumplido en Remove** | Se procesa la imagen completa y se valida `result.size == image.size` (`background_remover.py:281`) |
| 12 | Se mantiene el zoom cuando las dimensiones no cambian | **Cumplido en el modelo; PENDIENTE WINDOWS** | `viewport.py:315-336`; la decisión de `keep_view` es heurística (ver 4.2) |

---

## 6. Inconsistencias encontradas

| Id | Inconsistencia | Evidencia |
|---|---|---|
| I1 | **Un archivo de pruebas ocupa el lugar de un módulo de producción** | MD5 idéntico (P0-1) |
| I2 | La documentación del plan sigue hablando de **visor único** | `docs/plan_remove/PLAN_INTEGRACION_REMOVE_LUMINE.md` (“un solo visor compartido”), frente a la arquitectura vigente de dos visores |
| I3 | `MainWindow._remove_dialog` no se pone a `None` al cerrar Remove | `main_window.py:100,235`; inocuo hoy porque se consulta tras comprobar `_remove.state` (`:214-218`) |
| I4 | Camino heredado `DesignController.remove_background()` aplica Remove **sin vista previa** | `design_controller.py:188-189`; el menú no lo usa; **9 llamadas en 3 archivos de prueba, 0 en producción** (`test_interaction_state.py`, `test_controller.py`, `test_rmbg_session.py`) |
| I5 | `RemoveDialog` importa `STATUS_COLORS` del módulo de un panel de Lumine | `dialog.py:76` |
| I6 | Contradicción latente de la X: la X se rechaza (`dialog.py:177`), pero la decisión de diseño estaba abierta (D6 de la Fase 2) | `controller.py:236-239` |
| I7 | Semitono pierde DPI/ICC y ninguna prueba lo cubre | `comic_effect.py:46`; `grep` de `dpi`/`info`/`icc` en `tests/test_comic_effect.py`: sin resultados |

## 7. Pruebas: qué cubren y qué no

| Tipo | Módulos | Ejecutado aquí |
|---|---|---|
| Sin Tk (unitarias e integración con dobles) | la gran mayoría (`test_remove_controller`, `test_controller`, `test_interaction_state`, `test_rmbg_session`, `test_viewport*`…) | **Sí** |
| Con Tk real | `test_file_menu_gui` (22), `test_image_panel_interaction` (41), `test_image_panel_viewport` (21), `test_remove_dialog` (21), `test_remove_panel_zoom` (6) ≈ **111 funciones**, más `test_size_resolution_dialog*` | **No** (error de colección o omitidas por falta de Tk) |
| Opcionales | `test_rmbg_real_model` (2 omitidas: requieren `LUMINE_REAL_RMBG=1` y `rembg`) | No |
| **Nueva, sin Tk** | `tests/test_import_integrity.py` (3 pruebas): importaciones del proyecto apuntan a algo definido; ningún archivo de producción importa `pytest`/`tests`; `RemoveDialog` existe donde `main_window.py` lo importa | **Sí** |

**Lo que no está cubierto:** arranque real; conservación de zoom/paneo tras OK; atajos y foco con Remove abierto; `_remove_dialog is None` tras cerrar; DPI/ICC de Semitono; ninguna prueba de la conservación del documento con varios objetos (no existen).
**Posibles pruebas con implementación antigua:** no identifiqué ninguna que verifique el comportamiento antiguo; sí hay acoplamiento a `RemoveDialog`/`ui.win._remove_dialog` (`test_file_menu_gui.py:226`).
**Pruebas omitidas:** 4 en el sandbox; **dos son de Tamaño y resolución y se omiten solo por falta de `customtkinter`**, las otras dos son opcionales de RMBG real. Las cuatro omisiones de tu Windows no pude inspeccionarlas.

## 8. Resultados de ejecución (sandbox, sin Tk)

| Estado | Resultado |
|---|---|
| ZIP original | `640 passed, 4 skipped, 5 errors` |
| ZIP corregido | `643 passed, 4 skipped, 5 errors` (las 3 nuevas pasan; mismos 5 errores de colección por Tk) |
| Prueba nueva sobre el original | **3 failed** (detecta la corrupción); sobre el corregido: **3 passed** |
| Importación con Tk simulado, original | **falla** en `main_window.py:61` |
| Importación con Tk simulado, corregido | OK (`tools.remove.dialog`, `gui.main_window`, `app.application`) |
| `python main.py` real | **No ejecutado** |
| Apertura de Remove real | **No ejecutado** |

No hay regresiones: los 640 que pasaban siguen pasando.

## 9. Semitono

**No se intervino.** `diff` entre el ZIP original y el corregido: solo cambian `tools/remove/dialog.py`, `tests/test_remove_dialog.py`, el nuevo `tests/test_import_integrity.py` y el log (que no es de Semitono). `tools/comic_effect.py` y sus pruebas, y cualquier archivo de Semitono, son idénticos. El problema previamente detectado (pérdida de DPI/ICC, `comic_effect.py:46`) **sigue presente** y se atenderá en su fase.

## 10. Riesgos

| Riesgo | Estado |
|---|---|
| El arranque real puede revelar otro fallo no detectable con Tk simulado | PENDIENTE WINDOWS |
| Otro archivo sobrescrito de la misma manera | **Descartado por análisis estático** (ningún otro MD5 repetido entre `.py`; compilan todos; los imports apuntan a símbolos existentes). No cubre sobrescrituras con contenido distinto pero válido |
| La corrección del `after` cambia el ciclo de vida de `destroy()` | Bajo: cancela un `after` y no cambia ninguna interfaz; su prueba con Tk **no se ejecutó** |
| Documentación contradictoria (visor único) | Medio (I2) |
| Perder metadatos con Semitono | Conocido, no intervenido |

## 11. Conclusiones

1. **La causa del arranque fallido fue un error de archivo, no de arquitectura.** Restaurar el archivo correcto devuelve la implementación vigente, compatible con el controlador, la ventana principal y las pruebas actuales.
2. **La arquitectura acordada está realmente implementada** para Remove (ventana propia, visor propio, preview/commit, bloqueo por política). Lo “multiobjeto” sigue siendo una propuesta.
3. **La suite no podía detectar este fallo sin Tk.** La prueba estática nueva cierra esa brecha.
4. **Lo que falta no es de arquitectura sino de verificación:** arranque real y pruebas GUI (conservación de zoom, atajos, cierre) en Windows.
5. Hay deuda menor y localizada (referencias, un `after` de Tamaño y resolución, documentación), listada en `PLAN_ARREGLOS_LUMINE.md`.
