Conclusión: La política propuesta (ampliación BICUBIC, reducción LANCZOS, 100% sin remuestreo) es direccionalmente correcta, pero tiene un defecto técnico clave: tratar "100%" simplemente como "sin remuestreo" en pantallas HiDPI provocará desajustes entre el tamaño de visualización y la definición física de píxeles, causando que los usuarios vean una "imagen nítida pero de tamaño incorrecto" o una "imagen suavizada". Se recomienda introducir el concepto de "escala de píxeles del dispositivo (DPR)" en la primera versión, tratando por separado la escala lógica (zoom) y la escala física (asignación de píxeles), y añadir corrección de alfa premultiplicado para imágenes RGBA.

1. ¿Es una buena política? Ventajas y desventajas de cada filtro
BICUBIC (ampliación)

Ventajas: Considera 16 píxeles vecinos, resultando en transiciones suaves, adecuado para ampliar fotografías e imágenes con gradaciones tonales continuas. Menor costo computacional que LANCZOS, respuesta más rápida al hacer zoom .

Desventajas: Ligeramente suavizado en los bordes, las líneas finas y el texto pueden perder nitidez; puede producir un leve efecto de timbre (halo) en bordes de alto contraste.

LANCZOS (reducción)

Ventajas: Basado en núcleo sinc, excelente conservación de detalles y supresión de alias, es el filtro de mayor calidad para reducción .

Desventajas: El costo computacional es notablemente mayor que BICUBIC (la versión de orden superior requiere 36 píxeles vecinos), y en pilas de imágenes grandes puede causar micro-retrasos al arrastrar el zoom; para imágenes pequeñas algunos desarrolladores han reportado que la implementación de LANCZOS en Pillow no es tan buena como BICUBIC .

100% sin remuestreo

Ventajas: Esta es la línea base para la "visualización real de píxeles". Siempre que la relación de píxeles sea 1:1, es lo que los editores de imágenes deben garantizar como mínimo.

Desventajas: Bajo HiDPI, "100%" es un concepto ambiguo (ver abajo).

2. Qué significa exactamente "100%" en HiDPI
En una pantalla con 150% de escala, el sistema operativo generalmente hace que 1 píxel lógico (unidad Tk) corresponda a 1.5 píxeles físicos. Si en este momento "100%" significa "1 píxel de imagen = 1 píxel lógico", entonces el renderizador ampliará la imagen 1.5× y la dibujará en el framebuffer, y luego el sistema la reducirá a la pantalla física—esto equivale a una ampliación no solicitada por el usuario seguida de una reducción del sistema, lo que causa emborronamiento.

Los usuarios esperan que "100%" signifique "veo una correspondencia 1:1 entre píxeles de imagen y píxeles físicos de la pantalla". En pantallas HiDPI esto requiere que el visor consulte el DPR (Device Pixel Ratio) y calcule la escala física real como zoom × DPR. Solo cuando zoom × DPR = 1 se puede llamar 100% real. En la práctica, Lightroom y Photoshop bajo pantallas 4K con 150% de escala presentan el problema de "el 100% se ve más pequeño de lo esperado", precisamente porque el marco maneja el DPR de forma inconsistente .

Recomendación: Internamente usar "escala física" como fuente de verdad. La interfaz muestra el porcentaje lógico (escala física ÷ DPR), pero al renderizar se usa el tamaño físico para decidir el filtro.

3. Problemas al ampliar imágenes con contenido especial
Texto y líneas finas: BICUBIC ampliará el suavizado de bordes, el texto se vuelve "borroso". En este caso NEAREST (vecino más cercano) puede preservar mejor la apariencia de píxeles duros, pero no es adecuado para fotografías.

Píxeles individuales: Cualquier filtro de interpolación "inventará" píxeles alrededor. Si el usuario necesita inspeccionar píxeles individuales (como retoque o verificación de artefactos), a partir de cierto nivel de zoom (como ≥400%) se debe cambiar a NEAREST.

RGBA y transparencia: Pillow al reducir imágenes RGBA no tiene en cuenta el alfa por defecto, los píxeles completamente transparentes con colores oscuros (como (0,0,0,0)) "contaminarán" los píxeles semitransparentes vecinos, produciendo halos oscuros . Este es un defecto conocido de Pillow.

Bordes de alto contraste: Los bordes negro-blanco bajo BICUBIC/LANCZOS pueden producir sobreoscilación (halo/ringing).

