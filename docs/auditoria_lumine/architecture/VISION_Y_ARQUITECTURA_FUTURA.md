# LUMINECREATIVE
# ANEXO DE VISIÓN Y ARQUITECTURA FUTURA
## Documento de diseño gráfico, mesa de trabajo y herramientas integradas

**Tipo:** Documento de continuidad arquitectónica  
**Estado:** Visión y requisitos aprobados para orientar el diseño  
**Versión:** 1.0  
**Proyecto:** LumineCreative  
**Relación:** Complementa la auditoría de la Fase 1 y el anexo de transición Lumine → Remove.

---

# 1. VISIÓN GENERAL DEL PROYECTO

LumineCreative busca convertirse en un software de diseño gráfico con capacidades similares, en su concepto de trabajo, a CorelDRAW, Adobe Illustrator e Inkscape.

No se pretende copiar completamente estos programas, sino desarrollar un entorno propio que permita trabajar con imágenes y vectores, preparar diseños, editarlos, organizarlos y disponerlos para producción e impresión.

Adicionalmente, Lumine incorporará herramientas de procesamiento de imágenes, efectos y funciones asistidas por inteligencia artificial, tomando algunas capacidades que habitualmente encontramos en Photoshop.

**Lumine no es solamente un removedor de fondos. Remove Background es la primera herramienta especializada que permitirá establecer el modelo de integración de las herramientas futuras.**

# 2. CONCEPTO DEL ESPACIO DE TRABAJO

Lumine debe evolucionar hacia un entorno de diseño basado en una mesa de trabajo ampliable.

El usuario podrá establecer las dimensiones físicas del área de trabajo según sus necesidades de producción.

Por ejemplo:

- Ancho: 57 cm.
- Alto: 500 cm.

Esta mesa representa el espacio donde se organizarán los elementos que componen un diseño destinado a impresión.

No debe confundirse la mesa de trabajo con el tamaño de la ventana o del monitor. El documento puede ser considerablemente más grande que el área visible de la pantalla.

El usuario necesitará desplazarse, acercarse, alejarse y trabajar sobre distintas zonas del documento.

## 2.1. Trabajo con múltiples elementos

Lumine debe permitir incorporar y organizar múltiples elementos dentro de un mismo documento.

Entre ellos:

- Fotografías e imágenes rasterizadas.
- Imágenes con transparencia.
- Vectores.
- Formas geométricas.
- Textos.
- Elementos gráficos creados dentro de Lumine.

Cada elemento debe conservar su propia identidad y sus propiedades dentro del documento.

El usuario podrá acomodarlos, moverlos, escalarlos y organizarlos para preparar una composición de impresión.

## 2.2. Trabajo orientado a producción

Un ejemplo del flujo de trabajo esperado:

1. Crear una mesa de trabajo de 57 × 500 cm.
2. Importar varias imágenes.
3. Acomodarlas dentro de la mesa.
4. Seleccionar una imagen y eliminar su fondo.
5. Ajustar el resultado.
6. Importar un vector.
7. Modificar sus nodos cuando sea necesario.
8. Crear o modificar otros vectores.
9. Organizar todos los elementos.
10. Preparar el documento para impresión.

El documento completo debe permanecer organizado durante todas estas operaciones.

# 3. DOCUMENTO Y MODELO DE OBJETOS

Una condición fundamental para la evolución de Lumine es que el documento no sea simplemente una imagen abierta dentro de un visor.

Debe evolucionar hacia un documento de diseño que contenga múltiples objetos independientes.

Cada objeto deberá poder conservar, según su naturaleza:

- Identificador propio.
- Tipo de objeto.
- Contenido.
- Posición.
- Dimensiones.
- Escala.
- Rotación.
- Orden de apilamiento.
- Propiedades de transformación.
- Estado de selección.
- Propiedades específicas de su tipo.

En etapas posteriores también deberán contemplarse capas, agrupaciones, bloqueo, visibilidad y otras características propias de un editor gráfico.

## 3.1. Diferencia entre documento y objeto seleccionado

Esta distinción es esencial.

El documento representa toda la composición.

El objeto seleccionado representa el elemento concreto sobre el cual el usuario desea trabajar.

Por ejemplo, si un documento contiene diez imágenes y cinco vectores, seleccionar una imagen no debe convertir todo el documento en una única imagen ni hacer que las herramientas pierdan el conocimiento de los demás elementos.

La selección debe identificar exactamente qué objeto está siendo editado.

# 4. SISTEMA DE HERRAMIENTAS CONTEXTUALES

Lumine deberá reconocer el tipo de objeto seleccionado y presentar las herramientas correspondientes.

