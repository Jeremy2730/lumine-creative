# FASE 1 — Auditoría de la ventana principal de LumineCreative

**Alcance:** solo lectura. No se modificó, creó, borró ni renombró ningún archivo del proyecto. No se diseña la solución de la Fase 2.
**Código auditado:** `luminecreative/` del último zip (`4c3c88fb`) con los 4 archivos finales instalados (`dialog.py`, `test_remove_dialog.py`, `test_file_menu_gui.py`, `test_image_panel_interaction.py`). Es el estado que dio **791 passed, 4 skipped** en tu Windows. `_BAR_HEIGHT` = 15.
**Método:** lectura de código. Aquí no hay Tk, así que **nada de lo que sigue se ejecutó**; lo que depende del comportamiento de Tk en tiempo de ejecución está marcado.

**Leyenda**

| Marca | Significado |
|---|---|
| ✅ | Comprobado leyendo el código (archivo:línea) |
| ⚠️ | Inferencia razonable, **no ejecutada** (hay que verificarla con Tk real) |
| 💡 | Posibilidad futura. **No está aprobada ni diseñada** |

---

## 1. Arquitectura actual de la aplicación

Capas reales (de arriba abajo), todas ✅:

| Capa | Carpeta / archivos | Papel |
|---|---|---|
| Arranque | `main.py`, `app/application.py` | Raíz de composición: crea dependencias y la ventana |
| GUI | `gui/main_window.py`, `gui/panels/*`, `gui/components/*`, `gui/viewport*.py` | Ventana, paneles, menú, visor |
| Controladores | `app/controllers/design_controller.py`, `file_controller.py`, `tools/remove/controller.py`, `tools/size_resolution/controller.py` | Intermediarios GUI ↔ servicio; no importan Tk |
| Estado de interacción | `app/interaction.py` | Qué acciones están permitidas (`Action`, `Scope`, políticas) |
| Servicios | `app/services/*` (`processing_service`, `file_service`, `task_runner`, `document_state`, `tool_registry`) | Casos de uso, hilo de trabajo |
| Motor | `core/design_engine.py`, `core/models/processing_state.py`, `core/image_pipeline.py` | Estado de la imagen y preview/commit |
| Herramientas | `tools/*` (`background_remover`, `comic_effect`, `image_sharpener`, `size_resolution`, `remove`) | Algoritmos y, en dos casos, su ventana |

Patrón dominante ✅: **MVC ligero con vistas por `Protocol`**. `DesignView` (`design_controller.py:87-94`), `FileView` (`file_controller.py:53-77`) y `RemoveView` (`tools/remove/controller.py:80-93`) son las únicas cosas que los controladores saben de la interfaz.

Hay **una sola ventana raíz** (`MainWindow`, `ctk.CTk`) y **dos `CTkToplevel`**: `SizeResolutionDialog` y `RemoveDialog` ✅ (`grep CTkToplevel`: `tools/size_resolution/dialog.py:51`, `tools/remove/dialog.py:119`).

---

## 2. Flujo de arranque y creación de la ventana

```
python main.py
  main.py:14           DesignApplication().run()
    application.py:128   setup_logging(log_dir)
    application.py:130   sessions = RembgSessionManager()      (el modelo ONNX NO se carga aún)
    application.py:131   build_controllers(settings, sessions)
        :114               loader  = build_image_loader(settings)
        :115               service = ProcessingService(DesignEngine(loader), registry, output_dir)
        :116               design  = DesignController(service, BackgroundTaskRunner())
        :117               files   = FileController(design, FileService(loader, service), app_title)
    application.py:135   MainWindow(controller, settings, file_controller)
        main_window.py:91-93   ctk.set_appearance_mode / set_default_color_theme
                               super().__init__()   ← AQUÍ nace la raíz Tk (ctk.CTk)
        main_window.py:104-106 title · geometry(window_size) · minsize(820, 640)
        main_window.py:110-119 header, ImagePanel, ToolsPanel(oculto), StatusPanel
        main_window.py:121-122 menú + protocol("WM_DELETE_WINDOW", _on_close)
        main_window.py:124     interaction.subscribe(_refresh_controls)
        main_window.py:126     after(50 ms, _poll)
    application.py:138-139  controller.attach_view(window); file_controller.attach_view(window)
    application.py:141      window.mainloop()
    application.py:143      finally: sessions.close()
```

Quién controla el ciclo de vida ✅:

- **Crear y arrancar:** `DesignApplication.run` (`application.py:127-143`). Es el único `mainloop()`.
- **Cerrar:** `MainWindow._on_close` (`main_window.py:212-223`) → `FileController.request_exit` (`file_controller.py:144-159`) → `MainWindow.exit_application` (`main_window.py:207-209`: marca `_closed` y `destroy()`).
- **Sondeo de resultados:** `_poll` cada 50 ms (`main_window.py:272-277`), con `after` re-programado en `finally`. Es el único mecanismo que entrega resultados de hilos a la GUI (`BackgroundTaskRunner.drain`, `task_runner.py`).

Minimizar y maximizar ✅: **el código no los gestiona.** No hay `iconify`, `zoomed`, `<Map>`, `<Unmap>` ni `attributes` en `gui/`, `app/`, `tools/` ni `config/`. Los hace el sistema; lo único propio es `minsize(820, 640)` (`main_window.py:106`) y la reacción al cambio de tamaño del visor (sección 4).

---

## 3. Diagrama de componentes de la interfaz

### 3.1 Ventana principal (`MainWindow`, una columna con `grid`) ✅

```
MainWindow (ctk.CTk)                 main_window.py:82
│  rowconfigure(1, weight=1)         main_window.py:108   ← solo la fila 1 crece
├─ menú nativo tk.Menu               menu_bar.py: Archivos | Herramientas
├─ fila 0  header (CTkFrame)         título + autor                        :110
├─ fila 1  ImagePanel                visor principal              :111-112  (sticky nsew)
│            ├─ canvas (tk.Canvas)   imagen
│            ├─ barras de desplazamiento (ancho/alto fijo, se muestran/ocultan por dentro)
│            └─ barra de zoom: −  [%]  +  Ajustar  100 %
├─ fila 2  ToolsPanel                historial de procesos   :114-116  ← grid_remove(): OCULTO, pero se sigue alimentando
└─ fila 3  StatusPanel               etiqueta de estado + CTkProgressBar + detalle   :118-119
```

### 3.2 Remove hoy (ventana flotante) ✅

```
RemoveDialog (CTkToplevel, transient de MainWindow, modal por grab_set)   dialog.py:119
├─ fila 0  ImagePanel PROPIO (fit_min_zoom=True, tablero de transparencia)  :148
│            └─ CTkProgressBar  ← place(in_=canvas, relx=.5, rely=.5)       :240-246
└─ fila 1  contenedor inferior (CTkFrame)                                   :152
             ├─ etiqueta de mensaje (solo errores/avisos)
             └─ botones: Quitar fondo | Cancelar | OK
```

### 3.3 Qué permanece visible/activo al abrir Remove (hoy) ✅

- `MainWindow` **sigue existiendo y visible detrás** (Remove es un `Toplevel`). Su `ImagePanel`, header y `StatusPanel` no se ocultan ni se destruyen.
- Se **bloquea por política, no por ocultar**: `enter_workspace` (`interaction.py:191-197`) deja `can(action)` en `False` para todo en `Scope.MAIN` (`interaction.py:157-165`). `MainWindow._refresh_controls` (`main_window.py:260-270`) lo traduce en menú deshabilitado y `set_navigation_enabled(zoom=False, pan=False)` en su visor.
- Además el diálogo es modal: `transient` (`dialog.py:143`) + `grab_set` diferido 250 ms (`dialog.py:179`, `311`).

---

## 4. Arquitectura real del visor y sus dependencias

### 4.1 Piezas y responsabilidades ✅

| Pieza | Archivo | Responsabilidad | No sabe de |
|---|---|---|---|
| `ImagePanel` (`ctk.CTkFrame`) | `gui/panels/image_panel.py:134` | Widgets (canvas, barras, botones), **eventos del ratón**, repintado agrupado, permisos de zoom/paneo | Motor, controladores |
| `ViewportModel` | `gui/viewport.py:161` | **Geometría pura**: zoom, posición, centrado, límites, modo ajustar, `fit_min_zoom` | Tk, Pillow, píxeles |
| `ViewportRenderer` | `gui/viewport_renderer.py:83` | **Píxeles**: recorta y escala solo lo visible, niveles reducidos, tablero opcional | Tk, geometría (se la pide a `visible_area()`) |
| `viewport_interaction` | `gui/viewport_interaction.py` | Constantes y funciones: paso de zoom, rueda, factor de pantalla (usa `ctypes.windll` en Windows, `:102`, `:106`) | — |

### 4.2 Imagen original e imagen mostrada ✅

