Hechos confirmados
1. El modelo de hilos de Tkinter y el significado de RuntimeError

Cada objeto Tk contiene un intérprete de Tcl, y el intérprete de Tcl solo puede ser utilizado de forma segura por el hilo que lo creó. Las llamadas a Tkinter desde otros hilos se encolan en la cola de eventos del intérprete y son ejecutadas por el hilo del intérprete . La documentación oficial es clara: si el intérprete de Tcl no está ejecutando el bucle de eventos (mainloop), las llamadas a tkinter desde hilos no principales fallarán . El origen de RuntimeError: main thread is not in main loop es que el mecanismo de sondeo interno de _tkinter no logra obtener el control del hilo principal .

2. La liberación de objetos Tkinter desde hilos no principales es un problema conocido y reportado

En la lista de correo oficial de Python existe un informe de bug (issue39093) que documenta explícitamente: los objetos tkinter liberados por el recolector de basura en hilos no Tkinter causan crashes (inicialmente reportado como panic/core dump). La macro de verificación CHECK_TCL_APPARTMENT en Tkapp_Dealloc() de _tkinter.c está comentada, por lo que no se detecta que __del__ se llame desde el hilo incorrecto . En otra discusión de 2019, desarrolladores describieron el mismo fenómeno: "los objetos tkinter entran en ciclos de referencias y son recolectados por el hilo que esté ejecutándose cuando el GC cíclico se activa en ese momento" .

3. El finalizador Font.__del__ es un punto de activación plausible, pero no está probado

La evidencia actual se limita a: el volcado de pila muestra que Font.__del__ se ejecuta en un hilo de trabajo. Esto no demuestra que el GC haya ejecutado Font.__del__ en el hilo de la herramienta. Lo que falta por demostrar incluye: si el objeto Font ingresa a un ciclo de referencias, si el GC cíclico se activa durante la ejecución del hilo de trabajo, y si la llamada a __del__ proviene del hilo de trabajo o del hilo principal.

4. La solución en pruebas (fixture de GC) no equivale a corregir la aplicación

El fixture que controla el GC antes y después de las pruebas hace que las 437 pruebas pasen en pantalla virtual, pero esto solo bloquea el momento de activación del GC, no cambia el hecho de que "los objetos Tkinter pueden ser liberados en hilos no principales". En el uso normal, si hay objetos Tkinter participando en ciclos de referencias y el hilo de trabajo está ejecutándose cuando el GC se activa, la posibilidad de fallo sigue existiendo.

Hipótesis e incertidumbres
Hipótesis A (alta credibilidad): Los objetos relacionados con Tk (Font u otros objetos Tkinter) entran en ciclos de referencias, el recolector de basura cíclico de Python se activa durante la ejecución del código del hilo de trabajo, ejecutando Font.__del__ en el contexto del hilo de trabajo, lo que provoca RuntimeError.

Hipótesis B (credibilidad media): La pila en el volcado puede reflejar una llamada a __del__ provocada por una operación explícita de del o reasignación de referencia en el hilo de trabajo, en lugar del GC cíclico. Esto requiere verificar si la pila muestra gc.collect() o un recolector de ciclos.

Hipótesis C (credibilidad media): La llamada a Font.__del__ puede ser el resultado de una reacción en cadena tras la destrucción de objetos Tkinter. Por ejemplo, un PhotoImage o CTkImage se libera en un hilo de trabajo, su __del__ desencadena la limpieza de recursos Tk relacionados, involucrando indirectamente a Font.

Evidencia adicional necesaria:

Usar gc.get_referrers() o gc.DEBUG_SAVEALL para confirmar si el objeto Font está en un ciclo de referencias.

Instrumentar threading.current_thread() en Font.__del__ para registrar el hilo de ejecución; o usar faulthandler para registrar el ID del hilo actual al capturar la excepción.

Verificar si hay llamadas a del o reasignaciones que liberen objetos Tkinter en el código del hilo de trabajo.

Confirmar si otras pruebas con ventanas reales (no solo pantalla virtual) pueden reproducir la misma pausa.

