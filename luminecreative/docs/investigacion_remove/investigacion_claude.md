Antes de la arquitectura, qué verifiqué y qué no. Lo de rembg, sus providers y las licencias lo comprobé con búsqueda. Los patrones de otros proyectos (OpenCV DNN, MMSegmentation/Detectron2, Hugging Face, PyMatting) vienen de mi conocimiento previo y no los verifiqué en esta sesión.

0. Hallazgos que condicionan el diseño
rembg ya es un sistema de sesiones. Una sesión encapsula la carga del modelo, la configuración de GPU y la lógica de predicción. Por eso el adaptador debe crear la sesión una vez y reutilizarla, nunca por llamada. 
tessl
Los providers de ONNX Runtime se pasan como lista priorizada. new_session acepta una lista de providers, por ejemplo DirectML seguido de CPU. El patrón "lista de preferencia con fallback" ya existe, pero hay que verificar qué provider quedó realmente activo, porque ORT puede caer a CPU con solo un warning. 
pypi
rembg ya mezcla modelos distintos bajo un mismo runtime. Su catálogo incluye varias variantes de BiRefNet y bria-rmbg. BiRefNet y BRIA son modelos y rembg es un runtime. Tu primer diagrama los pone al mismo nivel, y es el principal defecto que le veo. 
pypi
La licencia es un criterio de selección de modelo. Los pesos de RMBG-2.0 usan CC-BY-NC-4.0, es decir, no comercial. Si la salida se usa comercialmente, BRIA exige licencia aparte. Como mi recuerdo es que BiRefNet y U2Net son permisivos (MIT y Apache-2.0), verifícalo antes de decidir. ModelSpec debe cargar la licencia como dato. 
huggingface
Los exports ONNX de modelos grandes pesan cientos de MB. El export de RMBG-2.0 ocupa unos 977 MB en FP32, 490 MB en FP16 y 350 MB cuantizado. Eso afecta descarga, RAM y tiempo de carga, y justifica caché con límite de memoria. 
huggingface
1. Arquitectura propuesta
Crítica de tus dos propuestas

Propuesta A (Remover → Backend → Rembg/BiRefNet/BRIA):

Mezcla modelo y runtime en el mismo nivel de jerarquía.
Hace que el backend devuelva RGBA, lo que esconde la máscara. Sin máscara no puedes refinar, editar a mano ni guardarla para V4.

Propuesta B (MaskGenerator → MaskRefiner → AlphaMatting → RGBAComposer):

Va en la dirección correcta, pero como pipeline fijo de 4 etapas es prematuro.
MaskRefiner y AlphaMatting se solapan: el matting es un refinamiento que usa la imagen como guía.

Convergen así: MaskGenerator es el backend, pero devolviendo un matte y no RGBA. El refinamiento es una lista opcional de MatteRefiner. RGBAComposer es una función pura.

Veredicto de patrones
Patrón	¿Sí?	Cómo
Adapter	✅ núcleo	Cada librería (rembg, onnxruntime, torch) se envuelve en un adaptador al contrato propio
Strategy	✅ pero no aparte	El backend es la estrategia. No construyas dos jerarquías
Factory	✅ mínimo	Una función create_backend(config), sin jerarquía de fábricas
Registry	✅ pequeño y lazy	dict[id → ModelSpec + entrypoint "módulo:clase"], sin importar nada hasta usarlo. Sin auto-descubrimiento mágico en V1
Dependency Injection	✅ clave	Inyección por constructor. Sin framework de DI, el composition root de la app cablea
Pipeline	❌ ahora, ✅ interno en V3	Como lista de refiners dentro del remover. No lo confundas con la cadena de efectos de tu app
Backend abstraction	✅	A nivel imagen → matte
Model abstraction	✅ como dato	ModelSpec (dataclass), no jerarquía de clases
Mask abstraction	✅	Matte, un value object pequeño
Decorator (extra)	✅	FallbackBackend, TimingBackend, EnsembleBackend componen backends sin tocar al remover
Null Object (extra)	✅	NullContext para cancelación y progreso
Diagrama conceptual
                     ┌──────────────── App (GUI, threads, EventBus, export) ────────────────┐
                     │  composition root: crea config, provider, remover; ejecuta en worker │
                     └───────────────┬──────────────────────────────────────────────────────┘
                                     │ inyecta (DI)
