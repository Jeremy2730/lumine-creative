# CAMBIOS REALIZADOS — 16-nov-2026

Base: `luminecreative.zip` recibido hoy (conservado intacto como referencia). Entorno: sandbox sin Tk.

## Archivos modificados (3)

| Archivo | Problema | Solución | Motivo |
|---|---|---|---|
| `tools/remove/dialog.py` | Contenía el archivo de pruebas (MD5 idéntico a `tests/test_remove_dialog.py`); sin `RemoveDialog` → `ImportError` al arrancar | Restaurada la implementación vigente de `RemoveDialog` (de 368 líneas de pruebas a 356 de producción), con `_BAR_WIDTH, _BAR_HEIGHT = 189, 15` | Es la implementación que usan el controlador, la ventana principal y las pruebas; no se creó una clase vacía ni una copia nueva |
| `tools/remove/dialog.py` (mismo archivo, P1-1) | El `after` diferido de preparación no se cancelaba al destruir | Nuevo `_setup_job`, `_cancel_setup_job()` (idempotente) y llamada en `destroy()`; `_finish_window_setup` lo limpia | Evitar un callback sobre una ventana destruida. Sin cambio de interfaz |
| `tests/test_remove_dialog.py` | Sin prueba del cierre inmediato | Añadida `test_closing_right_after_opening_cancels_the_deferred_window_setup`; el resto sin cambios | Cubre P1-1 |

## Archivo nuevo (1)

| Archivo | Para qué |
|---|---|
| `tests/test_import_integrity.py` | 3 pruebas estáticas, sin Tk: importaciones del proyecto válidas; sin código de pruebas en producción; `RemoveDialog` existe donde se importa. Habría detectado este fallo |

## Documentos añadidos
`docs/auditoria_lumine/INFORME_AUDITORIA_LUMINE.md`, `PLAN_ARREGLOS_LUMINE.md`, `CAMBIOS_REALIZADOS.md` y `FASE2_INFORME_ARQUITECTONICO_LUMINECREATIVE.md`.

## Pruebas ejecutadas (sandbox, sin Tk)

| Ejecución | Resultado |
|---|---|
| Suite en el ZIP original | `640 passed, 4 skipped, 5 errors` (colección: falta `tkinter`/`customtkinter`) |
| Suite en el ZIP corregido | `643 passed, 4 skipped, 5 errors` → **sin regresiones** (+3 nuevas) |
| `test_import_integrity.py` en el original / corregido | 3 failed / 3 passed |
| Importación con Tk simulado, original | falla en `gui/main_window.py:61` (reproduce el error) |
| Importación con Tk simulado, corregido | OK (`tools.remove.dialog`, `gui.main_window`, `app.application`) |
| Conformidad `RemoveDialog` ↔ `RemoveView` (AST) | sin métodos faltantes |

## No verificado (PENDIENTE WINDOWS)
- `python main.py` y que se cree la ventana principal.
- Apertura de Remove, procesar, OK y Cancelar.
- Los 5 módulos con Tk (≈111 funciones), incluida la prueba nueva del `after`.
- La suite completa (la última referencia, 791 passed / 4 skipped / 0 failed, **no** se considera el estado actual).

## Cambios deliberadamente NO realizados
- **Semitono / Halftone:** ningún archivo, algoritmo, configuración ni prueba. El problema de DPI/ICC (`comic_effect.py:46`) sigue presente.
- `DesignController.remove_background()` (9 consumidores en pruebas): se conserva.
- `MainWindow._remove_dialog` sin limpiar (P2-1), `after` de Tamaño y resolución (P2-4), `STATUS_COLORS` (P2-3).
- Comportamiento de la X de Remove.
- Documentación del plan con visor único (se señala, no se edita).
- Sin ToolHost, sin documento multiobjeto, sin cambios de arquitectura, sin dependencias nuevas, sin tocar `gui/`, `tools/` ni `tests/` de la raíz (respaldos), sin commits ni etiquetas.