4. ¿Es necesario cambiar de filtro por niveles de zoom?
No se recomienda hacer una conmutación automática compleja en la primera versión. Una estrategia pragmática es:

zoom < 100%: LANCZOS (reducción).

100% ≤ zoom < 400%: BICUBIC (ampliación).

zoom ≥ 400%: NEAREST (visualización de píxeles, facilitando ver la estructura real de píxeles).

Esta es una tabla de decisión de tres tramos, fácil de implementar y probar, también fácil de explicar a los usuarios. En el futuro se puede añadir una opción manual "priorizar suavidad/priorizar píxeles duros".

5. Cómo evitar halos, contaminación de color transparente y errores de redondeo
Halo y transparencia (lo más crítico): Para RGBA, no se puede llamar directamente a Image.resize() de Pillow sobre la imagen original. La práctica correcta es:

Alfa premultiplicado: Convertir RGB a R×A, G×A, B×A, luego interpolar. Después de interpolar, dividir por el nuevo alfa para recuperar el color. Esto evita que los píxeles transparentes contaminen a los semitransparentes .

Si no se hace premultiplicado, al menos se debe rellenar el color de los píxeles completamente transparentes antes de interpolar (usar el color promedio de los píxeles opacos circundantes), pero esto es un remedio temporal, no tan limpio como el premultiplicado.

Errores de redondeo:

Todas las coordenadas de recorte y destino de dibujo deben redondearse a enteros antes de pasarse a Canvas. Tk Canvas acepta floats pero el renderizado final se rasteriza, los floats pueden causar desplazamientos de medio píxel.

No calcular repetidamente las coordenadas de la ventana gráfica usando acumulación de floats; en su lugar, cada fotograma recalcula a partir del origen y el zoom actuales.

6. Pruebas objetivas recomendadas
Prueba	Método	Criterio de aprobación
Fidelidad al 100%	Cargar una imagen de cuadrícula de píxeles con píxeles rojo/verde alternados, DPR=1, zoom=100%	Captura de pantalla píxel por píxel, comparar con el original: cada píxel RGB debe ser idéntico, sin desplazamiento
Sin desplazamiento al reducir	Imagen con cuadrícula de líneas de 1px, reducir a 50% y 25%	Las líneas no deben desaparecer ni engrosarse; verificar simetría de posiciones de muestreo
Transparencia sin halo oscuro	RGBA: fondo completamente transparente negro (0,0,0,0), primer plano blanco opaco, reducir	Los píxeles semitransparentes en los bordes no deben tener componentes oscuros; comparar con referencia de GIMP
Estabilidad de ampliación	Ampliar texto/líneas finas a 200%, 400%, 800%	A 400% y superiores cambiar a NEAREST, los bloques de píxeles deben ser visibles y alineados
Consistencia HiDPI	Ejecutar misma operación de zoom con DPR=1 y DPR=1.5	El tamaño lógico de visualización debe ser consistente; la nitidez no debe degradarse por doble escalado
7. Calidad visual vs resolución real
Este punto debe quedar claro en la documentación del producto: La ampliación nunca recupera información. LANCZOS y BICUBIC solo "adivinan razonablemente" los valores de píxeles faltantes según los píxeles existentes. Ampliar una foto de 1000px al 400% para ver "detalles", esos detalles son inventados por el algoritmo, no son información real de la imagen. El valor del visor es permitir al usuario ver con precisión la apariencia de la imagen al nivel de píxel actual, no "mejorar la imagen".

Decisión final (recomendación para primera versión)
Introducir DPR: Calcular la escala física con escala_física = zoom_lógico × DPR. Solo cuando escala_física = 1 se omite el remuestreo; de lo contrario se aplica la siguiente tabla según la escala física.

Tabla de filtros: <1 → LANCZOS; [1, 4) → BICUBIC; ≥4 → NEAREST.

Obligatorio para RGBA: Premultiplicar alfa antes de interpolar, o al menos rellenar los píxeles completamente transparentes antes de interpolar.

Redondeo de coordenadas: Todas las coordenadas de Canvas se redondean a enteros antes de dibujar.

No hacer conmutación automática compleja ni "recuperación de detalles con IA" en la primera versión; primero garantizar que las tres líneas base—visualización correcta al 100%, sin halo en transparencias, sin desplazamiento en reducción—pasen las pruebas.