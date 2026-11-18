# PLAN DE INTEGRACIÓN DE REMOVE BACKGROUND EN LUMINECREATIVE

**Proyecto:** LumineCreative  
**Área:** Arquitectura de interfaz y gestión de herramientas  
**Objetivo:** Integrar Remove Background dentro de la ventana principal de LumineCreative, conservando su independencia funcional y utilizando una única ventana para toda la aplicación.

---

# 1. VISIÓN DEL PROYECTO

LumineCreative debe funcionar como una aplicación con una única ventana principal y diferentes herramientas que utilizan su espacio de trabajo.

Remove Background debe conservar su independencia funcional, pero dejar de abrir una ventana flotante independiente.

Cuando el usuario active Remove:

1. La interfaz principal de Lumine deja de mostrarse.
2. Remove ocupa el espacio de trabajo completo.
3. Se conserva la misma ventana, barra de título y controles del sistema.
4. Remove trabaja con su propio controlador, estado y configuración.
5. Al cancelar o confirmar, Lumine recupera su interfaz anterior.

**Principio arquitectónico fundamental:**

Lumine es el anfitrión visual. Las herramientas son independientes funcionalmente.

No queremos dos aplicaciones flotando ni dos ventanas compitiendo por la atención del usuario.

# 2. REGLAS QUE DEBEN RESPETARSE

Antes de comenzar, establecer estas reglas como condiciones del proyecto:

- Una sola ventana raíz de la aplicación.
- No crear una segunda ventana para Remove.
- No destruir Lumine al abrir Remove.
- No reconstruir Lumine al cerrar Remove.
- Conservar el estado anterior de Lumine.
- Mantener independientes los controladores de cada herramienta.
- Mantener el procesamiento separado de la interfaz gráfica.
- Compartir la infraestructura del visor sin compartir obligatoriamente las sesiones.
- No duplicar el motor de zoom, paneo ni renderizado.
- No modificar funciones que ya trabajan correctamente sin una justificación técnica.
- No introducir dependencias innecesarias entre Remove y Lumine.

# 3. PLAN DE EJECUCIÓN

## FASE 0. CERRAR Y CONGELAR EL ESTADO ACTUAL

**Prioridad: Máxima**

Esta fase comienza cuando Claude termine los ajustes que están pendientes.

### Actividades

1. Recibir y revisar el informe final de Claude.
2. Identificar todos los archivos modificados.
3. Comprobar las pruebas existentes.
4. Ejecutar las pruebas de Tk real en Windows.
5. Comprobar visualmente Remove.
6. Confirmar que los últimos cambios no afectaron el visor ni el procesamiento.
7. Crear un punto de restauración o commit de Git.

### Criterio de aceptación

Remove funciona correctamente en su implementación actual y tenemos una referencia estable para comparar los cambios posteriores.

No comenzar la integración sin cerrar esta fase.

---

## FASE 1. AUDITORÍA DE LA VENTANA PRINCIPAL DE LUMINE

**Prioridad: Crítica**

Antes de modificar Remove, debemos conocer cómo está construida Lumine.

### Investigar

1. Dónde se crea la ventana raíz.
2. Qué componente controla el ciclo de vida de la aplicación.
3. Dónde se construye la interfaz principal.
4. Cómo se distribuyen los paneles y el espacio de trabajo.
5. Cómo se administra actualmente el visor.
6. Cómo se gestionan los eventos de cerrar, minimizar y maximizar.
7. Cómo se administra el estado de la imagen abierta.
8. Cómo se conserva el zoom, paneo, selección y configuración.
9. Cómo se inicia actualmente Remove.
10. Cómo se conecta Remove mediante CTkToplevel.

### Resultado esperado

Un informe técnico que identifique:

- Arquitectura actual.
- Dependencias entre componentes.
- Archivos involucrados.
- Componentes reutilizables.
- Cambios necesarios.
- Riesgos de integración.

**Importante:** Esta fase es de auditoría. No modificar código.

---

## FASE 2. DISEÑAR EL SISTEMA DE VISTAS

**Prioridad: Crítica**

Diseñar un mecanismo que permita intercambiar las interfaces dentro de la misma ventana.

### Arquitectura conceptual

Lumine Window
- Workspace Host
  - Lumine View
  - Remove View
- Shared Viewer Infrastructure
  - Viewport
  - Renderer
  - Zoom
  - Pan

### Responsabilidades