## Verificación recomendada en Windows (orden)
```
python main.py
python -m pytest -q
```
Después, a mano: abrir imagen → Herramientas ▸ Quitar fondo → procesar → OK; repetir con Cancelar; comprobar que el zoom manual se conserva tras OK.

---

# Ajuste posterior (16-nov-2026, tarde): X con advertencia y controles de ventana de Remove

**Estudio previo (reutilizado, no se creó otra detección).** Un «cambio pendiente» de Remove es el resultado de la sesión sin confirmar: `RemoveController._result` en estado `COMPLETED`, el mismo criterio que habilita OK (`can_ok`, `controller.py`). OK cierra la sesión y el resultado pasa al documento; volver a abrir Remove es otra sesión sin resultado, así que lo ya confirmado nunca cuenta como pendiente. Procesando, error o resultado descartado tampoco cuentan.

| Archivo | Cambio |
|---|---|
| `tools/remove/controller.py` | `has_pending_changes` (= `can_ok`) y `request_close(confirm_discard)`: sin pendientes cierra como Cancelar sin preguntar; con pendientes pregunta; «Seguir editando» no toca nada; «Descartar» ejecuta `cancel()`. `refuse_close` queda solo para el intento de cerrar Lumine. `cancel()` no se tocó |
| `tools/remove/dialog.py` | La X llama a `_on_close_request`; nuevo diálogo `_DiscardChangesDialog` y `ask_discard_changes(parent)` con los textos pedidos; la ventana **ya no es `transient`** y se eliminó el ocultado del botón X por la API de Windows (`_hide_close_button` y sus constantes), para que el sistema muestre minimizar y maximizar/restaurar |
| `gui/main_window.py` | Al intentar cerrar Lumine con Remove abierto, además de `lift()` se hace `deiconify()` para recuperar la ventana si estaba minimizada |
| `tests/test_remove_controller.py` | +9 pruebas (sin Tk) |
| `tests/test_remove_dialog.py` | Sustituida la prueba «la X se rechaza» (ya no es el comportamiento pedido) por 6 pruebas con Tk |

**Pruebas ejecutadas aquí (sin Tk):** `test_remove_controller.py` 35 passed; suite completa `652 passed, 4 skipped, 5 errors` (los mismos 5 módulos que necesitan Tk; antes 643). Dos mutaciones del código (pendiente = cualquier estado; no preguntar nunca) hacen fallar 6 y 2 de las pruebas nuevas, es decir, las detectan.
**No ejecutado (PENDIENTE WINDOWS):** las 6 pruebas con Tk del diálogo, y todo lo visual.

**Decisiones que tomé y conviene que confirmes:**
1. Con RMBG trabajando, la X se comporta como Cancelar y **no pregunta** (aún no hay resultado que perder); la ventana sigue hasta que la IA termina.
2. «Seguir editando» devuelve el control modal a Remove (el diálogo de confirmación se lleva el grab al destruirse; `_take_modal` lo retoma).
3. Quitar `transient` es la **hipótesis** de que Windows no muestra minimizar/maximizar en ventanas `transient`; no la pude verificar. Efecto colateral: Remove tendrá su propio botón en la barra de tareas.

No se tocó Semitono ni ningún otro comportamiento de Remove.


---

# Ajuste (16-nov-2026, noche): Remove como ventana hija de Lumine + Cancelar/X durante RMBG

**Estudio previo.** `RemoveDialog` es un `CTkToplevel` con `master` = Lumine. En el ajuste anterior se le quitó `transient` (hipótesis: Windows no muestra minimizar/maximizar en ventanas `transient`) y eso la convertía en una ventana con **botón propio en la barra de tareas**, es decir, un «segundo programa». Esa decisión **se revierte**: choca con la jerarquía pedida.

