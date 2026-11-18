# CONTEXTO MAESTRO — INTEGRACIÓN REMOVE BACKGROUND EN LUMINECREATIVE

## 1. Propósito del proyecto

Integrar Remove Background dentro de LumineCreative como una herramienta propia del software.

LumineCreative es el programa anfitrión y propietario de la arquitectura general. Remove Background no es una aplicación independiente: es una herramienta que utiliza los recursos y servicios de Lumine.

La integración debe sentirse como utilizar otra herramienta de Lumine, no como abrir un segundo programa.

## 2. Principio arquitectónico fundamental

**Lumine es dueño del software, del motor y de la infraestructura.**

Lumine conserva la propiedad de:

- Ventana principal y ciclo de vida de la aplicación.
- Motor de procesamiento y documento activo.
- Imagen original y estado del documento.
- Servicios y ejecución de tareas.
- Sistema de interacción y permisos.
- Infraestructura del visor.
- Gestión de resultados y confirmación de cambios.

Remove conserva su lógica específica:

- `RemoveController`.
- Estados propios de Remove.
- Sesión de trabajo.
- Proceso de eliminación del fondo.
- Vista previa del resultado.
- Acciones de confirmar y cancelar.
- Mensajes y controles específicos de la herramienta.

Remove puede ser modular e independiente en su lógica, pero depende de Lumine como aplicación anfitriona.

## 3. Regla del visor

El objetivo es disponer de **un solo visor compartido en LumineCreative**.

Remove debe pedir prestado ese visor mientras está activa. No debe crear un segundo visor independiente ni mantener una copia paralela de la infraestructura de visualización.

El visor debe seguir siendo responsabilidad de Lumine.

La auditoría encontró que actualmente existen dos instancias de `ImagePanel`, cada una con su propio `ViewportModel` y `ViewportRenderer`. Aunque comparten código, no comparten estado ni constituyen una única instancia.

Esta diferencia debe resolverse en el diseño de integración.

## 4. Conservación del estado

Al entrar en Remove:

- Lumine conserva su documento.
- No debe perder el zoom ni el paneo.
- No debe perder la imagen activa.
- No debe reiniciar su interfaz innecesariamente.
- El trabajo de Remove no debe modificar el documento original antes de confirmar.

Al cancelar:

- Remove descarta su resultado pendiente.
- Lumine recupera el control.
- El documento y el estado anterior deben permanecer intactos.

Al confirmar:

- Remove entrega el resultado a Lumine.
- Lumine, mediante su motor, aplica el resultado al documento.
- Lumine continúa siendo el propietario del documento y de su historial de procesamiento.

## 5. Estado de las fases

### Fase 0 — Estabilización de Remove

**Cerrada.**

Validación en Windows:

- 791 pruebas pasadas.
- 4 omitidas.
- 0 fallidas.
- Tiempo: 140,21 segundos.

La barra de progreso quedó aprobada con ancho de 189 px y alto de 15 px.

No repetir auditorías ni pruebas de esta fase sin un motivo concreto.

### Fase 1 — Auditoría de Lumine

**Auditoría entregada y pendiente de revisión conceptual y resolución de preguntas.**

Documento de referencia:

`FASE1_AUDITORIA_LUMINECREATIVE.md`

Se revisaron:

- Arranque y ventana principal.
- Organización de la interfaz.
- Arquitectura del visor.
- Estado de la imagen.
- Flujo de Remove.
- Dependencias.
- Riesgos.
- Preguntas para diseñar la integración.

La auditoría fue de solo lectura. No se modificó código.

### Fase 2 — Diseño de integración

**Todavía no iniciada.**

Debe comenzar después de revisar las preguntas de arquitectura y acordar los principios de funcionamiento.

No implementar hasta aprobar el diseño.

## 6. Hechos importantes de la auditoría

- `DesignApplication` controla el arranque y existe un único `mainloop()`.
- `MainWindow` es la raíz `ctk.CTk`.
- `ImagePanel` contiene los widgets y eventos del visor.
- `ViewportModel` gestiona la geometría.
- `ViewportRenderer` gestiona los píxeles.
- `ProcessingState` conserva el documento.
- `DesignController` proporciona `preview` y `commit`.
- `InteractionState` ya permite bloquear las acciones principales cuando se utiliza una herramienta.
- `RemoveController` no depende de Tk.
- `RemoveDialog` sí está acoplado a `CTkToplevel`.
- El menú principal y los atajos pertenecen a la raíz.
- El resultado de Remove se confirma a través del motor de Lumine.

## 7. Riesgos que debemos resolver

1. Compartir un solo visor sin perder su estado.
2. Conservar zoom, paneo y encuadre.
3. Administrar correctamente los cambios de vista.
4. Evitar callbacks sobre widgets destruidos.
5. Gestionar Cancelar y la X durante el procesamiento.
6. Mantener los menús y atajos bajo el control de Lumine.
7. No interferir con otras herramientas.
8. Evitar duplicar renderizadores y memoria innecesariamente.
9. Mantener la confirmación de resultados bajo responsabilidad del motor de Lumine.

## 8. Preguntas de arquitectura pendientes

Tomar como base las doce preguntas de la sección 10.3 de la auditoría.

Resolverlas conversando, una decisión a la vez. No asumir respuestas ni convertir posibilidades en decisiones aprobadas.

Especial atención a:

- Cómo se presta el visor.
- Cómo se intercambian las vistas.
- Quién administra la sesión de Remove.
- Qué ocurre con los menús y atajos.
- Qué comportamiento tiene la X.
- Cómo se conserva el estado de Lumine.
- Qué responsabilidades pertenecen a Lumine y cuáles a Remove.

## 9. Forma de trabajo

- Trabajar por fases.
- Auditar antes de modificar.
- No repetir pruebas ya aprobadas sin una razón concreta.
- No hacer refactorizaciones ajenas al objetivo.
- No implementar decisiones todavía no aprobadas.
- Utilizar los nombres y las estructuras reales del código.
- Revisar cada informe antes de pasar a la siguiente etapa.
- Mantener un documento actualizado de acuerdos y decisiones.
- No pedir al usuario que repita información ya documentada.

## 10. Próximo objetivo

Terminar de revisar la auditoría y resolver las decisiones arquitectónicas necesarias para preparar Remove como una herramienta integrada de LumineCreative.

La prioridad no es convertir Remove en otro programa ni construir una arquitectura innecesariamente compleja.

La prioridad es que Lumine tenga una infraestructura de herramientas bien organizada y que Remove utilice correctamente esa infraestructura.

**Lumine es el anfitrión. Remove es una herramienta. El visor pertenece a Lumine.**