**Lumine Window**

- Mantener la única ventana raíz.
- Controlar título y controles del sistema.
- Administrar el ciclo de vida general.

**Workspace Host**

- Mostrar la vista correspondiente.
- Ocultar temporalmente la vista anterior.
- Activar la nueva vista.
- Administrar las transiciones.
- Evitar que dos herramientas estén activas simultáneamente.

**Lumine View**

- Conservar la interfaz principal.
- Mantener documentos y paneles.
- Recuperar su estado al regresar de Remove.

**Remove View**

- Mostrar la interfaz de Remove.
- Administrar su sesión.
- Comunicarse con su propio controlador.
- Entregar el resultado cuando corresponda.

**Shared Viewer Infrastructure**

- Proporcionar el motor visual compartido.
- Mantener zoom y paneo.
- Gestionar el renderizado.
- Evitar duplicaciones.

### Criterio de aceptación

Tener un diseño técnico aprobado antes de comenzar a modificar la estructura de la aplicación.

---

## FASE 3. ADAPTAR REMOVE PARA QUE SEA UNA VISTA INTEGRABLE

**Prioridad: Alta**

Actualmente Remove utiliza un CTkToplevel.

Debemos estudiar su transformación en un componente integrable, posiblemente un CTkFrame, que ocupe el espacio de trabajo de Lumine.

### Actividades

1. Separar la presentación de Remove de su ventana actual.
2. Conservar RemoveController.
3. Conservar su lógica de procesamiento.
4. Conservar su configuración.
5. Conservar el sistema de estados.
6. Conservar la barra de progreso y su animación.
7. Conservar el sistema de errores y WARNING.
8. Conservar el visor compartido.
9. Mantener la independencia funcional de Remove.

### No modificar innecesariamente

- RMBG.
- Preview y commit.
- Renderizador.
- Zoom y paneo.
- Tablero de transparencia.
- Lógica de cancelación.
- Procesamiento asíncrono.

### Criterio de aceptación

Remove puede presentarse dentro del espacio de trabajo de Lumine sin depender de una ventana independiente.

---

## FASE 4. IMPLEMENTAR EL INTERCAMBIO DE VISTAS

**Prioridad: Alta**

Implementar la transición entre Lumine y Remove.

### Al abrir Remove

1. El usuario pulsa Quitar fondo.
2. Lumine conserva su estado.
3. La vista principal deja de mostrarse.
4. Se activa Remove.
5. Remove ocupa el espacio disponible.
6. La ventana conserva sus dimensiones y controles.

### Al finalizar Remove

1. Remove ejecuta su operación de cierre.
2. Se libera su sesión.
3. Se entrega o descarta el resultado según corresponda.
4. Se recupera la vista principal.
5. Lumine continúa desde el estado anterior.

### Criterio de aceptación

El usuario puede entrar y salir de Remove repetidamente sin perder el estado de Lumine.

---

## FASE 5. GESTIÓN DE LA VENTANA Y SUS EVENTOS

**Prioridad: Alta**

Como solamente tendremos una ventana, debemos administrar correctamente sus eventos.

### Comportamiento esperado

**X durante Remove**

Debe comportarse como Cancelar:

- Descartar el resultado provisional.
- Cerrar la sesión de Remove.
- Recuperar Lumine.
- No cerrar toda la aplicación.

**Minimizar**

- Minimizar la ventana completa.

**Maximizar/restaurar**

- Modificar la misma ventana.
- Mantener la vista activa.
- Adaptar correctamente el visor al nuevo tamaño.

**Cerrar desde Lumine**

- Ejecutar el cierre normal de la aplicación.

### Casos especiales

- Cerrar Remove mientras RMBG está procesando.
- Recibir resultados después de solicitar el cierre.
- Evitar callbacks sobre widgets destruidos.
- Evitar sesiones duplicadas.
- Evitar que un resultado descartado termine aplicándose.
- Garantizar que la aplicación no quede bloqueada.

### Criterio de aceptación

Todos los eventos de ventana funcionan correctamente sin perder datos ni dejar procesos activos indebidamente.

---

## FASE 6. PRUEBAS DE INTEGRACIÓN EN WINDOWS

**Prioridad: Crítica**

Realizar pruebas con Tk y CustomTkinter reales.

### Pruebas visuales