**Configuración adoptada (a validar en Windows):**
1. `self.transient(master)` otra vez: ventana propia de Lumine → sin icono propio en la barra de tareas; el sistema la oculta y restaura con Lumine.
2. Botones − y □ pedidos a Windows con `WS_MINIMIZEBOX | WS_MAXIMIZEBOX` (`enable_minimize_maximize`, `ctypes`, solo Windows, fallo silencioso).
3. Minimizar desde Remove (`<Unmap>`): se minimiza también Lumine y un sondeo cada 150 ms devuelve Remove (y el control modal) cuando Lumine se recupera. Remove no queda minimizada sola.
4. Maximizar/restaurar son del sistema y solo afectan a Remove; no se toca ninguna geometría de Lumine.
5. Cancelar y X **con RMBG trabajando**: solo `RemoveView.alert()` → `winsound.MessageBeep(MB_ICONEXCLAMATION)` (respaldo `bell`). Sin diálogo, sin texto, sin cambio de estado, sin repintado; la tarea sigue y la sesión termina como siempre (COMPLETED/ERROR).

| Archivo | Cambio |
|---|---|
| `tools/remove/controller.py` | `RemoveView.alert()`; `cancel()` y `request_close()` en PROCESSING solo llaman a `alert()`. Eliminado el mecanismo «cancelar pendiente» (`_cancel_requested`, `cancel_requested`, `_discard`, estado `CANCELLED`, mensajes asociados), que ya era inalcanzable. `can_cancel` sigue activo procesando |
| `tools/remove/dialog.py` | `transient`, `alert()`, `_on_unmap`/`_follow_main_window` (+ cancelación en `destroy`), llamada a `enable_minimize_maximize`; docstrings reescritos |
| `tools/remove/window_policy.py` (nuevo) | Lógica sin Tk: `follows_main_minimize`, `main_is_restored`, `play_warning_sound`, `enable_minimize_maximize` |
| `tests/test_remove_controller.py` | Pruebas de cancelación reescritas al nuevo comportamiento (37 pasan) |
| `tests/test_remove_window_policy.py` (nuevo) | 9 pruebas sin Tk |
| `tests/test_remove_dialog.py` | Pruebas con Tk: sonido (Cancelar y X), procesamiento continúa, hija de Lumine, minimizar/restaurar/maximizar (estas 3, solo Windows) |

**Ejecutado aquí (sin Tk ni Windows):** suite `663 passed, 4 skipped, 5 errors` (los mismos 5 módulos que necesitan `customtkinter`); `test_remove_controller.py` 37 passed; importación con Tk simulado OK. Mutación (quitar el `alert`) hace fallar 4 pruebas.
**PENDIENTE WINDOWS:** todas las pruebas con Tk de `test_remove_dialog.py` y todo lo visual (ver lista manual en la entrega). Los puntos 1–4 son hipótesis sobre Tk/Windows.

Sin cambios en OK, Semitono, documento, zoom de Lumine ni visor.

---

# Corrección (17-nov-2026): minimizar (−) de Remove — v4

**Resultado de tu validación de v3:** todo bien salvo el botón − de Remove.

**Diagnóstico (por análisis; sin Windows aquí, son hipótesis razonadas):**
- v3 dejaba que Remove se minimizara SOLA y luego reaccionaba (`<Unmap>`, comprobar `state()` de ambas ventanas, `master.iconify()` y un sondeo de 150 ms para `deiconify`). Eso depende de tres supuestos no garantizados en Tk/Windows: que `<Unmap>` llegue para una ventana propia minimizada, que `state()` devuelva `"iconic"` en ese momento y que `deiconify()` sobre una ventana propia cuya dueña sigue minimizada surta efecto. Además es una carrera: Remove ya está minimizada (un estado que Windows trata de forma especial en ventanas propias, con barra de título suelta en el escritorio) antes de actuar.
- El sondeo no era la causa sino la consecuencia de ese diseño: restaurar desde fuera algo que ya está minimizado.
- `WM_ICONIFY/WM_WITHDRAW/WM_DEICONIFY` no son mensajes de Windows (son nombres de Tk: `iconify/withdraw/deiconify`); el mensaje nativo pertinente es `WM_SYSCOMMAND` con `SC_MINIMIZE`.
- Grab: el sondeo restablecía el grab tras `deiconify`; el grab de Tk no se pierde por minimizar, así que no era el problema, pero se rehace al volver por seguridad.