- **Propietario del documento:** el motor. `ProcessingState.current` (`core/models/processing_state.py:87`, `83`); `snapshot()` devuelve `ImageSnapshot(image=self.current, …)` **por referencia, sin copiar**.
- `MainWindow._snapshot` guarda el último snapshot (`main_window.py:102`, `170`).
- `ImagePanel.show(image, keep_view)` (`image_panel.py:225-237`) pasa la imagen a `ViewportModel` (solo su tamaño) y a `ViewportRenderer.set_image` (`viewport_renderer.py:118`), que guarda una **referencia** y **nunca la modifica** (todo lo que devuelve es una imagen nueva).
- El visor **no tiene** una "imagen original" separada: muestra la que se le entrega. La del tablero de transparencia se compone solo sobre el recorte visible y es solo visual.
- **Remove** guarda su propia referencia de solo lectura: `RemoveController._original` (`controller.py:178`) y el resultado sin confirmar `PreviewResult` en `_result`.

### 4.3 Cómo se actualiza el renderizado ✅

1. Un evento cambia el **modelo al instante** (aritmética).
2. `_interact` (`image_panel.py:385`) compara el estado antes/después y, si cambió, pide **un** repintado (`_request_render`, `:403`: un solo `after` de 16 ms).
3. `_render` (`:495`) pide los píxeles al renderizador, crea el `PhotoImage` y sincroniza controles (`_sync_chrome`, `:537`).
4. Cambio de tamaño del visor: `<Configure>` del canvas → `_on_configure` (`:373-380`) agrupa ráfagas con 80 ms de calma.

### 4.4 Eventos del ratón ✅

Todos enlazados **al canvas** del panel (`_bind_events`, `image_panel.py:341-357`): rueda (Windows/macOS y Button-4/5), botón central, espacio + botón izquierdo, arrastre, barras de desplazamiento; `<Enter>` hace `canvas.focus_set()` (`:353`) para recibir la barra espaciadora. Zoom con rueda anclado al cursor (`_on_wheel`, `:408`).

### 4.5 Qué es del modelo, del panel y del renderizador

| Decisión | Dueño |
|---|---|
| Zoom mínimo/máximo, "caber", centrado, límites de paneo, qué parte se ve | `ViewportModel` |
| Permisos (`_zoom_enabled`, `_pan_enabled`), botones, barras, cursor, porcentaje | `ImagePanel` |
| Remuestreo, niveles reducidos, tablero | `ViewportRenderer` |
| Si una imagen nueva "continúa el documento" (conservar zoom) | **`MainWindow._continues_document`** (`main_window.py:68-79`), no el visor |

### 4.6 Opciones específicas de Remove que hoy viven en el visor compartido ✅

`ImagePanel(fit_min_zoom=…, min_zoom=…, transparency_checkerboard=…)` (`image_panel.py:145-153`), `view_area` (`:197`) y `ViewportModel(fit_min_zoom, strict_min_zoom)`. Son **opt-in**: el visor principal no las usa (`MainWindow` crea `ImagePanel(self)` sin opciones, `main_window.py:111`). El único consumidor de `view_area` es Remove (`dialog.py:246`).

### 4.7 Instancias del visor hoy ✅

Hay **dos instancias independientes** de `ImagePanel`: la de `MainWindow` y la de `RemoveDialog`. Cada una con su propio `ViewportModel` y su propio `ViewportRenderer`. Comparten **código**, no estado. La imagen es la misma referencia mientras Remove muestra el original; con un resultado, Remove muestra la del `PreviewResult`.

---

## 5. Flujo actual de Remove Background

### 5.1 Apertura ✅

```
Menú Herramientas ▸ Quitar fondo
  menu_bar.py → MenuCallbacks.tools → MainWindow._on_remove          main_window.py:225
    session = RemoveController(self._controller)                      :227
    session.open()                                                    controller.py:166-181
        snapshot = design.current_snapshot()          (None → aviso "Primero abre una imagen")
        design.can(Action.OPEN_TOOL)                  (si no → aviso "Espera…")
        interaction.enter_workspace("remove_background")   ← BLOQUEA lo principal
        self._original = snapshot.image               (referencia, solo lectura)
    dialog = RemoveDialog(self, session)                              :231
        _build → ImagePanel propio, botones, barra, protocol, subscribe
        controller.attach_view(self)  (dialog.py:180)
            view.show_image(original, keep_view=False); view.state_changed()
    self._remove, self._remove_dialog = session, dialog               :235
    Si el diálogo falla al construirse: session.close() y se re-lanza  :232-234
```

### 5.2 Procesar ✅

`RemoveController.run` (`controller.py:193-205`) → `DesignController.run_preview("remove_background", sink=self)` → `run_task` (`design_controller.py` ~286-337): `begin(tool)` (política `FULL_LOCK`), `sink.set_busy(True)`, hilo `design-worker`, resultados vía `drain()` del `_poll` de `MainWindow`. El **sink** es `RemoveController`: el estado, el "ocupado" y el progreso van a Remove, **no** a la ventana principal.

