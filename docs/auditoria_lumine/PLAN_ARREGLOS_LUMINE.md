# PLAN DE ARREGLOS — LUMINECREATIVE (16-nov-2026)

Leyenda: ✅ CORREGIDO · ⏳ PENDIENTE · 🚫 NO INTERVENIDO (instrucción expresa) · 🧭 DECISIÓN TUYA
Todas las verificaciones “aquí” se hicieron **sin Tk** (sandbox). Lo marcado **WINDOWS** requiere tu máquina.

---

## P0 — Crítico

### P0-1 ✅ Lumine no inicia: `RemoveDialog` inexistente
| Campo | Detalle |
|---|---|
| Problema | `ImportError: cannot import name 'RemoveDialog' from 'tools.remove.dialog'` (`gui/main_window.py:61`) |
| Archivo | `tools/remove/dialog.py` |
| Evidencia | MD5 idéntico a `tests/test_remove_dialog.py` (`e322d71a…`); contiene `import pytest` y tests, y 0 clases `RemoveDialog`. Reproducido con Tk simulado |
| Consecuencia | La aplicación no arranca |
| Solución | Restaurar la implementación vigente de `RemoveDialog` (la última versión entregada, compatible con `RemoveView` y con las pruebas: `faltan en RemoveDialog: []`). No se creó una clase vacía ni una implementación duplicada |
| Dependencias | Ninguna (controlador y ventana principal no cambian) |
| Pruebas | Importación con Tk simulado (original falla / corregido OK) ✔ aquí; **`python main.py` y apertura de Remove: WINDOWS** |

### P0-2 ✅ Nada detectaba un módulo de producción sobrescrito por un test
| Campo | Detalle |
|---|---|
| Problema | Sin Tk, ninguna prueba importaba el diálogo; la suite daba verde en el ZIP roto |
| Archivo | nuevo `tests/test_import_integrity.py` |
| Solución | 3 pruebas estáticas (AST): importaciones del proyecto apuntan a símbolos definidos; ningún archivo de producción importa `pytest`/`tests`; `RemoveDialog` existe donde se importa |
| Pruebas | Sobre el original: 3 fallan. Sobre el corregido: 3 pasan, sin falsos positivos en todo el árbol |

---

## P1 — Alto

### P1-1 ✅ `after` diferido de `RemoveDialog` sin cancelar al destruir
| Campo | Detalle |
|---|---|
| Problema | `self.after(_SETUP_DELAY_MS, self._finish_window_setup)` (`dialog.py:179`) no se cancelaba en `destroy()`; solo lo frenaba la guarda `_alive` |
| Consecuencia | **HIPÓTESIS de Tk:** si el callback dispara tras destruir la ventana puede salir un `TclError` de “invalid command name” en consola. No lo reproduje (sin Tk) |
| Solución | Guardar el id (`_setup_job`), cancelarlo en `destroy()` (nuevo `_cancel_setup_job`, idempotente) y limpiarlo al ejecutarse. Sin cambios de interfaz |
| Pruebas | Añadida `test_closing_right_after_opening_cancels_the_deferred_window_setup` (en `test_remove_dialog.py`). **No ejecutada aquí (necesita Tk): WINDOWS** |

### P1-2 🚫 Semitono pierde DPI e ICC al aplicarse
| Campo | Detalle |
|---|---|
| Archivo | `tools/comic_effect.py:46` (`Image.fromarray` crea una imagen sin `info`) |
| Evidencia | Ejecutado en la Fase 2: `info == {}`; sin prueba que lo cubra |
| Estado | **No intervenido.** Se atenderá en una fase independiente |

---

## P2 — Medio

| Id | Problema | Archivo / evidencia | Solución recomendada | Pruebas | Estado |
|---|---|---|---|---|---|
| P2-1 | `MainWindow._remove_dialog` no se limpia al cerrar Remove | `main_window.py:100,235` | Ponerlo a `None` al cerrar la sesión | `ui.win._remove_dialog is None` tras OK/Cancelar (**WINDOWS**) | ⏳ |
| P2-2 | Camino heredado `DesignController.remove_background()` aplica Remove sin vista previa | `design_controller.py:188-189`; 9 llamadas en 3 archivos de prueba, 0 en producción | Decidir si se conserva como API de prueba o se migran esos tests a `run_preview` | los 3 archivos de prueba | ⏳ 🧭 |
| P2-3 | `STATUS_COLORS` importado desde un panel de Lumine | `dialog.py:76` ← `status_panel.py` | Mover la tabla a un módulo de tema común | importación + prueba visual | ⏳ |
| P2-4 | `after(150, _focus_modal)` de Tamaño y resolución no se cancela | `size_resolution/dialog.py:199` | Mismo patrón que P1-1 | cerrar el diálogo de inmediato (**WINDOWS**) | ⏳ |
| P2-5 | `keep_view` decidido por heurística, no por identidad | `main_window.py:68-79` | Decidir por identidad del objeto cuando exista (etapa E4) | zoom/paneo tras OK (**WINDOWS**) | ⏳ |
| P2-6 | Documentación contradictoria: plan con visor único | `docs/plan_remove/PLAN_INTEGRACION_REMOVE_LUMINE.md` | Anotar su sustitución por la arquitectura vigente | — | ⏳ |
| P2-7 | Pruebas GUI reales ausentes (zoom tras OK, atajos/foco, minimizar/maximizar, X) | ver §7 del informe | Implementar G1–G12 de la Fase 2 | en Windows | ⏳ |
| P2-8 | Tests acoplados a la forma actual (`dialog.master is ui.win`, `ui.win._remove_dialog`) | `test_file_menu_gui.py:226` | Revisar al cambiar la estructura de Remove | — | ⏳ |
| P2-9 | Modo de color normalizado a RGBA al cargar | `image_loader.py:150` | Confirmar que es la decisión de diseño; documentarla | — | ⏳ 🧭 |

## P3 — Futuro (no empezar)

| Id | Mejora | Nota |
|---|---|---|
| P3-1 | `object_id` y `asset_key` separados | 0 apariciones hoy |
| P3-2 | Revisión por objeto | hoy global (`processing_state.py:102,108`) |
| P3-3 | Documento multiobjeto | no implementar todavía |
| P3-4 | Extraer barra de carga y perfil de visor a componentes comunes | con una **segunda** herramienta |
| P3-5 | Comportamiento de la X | ✅ RESUELTO por decisión del usuario: cierra como Cancelar si no hay pendientes y pide confirmación si los hay; con RMBG trabajando solo suena el aviso (ver `CAMBIOS_REALIZADOS.md`) |
| P3-6 | Deshacer/rehacer | anotado en `processing_state.py:13` |
| P3-7 | Garantizar mecánicamente la inmutabilidad de imágenes compartidas | hoy por convención |

---

## Orden sugerido de las siguientes intervenciones
1. **Windows:** `python main.py`, abrir imagen, abrir Remove, OK y Cancelar; suite completa.
2. P2-1 y P2-4 (limpieza de referencias y `after`).
3. P2-7 (pruebas GUI reales).
4. Decisiones 🧭 (P2-2, P2-9, P3-5).
5. Fase independiente de Semitono (P1-2).