**Solución (reemplaza el mecanismo, no añade otro):**
1. `install_minimize_hook` intercepta `SC_MINIMIZE` en el HWND de Remove y lo consume: **Remove nunca se minimiza sola**.
2. En su lugar se llama a `master.iconify()` (diferido un turno con `after_idle`): Lumine se minimiza y Windows oculta con ella a su ventana propia (`transient`) → un solo icono en la barra de tareas.
3. Al recuperar Lumine, Windows vuelve a mostrar a Remove delante; el evento `<Map>` de Lumine (una vez por minimizado, sin sondeo) asegura `lift()` y devuelve el control modal (`grab_set`).
4. El botón − solo se pide a Windows si el gancho quedó instalado; el gancho se deshace en `destroy()`.
5. Minimizar Lumine directamente no se toca (el flag solo lo activa la orden desde Remove). Maximizar/restaurar, X, Cancelar, sonido, OK y visor: sin cambios.

| Archivo | Cambio |
|---|---|
| `tools/remove/window_policy.py` | Nuevos `is_minimize_command`, `install_minimize_hook`/`MinimizeHook`; `enable_minimize_maximize(minimize=...)`; eliminadas `follows_main_minimize` y `main_is_restored` |
| `tools/remove/dialog.py` | Eliminados `_on_unmap`, `_follow_main_window`, `_follow_job` y `_FOLLOW_MS`; añadidos `_request_minimize`, `_minimize_with_main`, `_on_main_map`, `_restore_after_main` |
| `tests/test_remove_window_policy.py` | Pruebas sin Tk del gancho con `ctypes` simulado |
| `tests/test_remove_dialog.py` | Pruebas de Windows reescritas (envían `SC_MINIMIZE` real) |

**Ejecutado aquí:** suite `666 passed, 4 skipped, 5 errors` (mismos 5 módulos con `customtkinter`); importación con Tk simulado OK. **PENDIENTE WINDOWS:** todo el comportamiento real (no se considera resuelto hasta tu confirmación).

---

# Corrección (17-nov-2026): cierre fatal de Python al pulsar − de Remove — v5

**Hecho aportado por ti:** el cierre fatal ocurre exactamente al pulsar − en Remove (v4).

**Ruta de ejecución que lo provoca (por análisis del diseño de `_tkinter`; no pude reproducirlo ni leer el código fuente de CPython 3.11 desde el sandbox, así que es una hipótesis fuerte, no una certeza):**
1. Windows envía `WM_SYSCOMMAND/SC_MINIMIZE` al HWND de Remove mientras Tk está dentro de `Tcl_DoOneEvent` (el bucle `mainloop`).
2. Se ejecuta mi `WNDPROC` de `ctypes`. `ctypes` toma el GIL (`PyGILState_Ensure`), pero **no** hace la contabilidad propia de `_tkinter` (`ENTER_PYTHON/LEAVE_PYTHON`, que guarda/restaura `tcl_tstate`).
3. En v4 el callback llamaba a Tk (`self.after_idle(...)`) → `ENTER_TCL/LEAVE_TCL` deja `tcl_tstate = NULL`.
4. En el mismo `Tcl_DoOneEvent` Tcl ejecuta después el script de ese `after idle` (y/o los eventos de minimizado); `ENTER_PYTHON` hace `PyEval_RestoreThread(tcl_tstate)` con `NULL` → **error fatal de Python**.
Regla que se deduce: **desde un callback nativo no se puede llamar a Tk/Tcl** (ni `after`, ni `iconify`, ni siquiera `after_idle`), aunque el hilo sea el principal.