La disponibilidad de herramientas dependerá del contexto de selección.

## 4.1. Cuando se selecciona una imagen

Se podrán presentar herramientas como:

- Remove Background.
- Mejorador de imagen.
- Ajustes de imagen.
- Efectos.
- Halftone / semitonos.
- Otras herramientas de procesamiento.

## 4.2. Cuando se selecciona un vector

Se podrán presentar herramientas como:

- Edición de nodos.
- Modificación de curvas.
- Movimiento de puntos.
- Ajustes de formas.
- Transformaciones.
- Operaciones vectoriales futuras.

## 4.3. Cuando se selecciona un texto

Se podrán presentar herramientas de edición tipográfica, formato y transformación.

## 4.4. Principio de funcionamiento

Las herramientas no deben aparecer como funcionalidades desconectadas del documento.

Deben trabajar sobre el objeto seleccionado y conocer su contexto.

La interfaz debe adaptarse al elemento seleccionado sin perder la estructura general del documento.

# 5. TRANSICIÓN ENTRE LUMINE Y SUS HERRAMIENTAS

Se conserva el concepto establecido en el anexo anterior.

Lumine es el anfitrión y propietario de la aplicación.

La transición a una herramienta no implica abrir otra aplicación ni crear una ventana independiente.

Se conserva:

- Barra de título de Lumine.
- Ventana principal.
- Controles del sistema operativo.
- Menú y estructura general del anfitrión.
- Documento completo.
- Infraestructura central.

Cambia el espacio central de trabajo y los paneles correspondientes a la herramienta activa.

## 5.1. Ejemplo: seleccionar una imagen y abrir Remove

El flujo esperado es:

1. El usuario está trabajando normalmente en Lumine.
2. El documento contiene varias imágenes y vectores.
3. Selecciona una imagen.
4. Lumine identifica el objeto seleccionado.
5. El usuario activa Remove Background.
6. Lumine cambia al espacio de trabajo de Remove.
7. Remove trabaja sobre la imagen seleccionada.
8. El usuario procesa y revisa el resultado.
9. Al confirmar, el resultado se incorpora al objeto correspondiente del documento.
10. Lumine regresa a su espacio de trabajo general.

Si el usuario cancela, se descarta el resultado pendiente y se conserva el objeto original.

## 5.2. El documento debe conservar su contexto

Durante la ejecución de Remove, Lumine debe conservar:

- Todos los objetos del documento.
- Sus posiciones y dimensiones.
- Sus propiedades.
- Su organización.
- La selección del usuario.
- El estado visual del documento.
- El zoom y paneo del espacio de trabajo general.

Remove no debe apropiarse del documento completo cuando su tarea consiste en procesar un objeto individual.

La herramienta recibe el objeto que debe trabajar y devuelve un resultado que Lumine puede aplicar mediante el mecanismo de confirmación.

# 6. ARQUITECTURA DEL VISOR

Se mantiene como requisito la existencia de un único visor real compartido.

El visor pertenece a Lumine, no a Remove ni a ninguna otra herramienta.

Las herramientas utilizan la infraestructura de visualización proporcionada por Lumine.

No se deben crear instancias paralelas de ImagePanel, ViewportModel o ViewportRenderer para simular que se comparte el visor.

La arquitectura actual deberá evolucionar para soportar el futuro documento de múltiples objetos.

Esto significa que el visor tendrá que representar una composición y no solamente una imagen individual.

Debe permitir:

- Visualizar el documento completo.
- Representar imágenes y vectores.
- Gestionar zoom y paneo.
- Identificar la selección activa.
- Mostrar los elementos según su posición y orden.
- Responder a las herramientas de interacción.
- Adaptarse a los diferentes espacios de trabajo.

**Importante:** la transición de Lumine a Remove no debe implicar destruir el visor y crear otro. Debe conservarse la propiedad y continuidad del sistema de visualización.

# 7. ARQUITECTURA ESCALABLE

Lumine debe prepararse para incorporar nuevas funcionalidades sin tener que reconstruir su arquitectura cada vez.

La arquitectura futura deberá contemplar responsabilidades diferenciadas:

| Componente | Responsabilidad |
|---|---|
| Aplicación anfitriona | Ventana, ciclo de vida y composición general |
| Sistema de documentos | Documentos, objetos y estado |
| Modelo de objetos | Imágenes, vectores, textos y formas |
| Sistema de selección | Identificar el objeto activo |
| Sistema de espacios de trabajo | Administrar las vistas de cada herramienta |
| Visor compartido | Representar el documento y sus elementos |
| Motor gráfico | Dibujar y transformar los objetos |
| Sistema de herramientas | Registrar y administrar herramientas |
| Controladores | Comunicar las acciones con los servicios |
| Servicios | Ejecutar operaciones de edición y procesamiento |
| Sistema de tareas | Gestionar operaciones asíncronas |