### 5.3 Resultado, OK y Cancelar ✅

| Acción | Efecto |
|---|---|
| Éxito | `_on_result` (`controller.py:261`): guarda `PreviewResult`, estado `COMPLETED`, `show_image(preview.image, keep_view=True)` en el visor de Remove. **El documento no cambia.** |
| Error | `_on_error` (`:273`): estado `ERROR`, mensaje de error (el único texto que el diálogo muestra) |
| **OK** | `ok()` (`:207-222`): `DesignController.commit_preview` → `engine.commit` (rechaza un resultado obsoleto por `revision`, `design_engine.py:103-114`) → **`MainWindow.show_snapshot` del visor principal** → `_close()`. Si falla, queda en `ERROR` con el documento intacto. |
| **Cancelar** sin tarea | `cancel()` (`:224-234`): descarta y `_close()` |
| **Cancelar** con RMBG trabajando | Solo **pide** descartar (`_cancel_requested`); la inferencia ONNX no se interrumpe; al terminar se descarta (`_discard`, `:290`) y queda abierta en `CANCELLED` |
| **X / Alt+F4** | `refuse_close` (`:236-239`): solo muestra un aviso. Además, en Windows se quita el menú del sistema del `Toplevel` para que no se dibuje la X (`dialog.py:317-333`) |
| **X de la ventana principal** | `MainWindow._on_close` (`main_window.py:214-219`): con Remove abierto → `refuse_close()` y `lift()` del diálogo; **no cierra Lumine** |

### 5.4 Cierre y limpieza ✅

`RemoveController._close` (`controller.py:298-311`) en este orden: suelta `_view` (ningún evento posterior llega a la ventana) → estado `CLOSED` → `view.close()` (= `RemoveDialog.destroy()`) → **siempre** `interaction.leave_workspace()` (en `finally`), que notifica a `MainWindow._refresh_controls`.

`RemoveDialog.destroy` (`dialog.py:335-345`): idempotente; marca `_alive=False`, da de baja la suscripción a `InteractionState`, cancela el único `after` de la barra y suelta el `grab`.

### 5.5 Tareas asíncronas y callbacks durante el cierre ✅

- El hilo nunca toca la GUI: entrega por cola; `drain()` descarta todo si `_closed` (`task_runner.py`).
- Un resultado tardío tras cerrar: `RemoveController._view` ya es `None` (`_status`, `_changed`, `set_busy` comprueban) y `_on_result`/`_on_error` salen si el estado es `CLOSED`.
- Un resultado descartado **no puede aplicarse**: solo `ok()` llama a `commit_preview`, y exige `COMPLETED` con `_result` no nulo (`can_ok`, `:144`).
- `RemoveDialog` protege cada método con `_alive`; el `after` de preparación (`dialog.py:179`) **no se cancela** al destruir, pero termina en `if not self._alive: return` (`:308`).

### 5.6 Componentes propios y reutilizados ✅

| Propios de Remove | Reutilizados de Lumine |
|---|---|
| `RemoveController`, `RemoveState`, `RemoveView` (protocolo) | `DesignController` (preview/commit/sink), `InteractionState`, `BackgroundTaskRunner` |
| `RemoveDialog` (ventana, botones, mensaje) | `ImagePanel` / `ViewportModel` / `ViewportRenderer` |
| Barra de carga (`CTkProgressBar` + `wait_value`/`finish_value`) | `PrimaryButton`, `SecondaryButton` (`gui/components/buttons.py`) |
| Opciones `fit_min_zoom` y tablero (en el visor, opt-in) | `STATUS_COLORS` importado de `gui/panels/status_panel.py` (`dialog.py:76`) |
| Política `FULL_LOCK` para `remove_background` (`interaction.py:111-114`) | `BackgroundRemover` + `RembgSessionManager` (sesión ONNX compartida, `application.py:130`) |

---

## 6. Inventario de archivos y clases relevantes