**Corrección mínima:**
- El callback nativo ya **no usa Tk**. Hace dos cosas, ambas de Windows/Python puro: `PostMessageW(HWND_Lumine, WM_SYSCOMMAND, SC_MINIMIZE, 0)` (asíncrono: Lumine procesa la orden por su ruta normal, igual que su propio −) y pone un indicador (`_mark_minimized`). Los dos HWND se calculan antes, fuera del callback.
- Eliminados `_request_minimize` y `_minimize_with_main` (eran los que llamaban a Tk).
- Al volver Lumine, `<Map>` (entregado por Tk de forma normal, no desde el callback nativo) pone Remove delante y recupera el modal, una vez por minimizado, sin sondeo ni ciclos (no se vuelve a minimizar nada).
- La función nativa se guarda de forma permanente (`_KEEP_ALIVE`): un mensaje tardío (p. ej. `WM_NCDESTROY`) nunca llama a memoria liberada.
- Prueba estática (`test_the_native_callback_makes_no_tk_calls`): falla si alguien vuelve a poner Tk dentro del callback (comprobado por mutación).

**Ejecutado aquí:** suite sin Tk; **PENDIENTE WINDOWS:** todo el comportamiento real.

---

# Corrección (17-nov-2026): Remove quedaba visible al minimizar Lumine — v6

**Síntoma (tu prueba de v5):** el cierre fatal desapareció; al pulsar − en Remove se minimiza Lumine pero Remove sigue visible.

**Investigación (qué pude y qué no desde el entorno de desarrollo, sin Windows ni Tk):**
1. *Propiedad.* El código establece la relación solo con `self.transient(self.master)` (Tk). En Tk/Windows eso debería crear a Remove como ventana propiedad (owned) del HWND envoltorio de Lumine. No hay en el proyecto ninguna otra llamada Win32 de propiedad.
2–3. *HWND y propietario reales.* **No verificable aquí.** Añadí el diagnóstico `window_report` (HWND de ambas, `GetWindow(GW_OWNER)`, `GA_ROOTOWNER`, visibilidad, minimizada, estilo extendido, y `remove_owner_is_lumine`). Se activa con la variable de entorno `LUMINE_DEBUG_WINDOWS=1` y escribe en el log y en `%TEMP%\lumine_remove_windows.log` en tres momentos: al preparar la ventana, al minimizar Lumine y al restaurarla.
4–5. *Por qué Remove queda visible.* Windows solo oculta con su dueña a las ventanas que de verdad son «owned». Que Remove siga visible tras minimizar Lumine implica que, en la práctica, Windows NO está tratando a Remove como propiedad del HWND de Lumine (el HWND que Tk usó como propietario, o su estado `transient`, no coincide con el envoltorio de Lumine, o se perdió al recrear la ventana). **Esto es una inferencia a partir de tu síntoma, no una medición**; el diagnóstico de arriba la confirmará o refutará.
6. *Restauración.* Si Windows nunca la ocultó, tampoco la restaura: no había ningún mecanismo mío que lo hiciera (v5 dependía solo de la propiedad del sistema; el `<Map>` de v5 solo actuaba si se había marcado una minimización).

**Cambio mínimo (no depende de la propiedad de Windows):**
- Remove se oculta/restaura por sí misma a partir de los eventos de Tk de Lumine, en contexto normal de Tk: `<Unmap>` de Lumine con `state()=="iconic"` → `withdraw()`; `<Map>` → `deiconify()`, `lift()`, `grab_set` y un único reintento a los 100 ms (el grab exige ventana visible).
- Los enlaces a Lumine se hacen **una vez por ventana principal** y se reparten a la Remove abierta (referencia débil): no se acumulan enlaces ni hace falta `unbind`.
- Se mantiene v5 íntegro: el callback nativo solo hace `PostMessageW` a Lumine y no llama a Tk (cubierto por la prueba estática). Se elimina el indicador `_minimized_with_main` y `_mark_minimized` (ya no hacen falta).
- Efecto colateral deliberado: cualquier minimización de Lumine con Remove abierta (también la de su propio − o Win+↓) oculta Remove con ella. Con Remove cerrada no hay ningún enlace activo y Lumine se comporta como siempre.