- Una sola ventana visible.
- Una sola barra de título.
- Una sola X.
- Un solo minimizador.
- Un solo maximizador.
- Remove ocupa todo el espacio de trabajo.
- El visor se adapta correctamente.
- No hay saltos visuales durante las transiciones.

### Pruebas funcionales

- Abrir Remove.
- Cancelar Remove.
- Confirmar Remove.
- Ejecutar RMBG.
- Reintentar procesamiento.
- Cambiar imágenes.
- Aplicar zoom.
- Utilizar paneo.
- Maximizar y restaurar.
- Minimizar y recuperar.
- Cerrar Remove mediante la X.
- Abrir Remove nuevamente.

### Pruebas de conservación

Comprobar que Lumine recupera:

- Imagen abierta.
- Zoom.
- Paneo.
- Panel seleccionado.
- Configuraciones.
- Estado de la interfaz.

### Criterio de aceptación

Todas las pruebas pasan y la experiencia visual corresponde al comportamiento esperado.

---

## FASE 7. DOCUMENTACIÓN Y PREPARACIÓN PARA FUTURAS HERRAMIENTAS

**Prioridad: Media**

Documentar la arquitectura implementada.

### Documentar

- Window.
- Workspace Host.
- Sistema de vistas.
- Ciclo de vida de herramientas.
- Integración de Remove.
- Infraestructura del visor compartido.
- Gestión de estados.
- Comunicación entre herramientas.

### Objetivo futuro

Permitir que otras herramientas de Lumine puedan utilizar el mismo espacio de trabajo sin crear ventanas independientes.

No implementar todas esas herramientas ahora. Solamente dejar preparada una arquitectura reutilizable.

# 4. ARQUITECTURA FINAL DE REFERENCIA

Lumine Window
│
├── Workspace Host
│   │
│   ├── Lumine View
│   │   ├── Paneles principales
│   │   ├── Documentos
│   │   └── Estado de interfaz
│   │
│   └── Remove View
│       ├── RemoveController
│       ├── RemoveDialog/View
│       ├── Remove Session
│       └── Configuración propia
│
├── Shared Viewer Infrastructure
│   ├── Viewport
│   ├── Renderer
│   ├── Zoom
│   └── Pan
│
└── Processing Infrastructure
    └── RMBG y procesamiento de imágenes

La estructura es conceptual. Los nombres y ubicaciones definitivos deben decidirse después de auditar el código existente.

# 5. CONDICIONES PARA TRABAJAR CON CLAUDE

Durante la implementación:

1. Trabajar por fases.
2. No implementar todas las fases en una sola intervención.
3. Auditar antes de modificar.
4. Presentar los archivos afectados antes de cambios estructurales.
5. Evitar refactorizaciones no relacionadas con el objetivo.
6. Mantener las pruebas existentes.
7. Crear pruebas nuevas para cada comportamiento.
8. Informar qué se modificó y por qué.
9. Ejecutar las pruebas disponibles.
10. No declarar una integración terminada sin validarla en Windows con Tk real.

Cada fase debe tener un informe de cierre y una aprobación antes de continuar.

# 6. ORDEN DE EJECUCIÓN

| Orden | Fase | Objetivo |
|---|---|---|
| 0 | Congelar estado | Proteger Remove |
| 1 | Auditoría | Conocer Lumine |
| 2 | Diseño | Definir Workspace Host |
| 3 | Adaptación | Integrar Remove |
| 4 | Transiciones | Intercambiar vistas |
| 5 | Ciclo de vida | Controlar eventos |
| 6 | Pruebas | Validar en Windows |
| 7 | Documentación | Preparar futuras herramientas |

# 7. RESULTADO FINAL ESPERADO

LumineCreative debe ofrecer una experiencia de aplicación profesional:

- Una sola ventana.
- Una sola barra de título.
- Un solo conjunto de controles del sistema.
- Diferentes herramientas dentro del mismo espacio de trabajo.
- Herramientas funcionalmente independientes.
- Visor compartido.
- Sesiones independientes.
- Procesamiento separado de la interfaz.
- Conservación del estado al cambiar de herramienta.

**La meta no es convertir Remove en una parte interna de Lumine. La meta es que Remove pueda trabajar dentro de Lumine sin perder su independencia.**

---

**ESTADO DEL PLAN:** Pendiente de ejecución.

**Punto de inicio:** Fase 0, después de finalizar los ajustes actuales de Remove Background con Claude.

**Regla principal:** No sacrificar lo que ya funciona para conseguir la integración visual.