| Archivo | Líneas | Clase / función clave | Relevancia para la integración |
|---|---:|---|---|
| `main.py` | 18 | `main()` | Arranque |
| `app/application.py` | 143 | `DesignApplication.run`, `build_controllers` | Raíz de composición; único `mainloop` |
| `gui/main_window.py` | 277 | `MainWindow(ctk.CTk)`, `_continues_document` | **Ventana raíz, anfitrión actual**; abre Remove; decide `keep_view` |
| `gui/panels/image_panel.py` | 588 | `ImagePanel` | Visor compartido |
| `gui/viewport.py` | 456 | `ViewportModel` | Geometría del visor |
| `gui/viewport_renderer.py` | 249 | `ViewportRenderer` | Píxeles del visor |
| `gui/viewport_interaction.py` | 124 | funciones de zoom/escala | Utilidades del visor |
| `gui/panels/status_panel.py` | 108 | `StatusPanel`, `STATUS_COLORS` | Estado/progreso de Lumine (no es el de Remove) |
| `gui/panels/tools_panel.py` | 53 | `ToolsPanel` | Historial (oculto) |
| `gui/components/menu_bar.py` | 136 | `MenuBar`, `bind_file_shortcuts` | Menú nativo y atajos en la raíz |
| `gui/components/dialogs.py` | 118 | `ask_*` | Diálogos nativos con `parent=` |
| `app/interaction.py` | 227 | `InteractionState`, `Scope`, `Action`, `TOOL_POLICIES` | Bloqueo central; **independiente de la ventana** |
| `app/controllers/design_controller.py` | 358 | `DesignController` | `run_preview`, `commit_preview`, `current_snapshot`, `warn` |
| `app/controllers/file_controller.py` | 274 | `FileController` | Abrir/guardar/salir/título |
| `app/services/task_runner.py` | 76 | `BackgroundTaskRunner` | Hilo y cola |
| `core/design_engine.py` | 142 | `DesignEngine` | `preview`/`commit` con `revision` |
| `core/models/processing_state.py` | 118 | `ImageSnapshot`, `PreviewResult`, `ProcessingState` | Propiedad de la imagen |
| `tools/remove/controller.py` | 323 | `RemoveController`, `RemoveState`, `RemoveView` | **Sesión de Remove sin Tk** |
| `tools/remove/dialog.py` | 345 | `RemoveDialog(CTkToplevel)` | **Presentación de Remove, acoplada a `CTkToplevel`** |
| `tools/remove/__init__.py` | 17 | reexporta controlador y estados (no el diálogo, a propósito) | Importar el paquete no exige CustomTkinter |
| `tools/size_resolution/dialog.py` | 441 | `SizeResolutionDialog(CTkToplevel)` | Segundo Toplevel; **fuera del alcance de Remove** |
| `tools/background_remover.py` | 312 | `BackgroundRemover`, `RembgSessionManager` | RMBG (no se toca) |

Pruebas que tocan este asunto ✅: `test_remove_controller.py` (26), `test_remove_dialog.py` (20), `test_remove_panel_zoom.py`, `test_viewport_fit_min.py` (14), `test_file_menu_gui.py` (22), `test_image_panel_viewport.py`, `test_image_panel_interaction.py`.

---

## 7. Componentes reutilizables (hechos, no propuestas)

| Componente | Por qué ya sirve fuera de un `Toplevel` | Evidencia |
|---|---|---|
| `RemoveController` | No importa Tk; habla con su vista solo por `RemoveView` | `controller.py:58-62` (solo `app`, `core`), `:80-93` |
| `InteractionState` (`Scope.MAIN`/`TOOL`, `enter/leave_workspace`) | Es lógica pura, sin widgets; ya modela "hay un espacio de herramienta abierto" | `interaction.py:13`, `157-203` |
| `ImagePanel` / `ViewportModel` / `ViewportRenderer` | Un `CTkFrame` autónomo; se instancian N veces sin compartir estado | `image_panel.py:134`; dos instancias hoy |
| `DesignController.run_preview(sink=…)` | Ya redirige estado, "ocupado" y progreso a cualquier receptor | `design_controller.py:209-230`, `343` |
| Bucle `_poll` único | Sigue entregando resultados mientras Remove está abierto | `main_window.py:126`, `272-277` |
| `PreviewResult` + `commit` con `revision` | Resultado desacoplado del documento y rechazado si quedó obsoleto | `processing_state.py:69-80`, `design_engine.py:103-114` |

---

## 8. Acoplamientos y obstáculos para la integración

Cada punto: **qué existe** (✅) → **por qué importaría** (⚠️, inferido).