| Archivo | Cambio |
|---|---|
| `tools/remove/window_policy.py` | Nuevos `window_report` y `log_window_report` (diagnóstico). `install_minimize_hook` sin cambios de lógica |
| `tools/remove/dialog.py` | `_on_main_unmap`, `_on_main_map` reescrito, `_retake_modal`, `_watch_main_window`; eliminados `_minimized_with_main` y `_mark_minimized` |
| `tests/test_remove_window_policy.py` | Pruebas del diagnóstico (propietario sí/no) y del log |
| `tests/test_remove_dialog.py` | Pruebas Windows: Remove oculta (no minimizada), restauración con modal, procesamiento continuo, Lumine sin Remove |

**Ejecutado aquí:** suite `673 passed, 4 skipped, 5 errors` (los mismos 5 módulos con `customtkinter`); importación con Tk simulado OK; simulación del orden de llamadas de los manejadores (`withdraw` → `deiconify`, `lift`, modal, un reintento; sin duplicados). **PENDIENTE WINDOWS:** todo el comportamiento real.

---

# Decisión (17-nov-2026): Remove sin botón minimizar — v7 (sustituye a v5 y v6)

**Decisión tuya:** Remove ya no minimiza Lumine ni se minimiza; su barra de título solo tiene maximizar/restaurar y cerrar. Lumine no se toca.

**Eliminado de v5/v6 (todo era exclusivo de minimizar Remove):**
- `window_policy.py`: `is_minimize_command`, `install_minimize_hook`, `MinimizeHook`, `_KEEP_ALIVE` (la subclasificación `WNDPROC` y el `PostMessageW`), `window_report`/`log_window_report` (diagnóstico de la investigación), el estilo `WS_MINIMIZEBOX` y el parámetro `minimize` (`enable_minimize_maximize` → `enable_maximize`).
- `dialog.py`: el gancho nativo, `_on_main_unmap`, `_on_main_map`, `_retake_modal`, `_cancel_modal_job`, `_watch_main_window` y sus registros débiles, `_hidden_with_main`, `_modal_job`, `_MODAL_RETAKE_MS`, `import weakref` y todo su texto en el docstring.
- `gui/main_window.py`: el `deiconify()` añadido en v2 (solo servía para recuperar una Remove minimizada). El archivo vuelve a ser **idéntico al original recibido**.
- Pruebas de minimizar (v3–v6).

**Conservado:** `transient(master)` (Remove delante de Lumine y sin icono propio), `grab_set` modal diferido, `enable_maximize` (`WS_MAXIMIZEBOX`), sonido de advertencia, X con advertencia, Cancelar/X sin efecto durante RMBG, OK, visor, Semitono. El minimizar de Lumine no se toca: no existe ya ningún enlace sobre su ventana.

**Pruebas nuevas/ajustadas:** `enable_maximize` solo añade `WS_MAXIMIZEBOX` y nunca el de minimizar; el módulo ya no expone nada de minimización; ningún archivo de producción conserva código de minimización (análisis de código, sin docstrings); Windows: la barra de título de Remove tiene maximizar y no minimizar, y Lumine sin Remove se minimiza igual.

**Ejecutado aquí:** suite sin Tk `663 passed, 4 skipped, 5 errors` (los mismos 5 módulos con `customtkinter`); importación con Tk simulado OK. **PENDIENTE WINDOWS:** que Remove no muestre −, que maximizar/restaurar y la X sigan igual, y qué hace Remove cuando minimizas Lumine desde la barra de tareas (no es parte de esta decisión; solo observar).

---

# Ajuste (17-nov-2026): mensajes de estado de Lumine más limpios — v8

