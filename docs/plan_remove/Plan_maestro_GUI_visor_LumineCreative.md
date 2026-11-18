# Plan maestro de trabajo — GUI, visor y espacios de trabajo de LumineCreative

**Estado:** Preparado; ejecución pendiente.  
**Regla principal:** No ejecutar este plan mientras Claude termina la fase de ajustes que está trabajando actualmente.

## 1. Objetivo

Estabilizar la arquitectura de ventanas, visores y espacios de trabajo de LumineCreative, conservando lo que funciona y aprovechando de PhotoCraft solo los patrones útiles.

Queremos:
- Un único sistema reutilizable de visor.
- Instancias de visor independientes por espacio de trabajo.
- Zoom, paneo y encuadre independientes entre la ventana principal y Remove.
- Ciclo de vida claro para abrir, activar, cerrar y liberar ventanas.
- Diálogos reutilizables para herramientas sencillas.
- Espacios de trabajo especializados para herramientas complejas.
- Remove aislado del documento principal mientras trabaja.
- Procesamiento pesado fuera del hilo gráfico.
- Pruebas y mediciones antes de declarar estable la arquitectura.

## 2. Principios que no se deben romper

1. No reemplazar el visor actual por el de PhotoCraft.
2. Un motor de visor, varias instancias: reutilizar `ImagePanel`, `ViewportModel` y `ViewportRenderer`.
3. No compartir el estado de navegación entre ventanas independientes.
4. No duplicar innecesariamente imágenes originales, cachés ni sesiones de procesamiento.
5. Remove es un espacio de trabajo especializado; no debe forzarse dentro de un diálogo genérico.
6. La GUI no debe ejecutar trabajo pesado.
7. Cada ventana, tarea, suscripción, callback, caché y sesión debe tener un ciclo de vida explícito.
8. Hacer cambios pequeños, medibles y verificables.
9. No migrar la GUI a Rust dentro de este plan.
10. No tocar archivos que Claude tenga abiertos en la fase actual.

## 3. Fase 0 — Esperar y cerrar la fase actual de Claude

**Prioridad:** bloqueante.

Cuando Claude termine:
1. Solicitar su reporte final y el diff completo.
2. Revisar archivos modificados.
3. Ejecutar las pruebas realizadas por Claude.
4. Confirmar que la aplicación inicia y que las funciones modificadas siguen funcionando.
5. Crear un commit o copia de seguridad estable.
6. Comparar sus cambios con este plan y marcar lo que ya quedó resuelto.
7. Actualizar este documento si la arquitectura cambió.

**No comenzar la Fase 1** si hay cambios parciales, errores conocidos sin documentar o pruebas pendientes de la fase actual.

# 4. Fases de trabajo

## Fase 1 — Nueva línea base y auditoría de integración

**Prioridad:** P0 — obligatoria.

La auditoría anterior se hizo sobre una copia ZIP; hay que volver a comprobar los hallazgos en el repositorio actualizado.

Tareas:
- Revisar `gui/panels/image_panel.py`, `gui/viewport.py`, `gui/viewport_interaction.py` y `gui/viewport_renderer.py`.
- Revisar `MainWindow`, `RemoveDialog`, controlador/sesión de Remove, tareas en segundo plano y diálogos.
- Revisar los cambios de Claude y sus efectos.
- Ejecutar la suite completa en el `.venv` real.
- Separar fallos del código, dependencias ausentes, fallos del entorno y pruebas que requieren Windows/Tk real.
- Verificar arranque y recorrido manual básico.
- Medir apertura de Remove, primera visualización, procesamiento, cierre y memoria antes/durante/después.

Entregables:
- `docs/auditoria_gui_linea_base.md`
- Lista de errores reproducibles.
- Tabla de pruebas aprobadas, fallidas, omitidas y bloqueadas.
- Métricas iniciales.

**Aceptación:** conocer qué sigue fallando y qué quedó corregido antes de refactorizar.

## Fase 2 — Estabilizar el visor compartido

**Prioridad:** P0 — crítica.

Tareas:
1. Auditar el renderizado RGBA y el uso de `Image.resize(..., box=...)`.
2. Comprobar si se procesa una región mayor que la visible.
3. Evaluar recortar primero la región necesaria y luego redimensionarla.
4. Verificar calidad, transparencia, bordes y coordenadas.
5. Medir cuándo y cuánto tarda `Image.reduce()` al construir niveles reducidos.
6. Evitar bloquear el hilo de Tk con operaciones costosas, si las mediciones justifican el cambio.
7. Evitar que una tarea antigua publique resultados sobre una imagen o vista que ya cambió.
8. Definir propiedad, límites y liberación de cachés.
9. Conservar zoom anclado al cursor, paneo, ajustar a ventana, zoom 100 %, barras y recorte visible.