| # | Acoplamiento | Evidencia ✅ | Efecto probable (⚠️) |
|---|---|---|---|
| A1 | `RemoveDialog` **hereda de `CTkToplevel`** y su construcción usa API de ventana: `title`, `geometry`, `minsize`, `transient`, `protocol`, `grab_set`, `grab_release` | `dialog.py:119`, `140-143`, `177`, `311`, `342` | Un `CTkFrame` no tiene ninguna de ellas; hay que decidir a quién pasa cada responsabilidad |
| A2 | Ocultar la X con la **API de Windows sobre el `Toplevel`** (`GetParent`, `SetWindowLongW`, `WS_SYSMENU`) | `dialog.py:317-333` | Aplicado a la raíz quitaría la X de **toda** la aplicación. Deja de tener sentido en una vista integrada |
| A3 | Título propio "Quitar fondo" y tamaño propio 980×760 / mínimo 680×560 | `dialog.py:140-142` | La raíz tiene título dinámico del documento (`FileController.window_title`) y mínimo 820×640 (`main_window.py:106`) |
| A4 | `RemoveDialog` **se conecta solo**: `controller.attach_view(self)` dentro de `_build` | `dialog.py:180` | Crear la vista ya inicia la sesión de vista; el orden de creación importa |
| A5 | **Referencias directas ventana↔ventana**: `MainWindow` guarda `_remove` y `_remove_dialog`; el diálogo recibe `master` y lo usa (`transient(self.master)`) | `main_window.py:99-100`, `235`; `dialog.py:143` | Hay estado de sesión repartido entre `MainWindow` y el diálogo |
| A6 | `MainWindow._remove_dialog` **nunca se pone a `None`** al cerrar Remove | `main_window.py:100`, `235` (sin asignación posterior) | Hoy es inocuo (el código consulta `_remove.state is not CLOSED` antes de usarlo, `:214`), pero deja una referencia a un widget destruido |
| A7 | La barra de carga se ancla con `place(in_=viewer.view_area)` y su **maestro es el diálogo** | `dialog.py:240-246` | Tk exige que el widget de `in_` sea el maestro del esclavo o un descendiente; con un marco como maestro seguiría cumpliéndose, pero depende de que `view_area` siga siendo descendiente |
| A8 | **Atajos de teclado en la raíz**: `bind_file_shortcuts` usa `window.bind`, y el comentario de diseño depende de que un `Toplevel` con foco no los dispare | `menu_bar.py` (docstring "NO con `bind_all`…"), `main_window.py:149-152` | Si los widgets de Remove pasan a ser hijos de la raíz, **Ctrl+O/S/Mayús+S llegarán a la raíz** (por los bindtags de Tk). Los frena `InteractionState` (`can(OPEN_IMAGE)` es falso con espacio abierto) y `FileController._warn_busy` solo escribe un aviso en el `StatusPanel`; no se comprobó con Tk real |
| A9 | `RemoveController` **no conoce** el menú ni la raíz, pero el **menú sigue vivo**: `_refresh_controls` lo deshabilita por política | `main_window.py:265-269` | Con una sola ventana, el menú visible durante Remove sigue regido por `InteractionState` (ya lo está) |
| A10 | `STATUS_COLORS` se importa del módulo de **`StatusPanel`** de Lumine | `dialog.py:76`, `status_panel.py:38` | Dependencia de Remove hacia un panel concreto de Lumine solo por una tabla de colores |
| A11 | `ImagePanel` **lee su tamaño de `winfo_width/height` del canvas** | `image_panel.py:359-360`; usado en `show` (`:229`), `_interact` (`:395`), `_render` (`:499`) | Con la vista principal **oculta**, los valores que devuelva Tk para un canvas no mapeado no están comprobados (ver R2) |
| A12 | `ImagePanel` toma el foco con `<Enter>` (`canvas.focus_set()`) | `image_panel.py:353` | Con dos visores dentro de una misma ventana, el foco de teclado (barra espaciadora) puede quedar en el visor que no está visible; no comprobado |
| A13 | Tests acoplados a la forma actual: `ui.win._remove_dialog`, `dialog.master is ui.win`, `isinstance(dialog, RemoveDialog)`, `ctk.CTk` + `Toplevel` en `test_remove_dialog.py`, y la prueba de que la X del sistema se rechaza | `test_file_menu_gui.py` (`test_tools_menu_opens_and_runs_each_tool_with_expected_behavior`), `test_remove_dialog.py` (fixture `env`, `test_closing_the_window_with_the_system_button_is_refused`) | Cualquier cambio estructural obliga a reescribir pruebas, no solo código |
| A14 | **`SizeResolutionDialog` es otro `CTkToplevel`** con su propia modalidad | `size_resolution/dialog.py:51`, `105`, `199-210` | El plan habla solo de Remove; ver pregunta P9 |

---

## 9. Riesgos técnicos