**Investigación.**
1. *Dónde se generan.* `DesignController` (`run_task`, `run_tool`, `commit_preview`, `warn`, `_require_image`) y `FileController` (abrir, guardar, extensión no válida) llaman a `view.show_status(mensaje, nivel)`.
2. *Sistema centralizado.* Sí, y único: `show_status` → `MainWindow.show_status` → `StatusPanel.set_message`, que pintaba «Estado: …» con color por nivel (`StatusLevel`: INFO, SUCCESS, WARNING, ERROR). La barra de progreso (`set_busy`/`show_progress`) es un canal aparte.
3. *Clasificación.* INFO = rutina («📂 Abriendo imagen…», «💾 Guardando…», inicio de herramienta, y el «Estado: Listo» inicial); SUCCESS = «✅ Imagen cargada», «💾 Imagen guardada en…», «herramienta aplicada (N × M px)». WARNING = «⏳ Espera a que termine el proceso actual», «Primero abre una imagen», «Extensión no válida», validaciones de Tamaño y resolución. ERROR = «No se pudo abrir/guardar/procesar…».
4. *Referencia Remove (sin modificarlo).* Su vista deja pasar solo `WARNING` y `ERROR`; los demás niveles se muestran vacíos.

**Cambio (mismo criterio, mismo canal, sin mecanismo nuevo):**
- `design_controller.py`: `NOTEWORTHY_LEVELS` y `user_visible_status(mensaje, nivel)` junto a `StatusLevel` (sin Tk, probable). Los controladores **siguen emitiendo todos los niveles** (nada cambia para sus pruebas ni otras vistas).
- `status_panel.py`: `set_message` muestra solo avisos y errores; lo rutinario deja el texto vacío (y borra un aviso anterior ya obsoleto). Texto inicial vacío en vez de «Estado: Listo». La barra de progreso y su detalle («etapa · % — mensaje») no se tocan.
- No se elimina ningún log técnico (`logger.error` con detalle en `run_task` sigue igual; hay una prueba que lo comprueba).

**Efecto visual a tener en cuenta:** el panel inferior de estado queda siempre colocado (alto fijo), así que en reposo es un recuadro sin texto. No lo oculté para no cambiar el tamaño del visor (zoom/encuadre); si prefieres que desaparezca cuando no hay nada que decir, es un ajuste aparte.

| Archivo | Cambio |
|---|---|
| `app/controllers/design_controller.py` | + política `user_visible_status` |
| `gui/panels/status_panel.py` | usa la política; sin «Estado: Listo» |
| `tests/test_status_messages.py` (nuevo) | 9 pruebas sin Tk |

**Ejecutado aquí:** suite `672 passed, 4 skipped, 5 errors` (los 5 módulos con `customtkinter`, sin cambios); importación con Tk simulado OK; mutación (mostrar SUCCESS) hace fallar 6 de las 9 pruebas nuevas. **PENDIENTE WINDOWS:** ver el panel en pantalla (sin texto al abrir/aplicar/guardar; con aviso o error cuando corresponda) y la prueba Tk existente `test_file_menu_gui.py:334` («Primero abre una imagen» sigue visible).

No se tocaron Remove, Semitono, carga, visor, zoom, herramientas, barra de progreso ni arquitectura.

---

# Política global de conservación de tamaño y resolución — v9
Informe completo: `docs/auditoria_lumine/AUDITORIA_CONSERVACION_TAMANO_RESOLUCION.md`.

| Archivo | Cambio |
|---|---|
| `core/image_metadata.py` (nuevo) | qué se protege (`dpi`, `icc_profile`) y `restore_metadata` |
| `core/operation.py` | contrato `changes_geometry` / `changes_resolution` |
| `core/image_pipeline.py` | hace cumplir el contrato tras cada operación (+ log de diagnóstico) |
| `tools/size_resolution/core.py` | declara su excepción |
| `tests/test_metadata_preservation.py` (nuevo) | 30 pruebas |

Remove y `comic_effect.py` no se modificaron. Efecto: Semitono ahora conserva PPI e ICC por la política global. Ejecutado: `702 passed, 4 skipped, 5 errors` (Tk). Pendiente Windows: repetir el caso con rembg real.