┌────────────────────────────────────▼───────────────────────────────────────────────────┐
│ NÚCLEO (puro: sin GUI/threading/rembg/onnx/torch)                                      │
│                                                                                        │
│  ImageOperation ◄── BackgroundRemover ──► compose_rgba() (función pura)                │
│                         │      │                                                       │
│                         │      └──► MatteRefiner* (V3+)  [lista opcional]              │
│                         ▼                                                              │
│                 BackendProvider (Protocol)  ── acquire() ──► lease                     │
│                         │                                                              │
│  OperationContext (cancelación + progreso, Protocol)       Matte · ModelSpec · errors  │
└─────────────────────────┼──────────────────────────────────────────────────────────────┘
                          │ implementado por
┌─────────────────────────▼──────────────────────────────────────────────────────────────┐
│ INFRAESTRUCTURA                                                                        │
│  ModelManager (caché LRU, leases, device)  ──  ModelRegistry  ──  ModelStore (pesos)   │
│        │                                                                               │
│  SegmentationBackend (Protocol)                                                        │
│   ├─ RembgBackend(model_name)      ← V1                                                │
│   ├─ OnnxSegBackend(ModelSpec)     ← V2 (BiRefNet/BRIA directo, sin rembg)             │
│   ├─ TorchBackend                  ← futuro                                            │
│   └─ FakeBackend                   ← tests                                             │
│  Decoradores: Fallback / Timing / Ensemble / Router                                    │
└────────────────────────────────────────────────────────────────────────────────────────┘

Regla de dependencias: las flechas apuntan al núcleo. Solo el registry referencia clases concretas, y lo hace con strings de entrypoint cargados de forma lazy.

2. Responsabilidades y qué NO debe hacer cada componente (puntos 3 y 4)
Componente	Responsabilidad	NO debe
BackgroundRemover	Orquestar: validar → normalizar → pedir backend → matte → refiners → componer → validar salida. Cumplir ImageOperation	Importar rembg/onnx/torch, crear hilos, cargar modelos por su cuenta, leer/escribir disco, conocer GUI
SegmentationBackend (adaptadores)	image → Matte al tamaño de la entrada (resize, normalización, inferencia, upsample internos). Traducir excepciones de terceros	Devolver RGBA, decidir el modelo, cachear sesiones, conocer políticas de fallback o el orden de los refiners
MatteRefiner	(image, matte) → matte (guided filter, morfología, feather, matting)	Correr un modelo de segmentación ni componer RGBA
compose_rgba	Combinar RGB original y matte en alpha straight, según la política de alpha previo	Tener estado ni hacer I/O
ModelManager / BackendProvider	Caché de backends por clave (modelo, runtime, device, opciones), leases, límite de memoria, descarga de sesiones	Conocer imágenes, correr inferencia, conocer GUI
ModelRegistry	Mapear id → ModelSpec + entrypoint, de forma lazy	Importar dependencias pesadas al registrarse
ModelStore	Localizar, verificar checksum y (opcionalmente) descargar pesos	Descargar sin permiso explícito
RemovalConfig / ModelSpec / DeviceSpec	Datos inmutables, serializables y picklables	Contener lógica ni recursos vivos (sesiones, tensores)
OperationContext	Contrato de cancelación cooperativa y progreso por etapas	Saber quién escucha (GUI, log, CLI)
Decoradores	Componer comportamiento (fallback CPU, timing, ensemble) sobre cualquier backend	Reimplementar el backend
3. Interfaces recomendadas (puntos 5)

Un boceto de contratos, no la implementación. Aplico tu convención de docstring de cabecera:

python
"""
imaging/segmentation/ports.py

Responsabilidad:
- Definir los contratos (Protocol) entre BackgroundRemover y la infraestructura.
- Definir los tipos de valor compartidos (Matte, BackendInfo).

No conoce:
- rembg, onnxruntime, torch, GUI, threads, disco.

Notas:
- Solo contratos y tipos; sin lógica de negocio.
"""
from dataclasses import dataclass
from typing import Any, ContextManager, Mapping, Protocol
import numpy as np
from PIL import Image


@dataclass(frozen=True)
class Matte:
    alpha: np.ndarray            # uint8, (H, W), mismo tamaño que la imagen de entrada
    meta: Mapping[str, Any]      # model_id, runtime, device activo, tiempos


class OperationContext(Protocol):
    def check_cancelled(self) -> None: ...                    # lanza OperationCancelledError
    def report(self, stage: str, fraction: float | None = None) -> None: ...


class SegmentationBackend(Protocol):
    info: "BackendInfo"          # id, ModelSpec, device activo, thread_safe, soporta_batch
    def predict(self, image: Image.Image, ctx: OperationContext) -> Matte: ...
    def close(self) -> None: ...


class MatteRefiner(Protocol):
    name: str
    def refine(self, image: Image.Image, matte: Matte, ctx: OperationContext) -> Matte: ...


class BackendProvider(Protocol):
    def acquire(self, config: "RemovalConfig") -> ContextManager[SegmentationBackend]: ...

Y la fachada pública:

python
class BackgroundRemover(ImageOperation):
    def __init__(self, provider, config, refiners=(), composer=compose_rgba): ...
    def prepare(self, ctx=None) -> None                     # carga el modelo (opcional)
    def generate_matte(self, image, ctx=None) -> Matte      # etapas 1-4
    def compose(self, image, matte) -> Image.Image          # etapa 5 pura
    def remove(self, image, ctx=None) -> RemovalResult      # imagen + matte + reporte
    def apply(self, image) -> Image.Image                   # contrato ImageOperation

Exponer generate_matte y compose por separado es la decisión que habilita V4: la app guarda el matte, el usuario lo retoca, y se recompone sin volver a inferir.

Uso Protocol y no ABC para que los fakes de test no necesiten heredar nada.

Layout sugerido:

tools/background_remover.py queda como fachada que reexporta, para no romper imports.
Un paquete imaging/segmentation/ con types, errors, ports, compose, remover, registry, manager, store, backends/, refiners/ (vacío hasta V3).

Agrega un test que escanee imports y falle si el núcleo importa tkinter, customtkinter, threading, rembg, onnxruntime o torch. Así tus principios se verifican solos.

4. Flujo de datos (punto 6)
PIL.Image ─► [1 validar + normalizar] ─► RGB uint8 (+ alpha previo si existía)
          ─► [2 acquire(backend)]     lazy load, caché, lease
          ─► [3 backend.predict]      resize al tamaño del modelo → inferencia → upsample a tamaño original
                                      ─► Matte (H,W) uint8
          ─► [4 refiners*]            (V3+) usan imagen original como guía
          ─► [5 compose_rgba]         RGB original + alpha, straight
          ─► [6 validar salida]       invariantes del contrato
          ─► PIL.Image RGBA

ctx.check_cancelled() y ctx.report(etapa) entre cada paso.

Matiz importante: la inferencia ocurre a la resolución del modelo (BiRefNet trabaja alrededor de 1024 px), así que el matte sale suavizado al volver a tamaño completo. Ahí es donde V3 (refinamiento a resolución completa guiado por la imagen) gana calidad real, sobre todo en cabello.

5. Contrato de apply(image) (punto de contrato)

Precondiciones:

La entrada es PIL.Image.Image con tamaño > 0.
Modos admitidos: RGB, RGBA, L, P. CMYK y 16 bits se convierten, pero la gestión de color es responsabilidad de la app.
La orientación EXIF la resuelve el cargador de la app. El remover no toca EXIF.

Postcondiciones e invariantes:

Devuelve PIL.Image modo "RGBA" con tamaño idéntico a la entrada.
No muta la entrada y la salida no comparte buffers con ella.
Alpha straight (no premultiplicado), 8 bits, sin NaN ni valores fuera de rango.
Los canales RGB no se alteran: se conservan los colores originales, incluso donde alpha = 0. Limitación conocida: los bordes semitransparentes arrastran color de fondo (fringe). La descontaminación de color es trabajo de V3.
Si la entrada ya tenía alpha, el resultado es alpha_modelo × alpha_previo. Hay que decidir y documentar esto, porque cambia el resultado al reprocesar.
Determinismo: misma entrada + config + versión de backend + device produce la misma salida (en GPU, dentro de una tolerancia documentada).
Sin efectos laterales: no escribe archivos, no crea hilos y no usa red salvo descarga explícitamente habilitada.
Solo lanza subclases de BackgroundRemovalError y nunca devuelve resultado parcial.
Cancelación: lanza OperationCancelledError y deja el sistema utilizable.
Seguridad entre hilos: una instancia puede llamarse desde cualquier hilo. Si el backend no es thread-safe, él mismo serializa con un lock interno. Proteger un recurso no es "conocer threading de la app".
6. Gestión de modelos (punto 7)

Separar tres ejes: modelo (pesos y metadatos) × runtime (rembg/onnx/torch) × dispositivo. Nombrar clases BiRefNetBackend mezcla los tres.

ModelSpec (dato inmutable): id, familia, fuente de pesos, checksum, resolución de entrada, mean/std, licencia y bandera de uso comercial. La app puede mostrar advertencias de licencia sin que el remover sepa nada.

Carga lazy:

Ningún import pesado ocurre al arrancar la app.
BackgroundRemover.__init__ es barato.
El modelo se carga en el primer apply o en un prepare() explícito, que la app puede llamar en su worker con progreso.

Descargas:

rembg descarga a su carpeta de caché en el primer uso. En una app de escritorio eso es una sorpresa.
ModelStore es offline-first: si faltan pesos lanza ModelFilesMissingError, y la GUI decide si descargar.

Caché:

ModelManager indexa por (spec.id, runtime, device, hash_opciones).
Es una instancia creada en el composition root, no un singleton global.
LRU con presupuesto de memoria.
with manager.acquire(cfg) as backend: entrega un lease, de modo que una evicción nunca descarga un modelo en plena inferencia.

GPU/CPU:

DeviceSpec(preferencia, allow_fallback).
Tras crear la sesión se verifica el provider realmente activo y se expone en info.active_device.
Con allow_fallback=False y GPU ausente se lanza DeviceUnavailableError. Con True se cae a CPU y se registra.
El primer inferir es lento (optimización de grafo y kernels). Ofrece warmup() opcional.

Multiprocessing:

Las sesiones no se serializan, pero RemovalConfig sí. Cada proceso hijo recibe config y construye su propio backend.
En Windows el método es spawn, así que los workers importan desde cero.
Con N procesos hay que repartir los hilos intra-op de ORT (cores/N) para no sobresuscribir CPU.
En GPU suele rendir más un solo proceso dueño de la GPU que varios compitiendo.

Memoria y resoluciones grandes:

Matte en uint8 como tipo de intercambio. Un float32 a 8000×8000 son 256 MB contra 64 MB.
max_pixels en config, para fallar pronto con ImageTooLargeError.
Una función estimate_peak_memory(size, spec) permite avisar antes de que ocurra el OOM.
Los refiners pueden usar float internamente, pero entregan uint8.

Batch:

Se orquesta fuera del remover: el runner de la app llama apply N veces reutilizando el mismo backend cacheado.
Más adelante, predict_batch como capacidad opcional con implementación por defecto en bucle.

Cancelación y progreso:

Cooperativos y por etapas vía OperationContext.
Una sola inferencia es prácticamente no interrumpible, así que se cancela entre etapas (y entre tiles en V3+).
La app implementa el contexto traduciendo report() a sus eventos. El remover solo ve el Protocol.
7. Gestión de errores (punto 8)
BackgroundRemovalError                      (base; lleva .code estable, .stage, .backend_id)
├─ ConfigurationError
├─ DependencyError
│   └─ MissingDependencyError               (paquete ausente; .package, .install_hint)
├─ ModelError
│   ├─ ModelNotFoundError                   (id desconocido en el registry)
│   ├─ ModelFilesMissingError               (pesos ausentes / descarga deshabilitada)
│   └─ ModelLoadError                       (corrupto, checksum inválido)
├─ InputError
│   ├─ InvalidImageError                    (tipo/modo/tamaño inválido)
│   └─ ImageTooLargeError
├─ BackendError
│   ├─ BackendUnavailableError
│   ├─ DeviceUnavailableError               (GPU no disponible y sin fallback)
│   ├─ InsufficientMemoryError              (RAM/VRAM)
│   ├─ InferenceError
│   └─ UnexpectedBackendError               (envuelve lo imprevisto, con __cause__)
├─ OutputError
│   └─ InvalidOutputError                   (shape, dtype, rango, NaN)
└─ OperationCancelledError                  (la GUI lo trata distinto de un fallo)

Reglas:

Traducción en la frontera. Cada adaptador captura las excepciones de terceros y relanza con raise ... from exc. Nunca se filtran tipos de onnxruntime o torch.
OOM en un solo lugar. ORT reporta fallos de memoria como excepciones genéricas, así que clasificarlos implica inspeccionar el mensaje. Esa heurística frágil vive en un único módulo, con tests.
Códigos estables, no texto. Las excepciones llevan code y parámetros, y la GUI los mapea a texto (y a idioma). El núcleo no contiene mensajes de interfaz.
El remover no reintenta. El fallback de GPU a CPU o a un modelo menor lo hace FallbackBackend (decorador), configurable desde fuera.
8. Testing (punto 9)

Unit (rápidos, sin modelos)

BackgroundRemover con FakeBackend configurable: máscara círculo, constante o degradado, y modos de fallo (OOM, NaN, shape incorrecto, lento, cancelable).
compose_rgba como función pura, incluyendo la política de alpha previo.
Tests de propiedades (hypothesis): para cualquier tamaño y modo válido se cumple RGBA, mismo tamaño y no mutación.
Traducción de errores con excepciones falsas de terceros.
El test de imports del núcleo.

Contract suite reutilizable. Una única batería (BackendContractSuite) que se ejecuta contra cada backend (fake, rembg, onnx): tamaño de salida, dtype, rango, determinismo y close(). Añadir un backend nuevo es heredar la suite. Los tests con modelo real llevan marker @pytest.mark.model.

Integración. Un modelo pequeño real en CI (por ejemplo u2netp, de pocos MB). Los modelos grandes y GPU son opt-in (slow, gpu).

Golden images, para "no empeorar el cabello":

Un conjunto curado de 30–60 imágenes por categoría: cabello, pelaje, bordes finos, bajo contraste, transparencias, logos o arte plano, alta resolución, y casos raros (escala de grises, paleta, ya recortadas).
Cada una con un matte de referencia revisado a mano.
No se comparan bytes de PNG. Se comparan métricas: IoU, MAE de alpha, F-measure de borde y las clásicas de matting (SAD, MSE, Gradient, Connectivity).
Métrica por zona: error medido solo en la banda "incierta" (dilatar menos erosionar la referencia). Ahí vive el cabello, y es lo que detecta la regresión que mencionas.
Umbrales por categoría, contra un baseline JSON versionado con el id y la versión del modelo.
Mejoras son bienvenidas, pero actualizar el baseline exige un cambio explícito y revisado (ratchet).
Guarda las imágenes en Git LFS o DVC, no en el repo principal, y revisa derechos de uso.

Regresión. Todo bug reportado agrega su imagen al conjunto. Al fallar se genera un reporte HTML con comparación lado a lado y overlay sobre fondos blanco, negro y de color (revela fringes que el damero oculta).