Pruebas:
- Imágenes pequeñas, medianas y grandes.
- RGB y RGBA.
- Transparencia y bordes suaves.
- Zoom bajo, 100 % y alto.
- Paneo repetido.
- Cambio de imagen con trabajo pendiente.
- Cierre del panel con repintado pendiente.
- Dos visores simultáneos con estados independientes.

**Aceptación:** sin congelamientos en operaciones habituales, sin resultados atrasados y sin regresiones visuales; mejoras respaldadas por mediciones.

## Fase 3 — Ciclo de vida común de ventanas y espacios de trabajo

**Prioridad:** P0 — alta.

Diseñar un administrador pequeño (por ejemplo `ToolWindowManager`) solo después de mapear las responsabilidades existentes. No crear una capa que duplique funciones actuales.

Responsabilidades:
- Registrar herramientas abiertas.
- Evitar aperturas duplicadas según la política de cada herramienta.
- Enfocar una ventana existente cuando corresponda.
- Gestionar estados de apertura, actividad, cierre y cierre completo.
- Coordinar el cierre de la aplicación principal.
- Ejecutar una única ruta de limpieza.
- Desregistrar ventanas cerradas.
- Evitar callbacks, suscripciones y referencias a ventanas destruidas.
- Distinguir destruir una ventana de detener una tarea de fondo.

Reglas:
- El administrador no procesa imágenes.
- No es propietario del documento si esa responsabilidad pertenece a otra capa.
- Cada herramienta conserva su lógica específica.
- La política de instancia única o múltiple se declara por herramienta.

**Aceptación:** abrir, enfocar, cerrar y volver a abrir no deja ventanas huérfanas, referencias obsoletas ni bloqueos atrapados.

## Fase 4 — Consolidar Remove como espacio de trabajo independiente

**Prioridad:** P0 — alta.

Arquitectura objetivo:
- Ventana especializada `RemoveDialog` o equivalente.
- Instancia propia de `ImagePanel`.
- Estado de vista propio (`ViewportModel`).
- Misma implementación reutilizable de `ViewportRenderer`.
- Controlador que coordina acciones y estados.
- Sesión de edición propietaria de datos temporales.
- Servicio RMBG reutilizable, sin duplicar sesiones por apertura.
- Tareas de fondo con cancelación/espera y entrega segura.

Tareas:
1. Verificar qué responsabilidades ya están resueltas.
2. Confirmar que el zoom y paneo de Remove no alteran la vista principal.
3. Verificar liberación de suscripciones, callbacks, `after` pendientes, `grab` y recursos.
4. Probar cierre de la ventana principal con Remove abierto.
5. Definir el cierre durante una inferencia.
6. Definir aceptar, cancelar y descartar.
7. Completar progresivamente un documento de trabajo independiente: original protegido, resultado temporal, capas/máscaras e historial cuando se implementen.
8. Impedir que una sesión cerrada reciba resultados tardíos.

Estados sugeridos: `CREATED`, `OPENING`, `READY`, `PROCESSING`, `CLOSING`, `CLOSED`. Reutilizar los estados actuales si ya cumplen esta función.

**Aceptación:** Remove puede abrirse, procesar, cancelar/aceptar, cerrarse y volver a abrirse sin alterar indebidamente la vista principal ni dejar recursos de la sesión anterior.

## Fase 5 — Auditoría de procesos, tiempos y memoria RMBG

**Prioridad:** P1 — alta.

Medir por separado:
1. Importación de dependencias.
2. Obtención/creación de sesión ONNX.
3. Preparación de imagen.
4. Inferencia.
5. Composición.
6. Publicación del resultado en GUI.
7. Tiempo total de extremo a extremo.
8. Cierre y liberación.

Pruebas:
- Primera ejecución en frío y siguientes con sesión caliente.
- Varias ejecuciones consecutivas.
- Cancelación antes de iniciar.
- Cierre durante procesamiento.
- Cierre normal después del resultado.
- Aperturas y cierres repetidos.

Medir memoria, hilos, tareas y sesiones. Diferenciar memoria retenida legítimamente por cachés de recursos que deberían liberarse.

**Aceptación:** las etapas explican el tiempo total y cada recurso persistente tiene propietario y justificación documentados.

## Fase 6 — Diálogos reutilizables para herramientas sencillas

**Prioridad:** P1 — media.

Tomar como referencia el sistema genérico de diálogos de PhotoCraft.

Tareas:
- Inventariar herramientas y diálogos actuales.
- Identificar controles comunes: sliders, campos numéricos, selectores y casillas.
- Diseñar una definición declarativa de parámetros.
- Separar definición, presentación y ejecución.
- Implementar previsualización, aplicar y cancelar cuando corresponda.
- Elegir una herramienta sencilla como piloto.
- Comparar el resultado con su ventana anterior antes de migrar otras.

No convertir Remove en diálogo genérico. No crear un framework de plugins innecesario ni migrar todas las ventanas de una vez.

**Aceptación:** una herramienta sencilla puede reutilizar la estructura sin duplicar la lógica de ventana y sin perder comportamiento.

