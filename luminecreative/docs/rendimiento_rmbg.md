# Rendimiento de RMBG (quitar fondo)

> **Estado de las mediciones:** en el entorno donde se hizo este trabajo **no está instalado `rembg`, no hay
> modelo `u2net.onnx` y no hay red para descargarlo**. Por eso NO hay medidas del coste del modelo (carga,
> inferencia, Execution Provider real, memoria con el modelo). Abajo se separa lo **verificado**, lo
> **medido** y lo **pendiente de medir**. No se extrapola ninguna cifra.

## 1. Causa de la lentitud

**Verificado leyendo el código original (zip entregado):**
- `app/application.py`: `registry.register("remove_background", lambda: BackgroundRemover())` → una instancia
  nueva por operación.
- `tools/background_remover.py`: llamaba a `remove(buffer.getvalue())` **sin `session`**.

**Conocimiento de la API de rembg 2.0.x (NO verificado aquí, `rembg` no está instalado):** si `remove` no recibe
`session`, crea una con `new_session()` en cada llamada, es decir, carga el modelo ONNX desde disco y crea la
`InferenceSession` en cada clic. Es la causa probable principal; **su peso real frente a la inferencia está sin
medir.** No se asume que el cuello de botella sea la CPU.

## 2. Qué se cambió

- `RembgSessionManager` (en `tools/background_remover.py`): sesión con carga diferida, un `Lock` (una
  inicialización y una inferencia a la vez), errores de inicialización traducidos a `ProcessingError` y **no
  cacheados**, `close()` que no se cuelga si hay una inferencia en curso.
- `app/application.py` crea **un** gestor en `DesignApplication.run`, lo inyecta en `build_tool_registry` y lo
  cierra al salir. Sin singleton global. `remove_fn` sigue funcionando (no toca la sesión).
- La sesión se crea en el hilo del `BackgroundTaskRunner` (primer uso), nunca al arrancar la GUI. No se añadió
  ningún hilo. Modelo sin cambios: `u2net` (el que rembg usa por omisión). No se activó GPU.
- Progreso por etapas (`core/progress.py`, `BackgroundTaskRunner`, `DesignController`, `StatusPanel`): fracciones
  0-1 monotónicas, entregadas por cola en `drain()`. La inferencia no inventa porcentaje.
- Corrección en esta revisión: el resultado de RMBG **perdía el PPI** (y el perfil ICC) de la imagen; ahora se
  traspasan de la entrada.

## 3. Medido (sin modelo)

`python scripts/benchmark_rmbg.py` con una «inferencia» que devuelve los bytes sin tocarlos. Solo mide lo que
rodea al modelo (codificar PNG y decodificar/pasar a RGBA) y la memoria del proceso **sin modelo**.
Linux, Python 3.13, 2 CPU, una sola corrida por tamaño; son órdenes de magnitud, no garantías.

| Entrada | Preparar (PNG) ms | Componer (RGBA) ms | Total ms | RSS MB |
|---|---:|---:|---:|---:|
| 640×480 | 11-19 | 4-5 | 16-23 | 64 |
| 1920×1080 | 73-78 | 30-32 | 103-109 | 187 |
| 4000×3000 | 356-398 | 160-172 | 517-570 | 209 |

Lectura honesta: con fotos grandes, codificar y decodificar PNG ya cuesta ~0,5 s **antes** de contar la
inferencia (y rembg repite internamente su propia decodificación/codificación). Esto es coste real de la
aplicación, aparte del modelo.

## 4. Pendiente de medir (necesita rembg + modelo)

No hay cifras para: tiempo de carga del modelo, inferencia, comparación antes/después (sesión nueva por
clic frente a sesión reutilizada: ejecuciones 1 fría, 2 y 3), Execution Provider activo, memoria con el modelo
cargado ni bloqueo de la interfaz con el modelo real.

```
pip install -r requirements.txt
python scripts/benchmark_rmbg.py --real --sizes 640x480,1920x1080,4000x3000
LUMINE_REAL_RMBG=1 pytest tests/test_rmbg_real_model.py -s     # pruebas opcionales con el modelo real
```
`--real` imprime la comparación «antes» (sin sesión) frente a «después» (sesión compartida), el provider activo
(`session.inner_session.get_providers()`) y la RSS. Pega esa salida aquí para completar el informe.

## 5. Límites conocidos

- Las proporciones de la barra por etapas (`_STAGES`) son provisionales hasta medir con el modelo real: marcan
  avance confirmado, no tiempo estimado.
- Durante la inferencia la barra no se mueve (ONNX Runtime no informa avance); solo cambia el texto.
- La liberación de la sesión al cerrar espera como máximo 2 s a una inferencia en curso.