| Id | Riesgo | Qué se sabe (✅) | Qué no se sabe (⚠️) | Cómo se comprobaría |
|---|---|---|---|---|
| R1 | **Perder el estado de Lumine al cambiar de vista** | El estado de Lumine vive **fuera** de los widgets: documento en el motor (`ProcessingState`), `_snapshot` en `MainWindow`, título en `FileController`, zoom/paneo en el `ViewportModel` del visor principal. Con un `Toplevel` hoy no se destruye nada | Si "ocultar" la vista (según cómo se haga) conserva widgets y modelo es **una decisión de la Fase 2**; destruir y recrear sí los perdería | Diseño + prueba de conservación (imagen, zoom, paneo) |
| R2 | **Tamaño del visor principal mientras está oculto, y al confirmar con OK** | OK llama a `MainWindow.show_snapshot` (`controller.py:207-222` → `main_window.py:168-175`) **antes** de `_close()`. `show()` lee `winfo_width/height` y, en zoom manual, `ViewportModel.set_viewport_size` conserva el centro de la imagen (`viewport.py:304`) | Qué devuelve Tk para el canvas oculto (último tamaño o 1×1) y si el zoom/encuadre del visor principal se altera al confirmar | **Prueba en Windows con Tk real** (zoom manual → Remove → OK → comparar zoom y centro) |
| R3 | **Duplicar el visor** | Hoy son dos instancias de la misma clase sin lógica duplicada (4.7). El motor de zoom/paneo/render existe una vez | Una vista integrada podría tentar a crear un tercer motor; el plan lo prohíbe | Revisión en Fase 2 |
| R4 | **Memoria de dos visores vivos** | Cada `ViewportRenderer` guarda una referencia a la imagen y construye niveles reducidos propios (`viewport_renderer.py:118`) | Cuánto pesan para imágenes de gran tamaño con ambos visores vivos; no se midió | Medición con una imagen grande |
| R5 | **Callbacks sobre widgets destruidos/ocultos** | Hoy están cubiertos: `_alive`, `_view=None`, `_closed`, `drain` descartando al cerrar (5.5). La barra tiene un solo `after` y se cancela | Con una vista que ya no se destruye al cerrar, hay que decidir qué hace "cerrar" con `_alive` y `destroy()` (hoy ambos están ligados a la destrucción de la ventana) | Pruebas de cierre durante procesamiento |
| R6 | **Eventos de la ventana (X) con una sola raíz** | Hoy la X de Remove **se rechaza** con un aviso; la del plan (Fase 5) la define como **Cancelar** | Es una **diferencia de comportamiento** entre lo actual y lo deseado; cambiarla afecta pruebas existentes (A13) | Decisión en Fase 2/5 |
| R7 | **Foco y teclado** compartidos entre dos visores y los atajos de la raíz | A8 y A12 | Comportamiento real de bindtags/foco | Pruebas manuales en Windows |
| R8 | **Parpadeo o saltos al intercambiar vistas** | No hay ninguna transición hoy | Depende de cómo se oculte/muestre y de `<Configure>` (80 ms de calma en `image_panel.py:373-380`) | Observación visual en Windows |
| R9 | **Regresión en lo ya validado** | 791 pasan; zoom aprobado, barra aprobada, mensajes aprobados | Cualquier reestructuración toca `dialog.py`, `main_window.py` y pruebas | Mantener la suite y la línea base (Fase 0) |
| R10 | **No poder verificar aquí** | Esta auditoría es estática | Todo lo marcado ⚠️ requiere tu Windows con Tk real | Plan de pruebas de la Fase 6 |

---

## 10. Conclusiones y preguntas para la Fase 2

### 10.1 Conclusiones (hechos)

1. **La separación que el plan necesita ya existe en la lógica, no en la presentación.** `RemoveController` + `RemoveView` + `InteractionState` no dependen de ninguna ventana (secciones 5.6 y 7).
2. **Todo el acoplamiento a `CTkToplevel` está en un solo archivo**, `tools/remove/dialog.py`, más dos referencias en `main_window.py` (`:99-100`, `:214-235`) y los tests (A1-A6, A13).
3. **El visor ya se reutiliza sin duplicar** (dos instancias de una clase). Lo que el plan llama "infraestructura compartida" es literalmente `ImagePanel`/`ViewportModel`/`ViewportRenderer` (sección 4).
4. **El estado de Lumine no vive en la ventana**, sino en el motor, en `MainWindow._snapshot`, en `FileController` y en el modelo del visor (R1).
5. **El bloqueo de la aplicación principal** mientras Remove está abierto ya es **política** (`Scope.MAIN`), no una consecuencia de que la ventana tape a otra.
6. **Hay un punto de contacto delicado y no comprobado:** el visor principal recibe la imagen confirmada mientras Remove está abierto (R2).
7. **Lo que hoy es exclusivo de la ventana flotante** y desaparecería o cambiaría de sentido: título propio, tamaño propio, modalidad por `grab_set`, X oculta por API de Windows, y rechazo de la X (A2, A3, R6).

### 10.2 Lo que PhotoCraft aporta como referencia (comprobado en su documentación y en las líneas citadas; **no es un modelo a copiar**)

PhotoCraft está escrito en **Rust con egui** (modo inmediato), no en Tkinter; no hay código reutilizable, solo ideas.