Riesgos de otros objetos similares
Objeto	Riesgo	Base
ImageTk.PhotoImage	Riesgo demostrado: La recolección de PhotoImage en un hilo no principal puede causar problemas; en la lista de correo se reporta que PhotoImage es recolectado por GC, causando que la imagen no se muestre o se bloquee . La documentación oficial también señala que es necesario mantener una referencia a PhotoImage para evitar que sea recolectado .	Reportes de la comunidad y documentación
CTkImage	Riesgo posible: CTkImage encapsula PhotoImage de PIL y objetos Tkinter; si su cadena de referencias incluye objetos Tk, la lógica de riesgo es la misma que PhotoImage. No hay reportes públicos de fallos específicos de CTkImage.	Inferencia
Font	Riesgo posible: La pila de esta incidencia apunta a Font, pero la causa raíz no está confirmada. Font contiene referencias a objetos Tk; si se libera en un hilo no principal, la lógica es la misma que la de otros objetos Tk.	Pila de esta incidencia
Objetos tkinter.Variable	Riesgo posible: La discusión en issue39093 menciona que Variable retiene self._tk; la liberación en un hilo no principal también puede desencadenar problemas .	Discusión en lista de correo
Distinción: "Riesgo demostrado" se refiere a casos documentados de fallo o advertencia explícita en la documentación oficial; "Riesgo posible" se refiere a que la ruta de fallo existe en teoría, pero no se ha observado en este proyecto ni en reportes públicos.

¿Es suficiente el arreglo en pruebas?
No suficiente. Razones:

El fixture de pruebas solo controla el momento de activación del GC, no elimina la posibilidad de que los objetos Tkinter sean liberados en hilos no principales.

En producción, las operaciones del usuario (arrastrar y soltar, cambio de tema, cambio de tamaño de ventana) pueden crear y destruir objetos Tk con más frecuencia que en las pruebas, aumentando la probabilidad de activación del GC.

Deshabilitar el GC o controlarlo manualmente en pruebas oculta el problema, no lo expone. Si posteriormente se agrega nuevo código que crea ciclos de referencias, las pruebas no lo detectarán.

Riesgos de deshabilitar el GC en pruebas: fuga de memoria, las pruebas no reflejan el comportamiento real de uso, los resultados de las pruebas pierden valor de referencia.

Opciones y comparación
Opción	Ventajas	Riesgos/Costos
A. Cola de resultados + procesamiento en hilo principal (recomendado)	Resuelve fundamentalmente el problema de hilos: todos los objetos Tk son creados, utilizados y liberados en el hilo principal. Bajo acoplamiento, no requiere refactorización arquitectónica.	Requiere que los hilos de trabajo devuelvan los resultados a través de una cola, y el hilo principal los procese periódicamente con after(). Aumenta ligeramente la complejidad del código, pero es manejable.
B. Creación y liberación explícita de recursos Tk en el hilo principal	Puede resolver localmente el problema de liberación de Font/PhotoImage.	Requiere rastrear todos los objetos Tk que puedan liberarse en hilos de trabajo; es fácil pasar por alto casos límite. No resuelve el problema de GC ejecutándose en hilos de trabajo.
C. Uso correcto de after()	El hilo de trabajo solo escribe en la cola, el hilo principal sondea con after(); es una práctica estándar de Tkinter .	Requiere garantizar que after() se registre en el hilo principal y que el hilo de trabajo no llame directamente a Tk.
D. Uso de mttkinter o solución similar	Envoltura thread-safe existente.	Agrega dependencia, no es mantenida oficialmente, puede introducir nuevos problemas. No recomendado para este proyecto.
Recomendación final
Primera opción: Opción A (cola de resultados + procesamiento en hilo principal). Razones:

Mínimo cambio seguro: Los hilos de trabajo de las herramientas ya existen; solo es necesario agregar una queue.Queue, el hilo de trabajo escribe resultados en la cola (datos puros, no objetos Tk), el hilo principal usa after() para procesar la cola periódicamente, creando o actualizando objetos Tk.

No acopla el motor a Tk: La lógica de procesamiento de imágenes en core/ y tools/ permanece sin cambios; la capa app/ es responsable de transferir resultados de la cola a la GUI.

Compatible con la hipótesis de fallo actual: Ya sea Font, PhotoImage u otros objetos Tk, siempre que se garantice que son creados y liberados en el hilo principal, el riesgo se elimina en la raíz.

Complemento necesario:

Auditar el código de hilos de trabajo para confirmar que no hay llamadas directas o indirectas a Tkinter (incluyendo creación implícita de Font, PhotoImage, etc.).

Agregar una prueba específica de "liberación de objetos Tk en hilo no principal": crear un objeto Font en un hilo de trabajo y liberarlo, verificar que se lanza RuntimeError o que el comportamiento no está definido; luego confirmar que tras la corrección ya no se activa.

Para la incidencia actual, agregar registro en Font.__del__ para confirmar el hilo de ejecución, o usar gc.get_objects() para verificar si Font está en un ciclo de referencias. Si se confirma que no es un ciclo de referencias sino una liberación explícita, la prioridad de la corrección es aún mayor.

No recomendado: Cambiar toda la arquitectura o introducir un framework de GUI thread-safe de terceros. La evidencia actual no respalda la necesidad de una refactorización a gran escala.