Esta tabla representa responsabilidades arquitectónicas que deberán estudiarse y definirse. No implica que debamos crear inmediatamente todos esos módulos o clases.

# 8. HERRAMIENTAS FUTURAS

El patrón establecido para Remove deberá permitir incorporar progresivamente:

| Herramienta | Tipo de trabajo |
|---|---|
| Remove Background | Procesamiento de imágenes |
| Halftone / semitonos | Efectos de imagen |
| Mejorador de imagen | Procesamiento e IA |
| Ajustes de imagen | Edición rasterizada |
| Editor de vectores | Creación y modificación vectorial |
| Editor de nodos | Modificación de geometría |
| Herramientas de texto | Edición tipográfica |
| Herramientas de transformación | Modificación de objetos |

No todas estas herramientas tienen que utilizar exactamente la misma interfaz. Cada una podrá tener sus propios controles y paneles, pero deberán respetar la arquitectura anfitriona de Lumine.

# 9. REGLAS ARQUITECTÓNICAS FUNDAMENTALES

Las siguientes reglas orientarán las decisiones de desarrollo:

1. LumineCreative es el propietario de la aplicación y de su infraestructura central.
2. El documento debe poder contener múltiples objetos independientes.
3. Las herramientas deben conocer el objeto seleccionado sobre el que trabajan.
4. Una herramienta no debe alterar elementos ajenos a su operación.
5. El documento completo debe conservarse durante las transiciones.
6. Debe existir un único sistema de visor real compartido.
7. Las herramientas no deben crear visores paralelos.
8. Los resultados deben pasar por mecanismos controlados de confirmación.
9. Cancelar debe descartar los cambios pendientes de la herramienta.
10. Las herramientas deben integrarse dentro de la misma ventana anfitriona.
11. La arquitectura debe permitir incorporar nuevas herramientas sin rehacer el sistema.
12. No se deben implementar prematuramente componentes futuros que todavía no sean necesarios.
13. Las funcionalidades ya verificadas deben protegerse mediante pruebas de regresión.

# 10. RELACIÓN CON LA FASE ACTUAL DE REMOVE BACKGROUND

Este documento no autoriza iniciar una reconstrucción general de Lumine.

La prioridad sigue siendo completar correctamente el trabajo actual de Remove.

Sin embargo, la integración debe realizarse teniendo en cuenta el futuro del proyecto.

La estrategia será:

**Primero:** conservar y estabilizar la arquitectura actual.

**Segundo:** diseñar el sistema de espacios de trabajo y la transición entre Lumine y sus herramientas.

**Tercero:** integrar Remove utilizando el documento, la infraestructura y el visor compartidos.

**Cuarto:** validar el funcionamiento en Windows con Tk real y ejecutar las pruebas de regresión.

**Quinto:** documentar qué partes de la arquitectura sirven como base para las siguientes herramientas.

**Sexto:** planificar la evolución del documento de una imagen individual a una mesa de trabajo con múltiples objetos rasterizados y vectoriales.

# 11. CRITERIO FINAL DE DISEÑO

Lumine debe pensarse como una aplicación anfitriona de diseño gráfico extensible.

El usuario trabaja sobre un documento que puede contener múltiples imágenes, vectores y otros elementos.

Selecciona un objeto, utiliza la herramienta que necesita y regresa a su composición sin perder el contexto de trabajo.

Remove Background es el primer ejemplo de este comportamiento.

El objetivo final no es tener varias herramientas independientes dentro de una ventana, sino tener un único entorno de diseño donde todas las herramientas trabajen sobre un mismo documento y una infraestructura compartida.

**Lumine es el entorno de trabajo. Las herramientas son capacidades integradas de ese entorno. El documento es el centro de toda la operación.**

---

# 12. ESTADO Y USO DE ESTE DOCUMENTO

Este anexo debe acompañar:

- La auditoría de la Fase 1 de Claude.
- El documento de continuidad arquitectónica.
- El anexo de transición Lumine → Remove.
- Los futuros planes de integración y escalabilidad.

Debe utilizarse como referencia antes de tomar decisiones arquitectónicas que afecten el documento, el visor, los espacios de trabajo o el sistema de herramientas.

**No implica implementar ahora una mesa de trabajo vectorial completa.** Su propósito es evitar que las decisiones actuales cierren el camino hacia esa evolución.