| Qué hace PhotoCraft | Dónde | Lectura para Lumine (💡 posibilidad, no decisión) |
|---|---|---|
| El núcleo no conoce la interfaz: "comandos entran, eventos salen" (`Session`) | `docs/architecture.md` §4.1, §4 "UI-swap seam" | Se parece a `DesignController` + `InteractionState` |
| Cada comando declara su **tipo**: `Instant` / `Dialog` / `Interactive` (este último "entrega el control a una herramienta", p. ej. Free Transform) y un modo de **vista previa** `None/Live/Proxy` | `docs/architecture.md` §4.2 | Remove sería análogo a un comando con vista previa y confirmación (hoy ya es preview/commit) |
| El visor es un componente aparte (`Viewport`: cámara, zoom, paneo, `doc_to_screen`) que cualquier toolkit incrusta | `docs/architecture.md` §4.4 | Coincide con la separación `ViewportModel`/`ViewportRenderer` |
| Los diálogos se **dibujan dentro de la misma ventana** (`egui::Window` anclada al centro) | `crates/ui-egui/src/workspace_ui.rs:348` y otros | Es el equivalente a una capa dentro de la ventana única |
| **Pero** algunas herramientas pesadas abren una **ventana de sistema aparte** (Camera Raw, 1360×900) o una ventana de documento | `camera_raw_ui.rs:853`, `canvas.rs:3517` | PhotoCraft no es 100 % "una sola ventana": mezcla ambos enfoques |
| En Windows/Linux **dibuja su propia barra de título** (sin decoraciones del SO); Cerrar ejecuta Archivo ▸ Salir y por tanto pregunta por cambios sin guardar | `docs/ui-design.md` "Title bar" | No aplica a CustomTkinter tal cual |
| Preferencias con **Apply / OK / Cancel**; Cancel descarta solo lo hecho desde el último Apply | `docs/ui-design.md` "Preferences" | Semántica parecida a Quitar fondo / OK / Cancelar |

*Limitación:* leí `docs/architecture.md`, `docs/ui-design.md` y las líneas de `ui-egui` citadas. **No** estudié el bucle de eventos ni la gestión interna de modos de PhotoCraft.

### 10.3 Preguntas que la Fase 2 debe resolver (sin respuesta propuesta aquí)

| # | Pregunta | Por qué es una decisión |
|---|---|---|
| P1 | Al pasar de Lumine a Remove, ¿la vista principal se **oculta conservando sus widgets** o se **destruye y recrea**? | R1, R2 y el requisito "no reconstruir Lumine" |
| P2 | ¿Qué pasa con el **menú nativo** y los **atajos** de la raíz durante Remove? (A8, A9) | Hoy el menú se deshabilita por política; los atajos están en la raíz |
| P3 | ¿Quién es el **dueño de la sesión de Remove**: `MainWindow` (como hoy) o un anfitrión de vistas? (A5, A6) | Define dónde viven `_remove` y el ciclo de vida |
| P4 | ¿Qué hace **X** durante Remove? El plan dice "como Cancelar"; hoy se rechaza con aviso (R6) | Cambia comportamiento y pruebas |
| P5 | ¿Qué hace la X **si RMBG está procesando**? Hoy Cancelar con tarea en curso solo *pide* descartar | Caso especial del plan (Fase 5) |
| P6 | ¿Qué **título** y **tamaño mínimo** rigen mientras Remove está visible? (A3) | Una sola raíz con `minsize 820×640` |
| P7 | ¿Cómo se **cierra** una vista que ya no es una ventana, y qué significan `destroy()` y `_alive` para ella? (R5) | Hoy ambos coinciden con destruir el `Toplevel` |
| P8 | ¿Dónde debe vivir la **barra de carga** respecto al visor para conservar el `place(in_=…)`? (A7) | Hoy depende de que el maestro sea el diálogo |
| P9 | ¿`SizeResolutionDialog` (otro `Toplevel`) **queda como está**? (A14) | El plan solo habla de Remove |
| P10 | ¿Qué visor tiene el **foco de teclado** y cómo se evita que el oculto lo capture? (A12) | Barra espaciadora y `<Enter>` |
| P11 | ¿Las opciones de Remove en el visor compartido (`fit_min_zoom`, `view_area`, tablero) **se mantienen como opt-in** o se reorganizan? (4.6) | Regla del plan: no duplicar ni tocar lo que ya funciona |
| P12 | ¿Cómo se **verifica** la conservación de estado (R2) antes de dar por buena la Fase 4? | Solo comprobable con Tk real |

---

*Fin de la auditoría. No se propone ni se aprueba ningún cambio. El diseño del sistema de vistas es el objeto de la Fase 2.*