9. Benchmark (punto 10)

Separado de los tests, porque el tiempo es ruidoso. Se corre local o nocturno, no en CI compartido.

Mide: latencia p50/p95, throughput, RAM y VRAM pico, y arranque en frío vs. caliente (carga vs. inferencia).
Matriz: resoluciones (≈1, 4, 12 y 24 MP) × dispositivo × tamaño de batch.
Método: calentamiento, N ≥ 10 repeticiones, y registro del entorno (CPU/GPU, versión de ORT, driver).
Instrumentación: TimingBackend como decorador, sin tocar los backends.
Salida: JSON comparable entre ejecuciones, con umbrales holgados (por ejemplo fallar si la latencia empeora >25% en la misma máquina).
Decisión de modelo: una tabla calidad (golden) vs. velocidad vs. memoria. Un modelo nuevo solo se "promueve" si pasa el gate de calidad por categoría y entra en tu presupuesto de rendimiento.
10. Roadmap (punto 11)
Versión	Qué se agrega	Qué NO cambia	Criterio de salida
V0	Dataset golden + harness de métricas sobre el comportamiento actual de rembg	Todo el código	Baseline guardado
V1	Puertos, errores, Matte, compose_rgba, RembgBackend (usando only_mask=True para obtener el matte), manager básico, fakes y contract suite	La API de apply hacia la app	Mismos resultados que V0 dentro de tolerancia
V2	OnnxSegBackend directo (BiRefNet; BRIA solo si la licencia lo permite)	BackgroundRemover y la app	Supera el baseline en categorías clave sin romper rendimiento
V3	MatteRefiners: guided filter, morfología, feather, descontaminación de color, matting a resolución completa	Backends	Mejora medible en la banda de cabello
V4	La app guarda el Matte, edita (pincel, trimap) y recompone. Opcional: un puerto separado InteractiveSegmenter (estilo SAM)	SegmentationBackend	Editar no re-infiere
V5	EnsembleBackend y RouterBackend (elegir modelo por tipo de imagen)	Todo	Siguen siendo SegmentationBackend

El puerto interactivo (V4) es aparte a propósito: un segmentador por prompts tiene otra firma, y forzarlo dentro de SegmentationBackend ensucia el contrato.

11. Decisiones irreversibles vs. reversibles (punto 12)

Difíciles de revertir; decídelas con cuidado ahora:

El backend devuelve matte al tamaño de la entrada (uint8), no RGBA. Todo V3–V5 depende de esto.
Convención de alpha straight, RGB original intacto y política de alpha previo.
Nombres y códigos públicos de la jerarquía de excepciones, porque la GUI se acoplará a ellos.
RemovalConfig y ModelSpec son datos picklables y serializables (multiproceso y benchmarks lo necesitan).
La firma de OperationContext (cancelación y progreso).
PIL en la frontera pública y NumPy dentro.
Exponer generate_matte / compose como pasos separados.

Fáciles de revertir:

Qué librería de inferencia se usa, incluso quitar rembg del todo.
Nombres de clases concretas y el layout de carpetas.
Mecanismo del registry (dict hoy, entry points mañana).
Política de caché (LRU, tamaños, evicción).
Estrategia de tiling.
Cuántos y cuáles refiners se encadenan.
Riesgos y puntos a validar
Licencias. Confirma la licencia de cada modelo candidato antes de V2 si el resultado es comercial. Los datos que cité son de las fichas que encontré, no un dictamen legal.
Versión de bria-rmbg en rembg. No pude confirmar con certeza qué versión empaqueta, y no es lo mismo que RMBG-2.0.
Datos golden. Sin un conjunto representativo y con mattes revisados, la estrategia de regresión pierde su sentido. Es el trabajo más caro de todo el plan.

Una pregunta para cerrar el diseño: ¿cómo está definido hoy ImageOperation.apply? Necesito saber si acepta kwargs extra o si el OperationContext debe inyectarse por constructor, porque eso cambia el punto 5 de forma pequeña pero real.