## Fase 7 — Pruebas de integración GUI en Windows

**Prioridad:** P1 — alta.

Con Tk real:
- Abrir/cerrar Remove.
- Reabrir y verificar política de instancias.
- Cerrar con la X de Windows.
- Aceptar y cancelar.
- Cerrar la ventana principal con Remove abierto.
- Verificar `transient`, `grab_set` y liberación de `grab`.
- Verificar foco y activación.
- Cambiar de herramienta repetidamente.
- Cerrar durante una tarea.
- Confirmar que no quedan ventanas huérfanas.

Mantener pruebas unitarias rápidas y separar claramente las pruebas que requieren escritorio/Windows. No contar fallos de colección como pruebas aprobadas.

**Aceptación:** los recorridos críticos funcionan en el entorno objetivo y el reporte distingue aprobadas, fallidas, omitidas y bloqueadas.

## Fase 8 — Documentación y limpieza

**Prioridad:** P2 — media.

Tareas:
- Actualizar README del visor.
- Documentar responsabilidades y dependencias.
- Documentar ciclo de vida de herramientas.
- Documentar propiedad de imágenes, cachés y sesiones.
- Registrar decisiones arquitectónicas.
- Eliminar código obsoleto solo después de rastrear sus consumidores.

Entregables sugeridos:
- `docs/arquitectura_gui.md`
- `docs/ciclo_vida_ventanas.md`
- `docs/visor_rendimiento.md`
- `docs/remove_workspace.md`

**Aceptación:** la documentación coincide con el código y explica cómo abrir una herramienta, solicitar el visor, ejecutar trabajo y cerrar limpiamente.

# 5. Orden resumido

| Orden | Fase | Prioridad |
|---:|---|---|
| 0 | Cerrar la fase actual de Claude | Bloqueante |
| 1 | Nueva línea base | P0 |
| 2 | Estabilizar visor | P0 |
| 3 | Ciclo de vida de ventanas | P0 |
| 4 | Remove Workspace | P0 |
| 5 | Tiempos, procesos y memoria RMBG | P1 |
| 6 | Diálogos genéricos | P1 |
| 7 | Integración GUI en Windows | P1 |
| 8 | Documentación y limpieza | P2 |

Las pruebas de las Fases 5 y 7 pueden comenzar parcialmente antes, pero no se debe declarar estable el sistema hasta tener sus resultados.

# 6. Fuera de alcance

- Reemplazar el visor por el de PhotoCraft.
- Crear un segundo motor de zoom/paneo.
- Permitir que Remove manipule directamente el documento principal mientras trabaja.
- Duplicar el modelo RMBG por ventana.
- Ejecutar procesamiento pesado en el hilo de Tk.
- Crear abstracciones excesivas.
- Migrar toda la GUI a Rust.
- Cambiar muchas capas a la vez.
- Eliminar código sin rastrear sus usos.
- Iniciar una fase con errores bloqueantes de la anterior sin resolver o documentar.

# 7. Protocolo de trabajo con Claude

Para cada fase:
1. Entregar solo la fase que se va a ejecutar y su contexto.
2. Pedir primero análisis de archivos afectados y plan de cambios.
3. Acordar archivos modificables y protegidos.
4. Exigir cambios pequeños y sin refactorizaciones no autorizadas.
5. Exigir pruebas antes y después.
6. Solicitar diff y lista de archivos modificados.
7. Revisar errores, advertencias, regresiones y pendientes.
8. Actualizar este plan con evidencia.
9. No iniciar la siguiente fase hasta aceptar la anterior.

### Formato obligatorio del reporte de Claude

- Objetivo y estado inicial.
- Archivos inspeccionados.
- Archivos modificados.
- Cambios realizados y motivo.
- Pruebas ejecutadas y resultados.
- Pruebas no ejecutadas y motivo.
- Errores encontrados.
- Riesgos y pendientes.
- Confirmación de que no modificó archivos fuera del alcance.

# 8. Registro de avance

- [ ] Fase 0 — Entrega y cierre de ajustes actuales de Claude.
- [ ] Fase 1 — Nueva línea base y auditoría.
- [ ] Fase 2 — Estabilizar visor.
- [ ] Fase 3 — Ciclo de vida de ventanas.
- [ ] Fase 4 — Remove como espacio de trabajo independiente.
- [ ] Fase 5 — Tiempos, procesos y memoria RMBG.
- [ ] Fase 6 — Diálogos genéricos.
- [ ] Fase 7 — Integración GUI en Windows.
- [ ] Fase 8 — Documentación y limpieza.

## Decisión final

La prioridad no es agregar más herramientas ni cambiar de tecnología. Es consolidar lo que ya existe: un visor reutilizable, espacios de trabajo independientes y un ciclo de vida de ventanas confiable.

**Primero estabilidad; después reutilización; finalmente ampliación de herramientas.**

Este plan queda preparado para comenzar cuando Claude entregue y cerremos formalmente la fase que está trabajando por separado.
