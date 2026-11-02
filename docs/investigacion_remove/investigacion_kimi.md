## Investigacion kimi

Investigación: Estado del arte en eliminación de fondos, image matting y segmentación saliente (2018–2026)
Voy a realizar búsquedas exhaustivas en paralelo sobre los modelos, datasets y benchmarks clave, y luego sintetizaré todo en un informe estructurado.

Search 2025 2026 matting advances datasets license info
Buscar en la Web（16 resultados）
Buscar en la Web（18 resultados）
Buscar en la Web（18 resultados）
Buscar en la Web（18 resultados）
Buscar en la Web（19 resultados）
Buscar en la Web（20 resultados）
Buscar en la Web（17 resultados）
Buscar en la Web（19 resultados）
Pensamiento completado
He recopilado información sólida sobre los pilares (U2-Net, DIS/IS-Net, BiRefNet, RMBG, ViTMatte, MODNet, RVM, MAM, benchmarks y datasets). Ahora busco los desarrollos más recientes (2024–2026) para cerrar el estado del arte.

Thorough 4000‑Word Report
Buscar en la Web（14 resultados）
Buscar en la Web（18 resultados）
Buscar en la Web（18 resultados）
Pensamiento completado
Tengo material suficiente. Ahora sintetizo todo en el informe completo y lo guardo como documento descargable.

Report on Hidden Rounds with Rhemann Benchmark and U2-Net
Ejecutar código Python
Compose and Deliver Markdown Report via Python
Ejecutar código Python
Pensamiento completado
Estado del arte: Background Removal, Image Matting y Salient Object Detection (2018–2026)
Nota de método: distingo explícitamente [EVIDENCIA] (respaldado por papers/benchmarks/repositorios citados) de [OPINIÓN] (mi juicio de ingeniería). El informe completo también está guardado como documento al final.
1. Timeline del desarrollo tecnológico
Hojas
Año	Hito	Relevancia práctica
2017	Deep Image Matting (DIM, CVPR'17) + Adobe Composition-1k	Establece el paradigma trimap-based y el benchmark matting estándar
2018–2019	AlphaGAN, IndexNet (ICCV'19), GCA Matting, BASNet	Primeras CNNs end-to-end para alpha matting y SOD moderno
2020	U2-Net (Pattern Recognition) · FBA Matting · Background Matting "Green Screen" (CVPR'20)	U2-Net se vuelve el estándar de-facto de background removal (base de rembg, Pixelmator, etc.)
2020–2022	MODNet (AAAI'22, arXiv 2020); BSHM	Portrait matting trimap-free en tiempo real (67 FPS a 512²)
2021	BackgroundMattingV2 (CVPR'21) · HDMatt · MG Matting · Human-2k, SIM datasets	BGMv2: 30 FPS en 4K guiado por frame de fondo; llegan los datasets HR de personas
2021	RVM — Robust Video Matting (WACV'22, arXiv 2021, ByteDance)	Video matting recurrente, 76 FPS en 4K, sin inputs auxiliares
2021	AIM-500 (IJCAI'21): primer benchmark de imágenes naturales reales	Antes todo era composición sintética
2022	DIS + IS-Net (ECCV'22) + DIS5K	Define Dichotomous Image Segmentation y la métrica HCE
2022	InSPyReNet (ACCV'22) · PP-Matting/V2 (PaddleSeg)	SOD de alta resolución; matting industrial trimap-free
2023	SAM (ICCV'23) · Matte Anything · Matting Anything (MAM) · MatteFormer	Era de foundation models: matting interactivo sobre SAM
2023	ViTMatte (arXiv 2023; pub. Information Fusion 2024)	SOTA con amplio margen en Composition-1k con ViT plano preentrenado
2024	BiRefNet (CAAI AIR'24) · BRIA RMBG-1.4 → RMBG-2.0	Nuevo SOTA open-source en DIS; RMBG-2.0 se vuelve referencia comercial
2024	SAM 2 + SA-V dataset (51K videos)	Segmentación promptable unificada imagen+video; 6× más rápido que SAM en imagen
2024	SDMatte (CVPR'24): unifica matting automático e interactivo con ViTs preentrenados	—
2025	ZIM (ICCV'25, Highlight): matting zero-shot sobre arquitectura SAM; dataset SA1B-Matte	Zero-shot real conservando generalización
2025	MatAnyone (CVPR'25); VM800 dataset	Video matting con memoria consistente; supera a RVM en todos los benchmarks
2025–26	MatAnyone 2 (CVPR'26) · MAM2 — Matting Anything 2 (ICLR'26) + NOVM	Video matting de cualquier objeto (humo, fuego, agua) con prompts tipo SAM 2
[EVIDENCIA] MAM2 se construye sobre SAM 2 con LoRA y añade un Promptable Dual-mode Decoder que predice máscara y trimap simultáneamente, más un módulo ligero de matting (MEMatte) — y lo presenta en un nuevo benchmark de objetos naturales (NOVM: 50 clips de animales, burbujas, nubes, fuego, agua, escarcha) . MatAnyone usa propagación de memoria con fusión region-adaptativa y aporta el dataset VM800 .
2. Tabla de modelos
Hojas
Modelo	Año / Paper	Arquitectura / Backbone	Input	Output / Resolución	Datasets	Métricas	Fortalezas	Debilidades	Licencia / disponibilidad
U2-Net	2020, Pattern Recognition (Qin et al.)	U-Net anidado de 2 niveles con bloques RSU; sin backbone preentrenado	RGB 320×320	Saliency 1 canal	DUTS-TR; eval: ECSSD, DUT-OMRON, HKU-IS, PASCAL-S, SOD	maxFβ, MAE, E-measure, S-measure	Mejor relación calidad/coste de su época; 176 MB, ~30 FPS	Bordes duros, sin alpha real; mal con multi-objeto/fondos complejos	Apache-2.0, repo oficial, pesos libres
U2NetP	2020 (mismo paper)	Versión reducida	RGB 320×320	Igual	Igual	Igual	4.7 MB, ~40 FPS; CPU/móvil	Bordes claramente "blocky"	Apache-2.0
IS-Net	2022, ECCV (Qin et al.)	U2-Net + supervisión intermedia (features + máscara)	RGB HR	Máscara binaria	DIS5K (5,470 imágenes 2K/4K)	F, E, S, MAE, HCE	SOTA inicial en DIS	Multi-etapa/lento; binario; superado por BiRefNet	Código abierto
InSPyReNet	2022, ACCV (Kim et al.)	Encoder Swin-B/Res2Net + decodificador piramidal; blending LR+HR	RGB (LR train, HR test)	Saliency HR	DUTS, HRSOD, UHRSD, DIS5K	Fβ, MAE, S, E, mBA	Muy fuerte en HR y bordes; licencia limpia; en comparativas comunitarias supera a BRIA/U2Net/ISNet	Multi-etapa → lento; VRAM alta en HD; binario	MIT
MODNet	AAAI 2022 (arXiv 2020)	Tres ramas: semántica (MobileNetV2 + e-ASPP), detalle, fusión	RGB solo	Alpha 512×512	Adobe Matting, PPM-100 (propio)	MSE, MAD, SAD	67 FPS (1080Ti); cabello sorprendente para su tamaño	Solo retratos; 512² pierde detalle	Código y pesos públicos
BackgroundMattingV2	CVPR 2021 (Lin et al.)	Red base LR + refiner HR por parches	RGB + fondo capturado	Alpha + F, 4K	VideoMatte240K, PhotoMatte85	SAD, MSE, Grad, Conn, dtSSD	30 FPS 4K; hebras de cabello excelentes	Requiere capturar el fondo sin sujeto: inviable en fotos sueltas	MIT
RVM	WACV 2022 (arXiv 2021)	RNN recurrente con memoria temporal (ConvGRU); MobileNetV3/ResNet-50	Frames video	Alpha temporal	VideoMatte240K	SAD, MSE, Grad, Conn, dtSSD	4K 76 FPS / HD 104 FPS; sin trimap ni fondo	Solo humanos; licencia copyleft	GPL-3.0
FBA Matting	2020 (arXiv)	ResNet que predice F, B y α conjuntamente	RGB + trimap	Alpha + colores	DIM/Composition-1k	SAD, MSE, Grad, Conn	Resuelve contaminación de color (predice F)	Necesita trimap bueno; lento en HR	Código público
PP-Matting / V2	2022 (arXiv 2204.09433), PaddleSeg	Dos ramas: HRDB (detalle) + SCB (contexto), guidance flow	RGB	Alpha	Composition-1k, Distinctions-646	SAD, MSE, Grad, Conn	Trimap-free competitivo con trimap-based	Ecosistema PaddlePaddle	Apache-2.0
ViTMatte	arXiv 2023 / Inf. Fusion 2024	ViT plano preentrenado (MAE) + conv neck + Detail Capture Module	RGB + trimap/máscara guía	Alpha	Composition-1k, Distinctions-646	SAD, MSE, Grad, Conn	Máxima precisión conocida en Composition-1k	Requiere guía; costoso sin ella	Código y pesos públicos
Matting Anything (MAM)	2023 (arXiv) / CVPRW 2024	Features de SAM + módulo Mask-to-Matte ligero (2.7M params)	RGB + prompt (box/punto/texto)	Alpha	Composition-1k, AIM-500, P3M	SAD, MSE, MAD, Grad, Conn	Un modelo para semántico/instancia/referring; interacción trivial	Paridad con especialistas, no superior	Open-source (SHI-Labs)
Matte Anything	2024, Image & Vision Computing	Pipeline SAM + GroundingDINO → pseudo-trimap → ViTMatte	RGB + prompt	Alpha	Composition-1k	SAD, MSE, Grad, Conn	Calidad de trimap-based con clicks	Coste de 2 foundation models	Código público
SAM	ICCV 2023	ViT image encoder + prompt + mask decoder	RGB + prompt	Máscara binaria	SA-1B (1,100M máscaras)	mIoU zero-shot	Generalización; ecosistema	Sin transparencia; artefactos checkerboard en bordes	Apache-2.0
SAM 2	2024; ICLR 2025	Hiera (MAE) + memoria streaming + decoder promptable	Imagen o video + prompt	Masklets binarios	SA-1B + SA-V	J&F, mIoU; 6× más rápido que SAM	Unificado; correcciones en cualquier frame; tracking	Salida binaria; necesita refiner para alpha	Apache-2.0
BiRefNet	CAAI AIR 2024 (Zheng et al.)	Localization Module (Swin) + Reconstruction Module con referencia bilateral: parches de imagen + mapa de gradientes + supervisión auxiliar de gradiente	RGB (1024×1024; lite hasta 2560×1440)	Máscara/alpha HR	DIS5K, HRSOD, COD + variantes (general, portrait, matting, DIS, COD, massive)	Fβ, MAE, E, S, HCE; SOTA en DIS/COD/HRSOD	Mejor open-source para foreground HR; detalles finísimos; ONNX; en HF transformers y rembg	Dicotómico (la variante matting da alpha); costoso en HR	MIT (código + pesos)
BRIA RMBG-1.4 / 2.0	2023 / nov 2024	Arquitectura BiRefNet + dataset propietario licenciado	RGB 1024×1024	Alpha 8-bit (256 niveles), no binaria	>12K (v1.4) / >15K (v2.0) imágenes licenciadas (e-commerce, stock, gaming)	Benchmark propio + DIS/matting	Cabello, transparencias, telas; legalmente limpio; v1.4: >5M descargas	CC BY-NC 4.0 → licencia comercial de pago	Source-available; API fal.ai ($0.018/img), Replicate, ComfyUI
ZIM	ICCV 2025 Highlight (NAVER)	SAM + pixel decoder jerárquico (stride 2) + prompt-aware masked attention; entrenado en SA1B-Matte	RGB + prompt	Matte de micro-detalle	MicroMat-3K + 23 datasets zero-shot	SAD, MSE, MAE, Grad, Conn	Zero-shot real; MSE 1.893 vs 11.057 de SAM (box prompt, MicroMat-3K); solo +10 ms sobre SAM	No alcanza matting con trimap en transparencias extremas	Open-source (naver-ai/ZIM), pesos ViT-B/L
MatAnyone	CVPR 2025 (NTU S-Lab)	Basado en Cutie: memoria banco + Consistent Memory Propagation	Video + máscara 1er frame	Alpha estable	VM800 (nuevo)	MAD, MSE, Grad, dtSSD	Supera a RVM/MaGGle en todos los benchmarks; tolera máscaras imperfectas	Requiere máscara inicial; licencia restrictiva	NTU S-Lab License 1.0
MAM2 (Matting Anything 2)	ICLR 2026	SAM2+LoRA + decoder dual (máscara+trimap) + siamese de memoria + MEMatte	Video + prompt (punto/caja/máscara)	Alpha de cualquier objeto	NOVM (animales, humo, fuego, agua), YouTubeMatte, VM240K	MAD, MSE, Grad, dtSSD	MAD 1.19 vs 3.50 de RVM-Large (YouTubeMatte); cualquier objeto	Reciente; coste; transparencias extremas aún fallan	Código anunciado
MatAnyone 2	CVPR 2026 (arXiv dic 2025)	MatAnyone + Matting Quality Evaluator (DINOv3+DPT)	Video + máscara	Alpha	VMReal	MAD, MSE, Grad, dtSSD	Mejor detalle en cabello al viento e iluminación	Muy reciente	Académico
GVM (Generative Video Matting)	2025	Stable Video Diffusion + flow matching sobre alpha latents	Video	Alpha	VideoMatte240K, V-HIM60	MSE, SAD, Grad, Conn, dtSSD	SOTA en Grad/dtSSD; robusto en fondos complejos	10–50× más lento que RVM; experimental	Investigación
Otros relevantes: MatteFormer (CVPR'23), SDMatte (CVPR'24), HDMatt (AAAI'21), AIM-Net (IJCAI'21), TransMatting (ECCV'22, objetos transparentes), P3M-Net (retratos con privacidad), RefMatte (matting por lenguaje), UIM (ACM 2026), MEMatte (2025, trimap-based eficiente).
3. Métricas: qué miden y cuáles importan para su producto
Segmentación binaria (SOD/DIS):
IoU / mIoU: superposición máscara vs. ground truth.
F-score (Fβ, β²=0.3): precisión–recall con énfasis en precisión; variantes maxFβ (umbral óptimo), wFβ (ponderada), adaptFβ.
MAE: error absoluto medio del mapa.
S-measure / E-measure: similitud estructural y de error combinado; más alineadas con percepción.
HCE (Human Correction Efforts): estima los clics de ratón necesarios para corregir la máscara — la métrica más cercana al coste real de un flujo de edición.
relaxFβ / mBA (mean Boundary Accuracy): calidad de frontera explícita.
Alpha matting (estándar Rhemann et al., CVPR 2009):
SAD: Σ|α−α*| — global, pero dominada por regiones grandes.
MSE / MAD: error cuadrático/medio global; MAD es el estándar en benchmarks automáticos (AIM-500, P3M).
SAD-T: SAD solo en la zona de transición — crítico, porque ahí vive la mayor parte del error perceptible.
Gradient: diferencia de gradientes entre mattes — nitidez estructural del borde.
Connectivity: penaliza fragmentación (hebras cortadas, islas).
dtSSD: coherencia temporal (video).
[EVIDENCIA] La correlación con percepción humana es el punto central de su pregunta: el benchmark de alphamatting.com validó con usuarios que Gradient y Connectivity se correlacionan ~0.75 con el juicio humano, mientras SAD/MSE apenas ~0.28–0.51. SAD/MSE "no siempre correlacionan con la calidad visual percibida" — por eso existen medidas perceptuales.
Métrica relevante para una herramienta de eliminación de fondos (conclusión):
Primarias: Grad + Conn + SAD-T (lo que el ojo ve: bordes, hebras, transparencias).
Secundarias: MAD/MSE global (detectar desastres semánticos).
Operativas: HCE (cuánto corregirá el usuario) y dtSSD si hay video.
Fβ/IoU iguales + mejor Grad/Conn/HCE ⇒ se ve mejor: bordes nítidos y continuos, no solo área correcta.
4. Datasets: cuál sirve para qué
Hojas
Dataset	Año	Contenido	Sirve para	Notas
DUTS (TR/TE)	CVPR'17	10,553 train / 5,019 test	SOD general; entrena U2-Net/InSPyReNet	Estándar SOD
DUT-OMRON, ECSSD, HKU-IS, PASCAL-S, SOD	2013–2017	~1K–5K c/u	Eval SOD	Escenas complejas
HRSOD / UHRSD / DAVIS-S	2020–21	SOD alta resolución	DIS/SOD-HR	Eval de InSPyReNet, BiRefNet
COD (COD10K, CAMO, NC4K)	2019–22	Objetos camuflados	COD	Caso extremo de bajo contraste
DIS5K	ECCV 2022	5,470 imágenes HR (2K/4K), objetos "meticulous"	Background removal de alta precisión: objetos, estructuras finas, fondos complejos	Anotaciones finísimas; métrica HCE
Composition-1k (DIM)	CVPR 2017	431 FG train + 50 FG test sobre 1,000/100 BG	Matting con trimap (objetos)	Sintético: composición perfecta
AlphaMatting.com	CVPR 2009	27 train / 8 test HR naturales con trimaps	Benchmark clásico online	Imágenes muy difíciles
AIM-500	IJCAI 2021	500 imágenes naturales reales: 100 retrato, 200 animal, 34 transparentes, 75 plantas, 45 muebles, 36 juguetes, 10 frutas	Generalización real de matting automático	Primer test no-compuesto
Human-2k	ICCV 2021	2,000 train / 100 test HR (2112×2075)	Matting personas/cabello	Sintético pero detallado
HIM2k, P3M-10k (9,421+1,000), RWP-636, PPM-100	2021–22	Humanos reales (P3M: 5,382 con rostro pixelado)	Retratos, cabello, dominio real	P3M = benchmark real estándar
AM-2k, SIM, Trans-460 / TOM-876	2018–22	Animales; 20 clases; transparentes	Animales, transparencias	Trans-460/TOM: lo único para vidrio/agua
VideoMatte240K, PhotoMatte85, VM800, YouTubeMatte, NOVM	2021–25	Video matting	Video personas / objetos	VideoMatte240K: 240K clips sintéticos
SA-V	2024	51K videos, 643K masklets	Video segmentación (SAM 2)	Estándar
SA1B-Matte / MicroMat-3K	ICCV 2025	SA1B convertido a labels matte micro-nivel	Zero-shot matting (ZIM)	Escala sin anotación manual
Matriz rápida: personas+cabello → Human-2k, HIM2k, P3M-10k · objetos/finos → DIS5K, SIM, AIM-500 · transparencias → Trans-460, TOM, AIM-500 · matting alto precisión → Composition-1k + Distinctions-646 + AIM-500 · fondos complejos reales → AIM-500, P3M-500-NP, DIS-TE4 · video → VideoMatte240K, YouTubeMatte, VM800, NOVM.
5. Por qué modelos con métricas similares se ven distintos
[EVIDENCIA]
Las métricas globales ocultan la frontera. SAD/MSE promedian toda la imagen; un error de 0.05 concentrado en el 5% de píxeles del borde pesa poco numéricamente y mucho visualmente. Grad y Conn se diseñaron precisamente para medir lo que SAD no captura.
Boundary quality vs. área correcta. U2-Net optimiza Fβ global a 320×320; su borde queda "blocky" al reescalar. BiRefNet introduce referencia bilateral explícita con mapas de gradiente como supervisión objetivo  y entrena en DIS5K — la señal de entrenamiento decide el look, no la métrica de evaluación.
Cabello y estructuras finas exigen tres cosas a la vez: anotaciones de nivel hebra en training (Human-2k, DIS5K), resolución de inferencia ≥1024, y supervisión explícita de detalle (rama de detalle de MODNet, DCM de ViTMatte, gradient supervision de BiRefNet). Sin ellas, el modelo aprende que "hebras = ruido" y suaviza.
Transparencias requieren alpha parcial real. RMBG-2.0 emite alpha de 8 bits no binaria con niveles de transición suaves, mientras los modelos binarios producen bordes duros artificiales . Este es exactamente el argumento de ventaja de BRIA sobre BiRefNet "puro".
Color contamination y halos. Extraer el foreground como F = α·I hace que el borde herede el color del fondo original → halo al componer. FBA lo resuelve prediciendo F y B conjuntamente; MAM2 lo documenta como problema abierto del campo: el foreground extraído "inevitablemente retiene algo del color de fondo" .
Errores semánticos vs. de detalle. Un error semántico grande (objeto equivocado en escena multi-objeto) pesa infinitamente más que 0.01 de MAE difusa, aunque numéricamente pueda compensarse.
Dependencia de umbral. U2-Net/IS-Net/BiRefNet emiten logits; el threshold (0.5 por defecto) cambia radicalmente el resultado. RMBG-2.0/BiRefNet permiten threshold configurable por caso de uso.
Resolución efectiva. Inferir a 512² y reescalar destruye detalle antes de que una métrica global lo note.
6. Estado del arte actual por caso de uso
Hojas
Caso	Mejor opción	Alternativas maduras	Experimental
A. Background removal general	RMBG-2.0 (calidad/licencia) o BiRefNet-general (MIT, casi igual)	InSPyReNet (MIT), IS-Net, U2-Net para bajo coste	ZIM
B. Personas	BiRefNet-portrait / RMBG-2.0	MODNet (GPU débil/tiempo real), PP-MattingV2	—
C. Cabello alta precisión	RMBG-2.0 / BiRefNet-matting a 1024+; máximo: Matte Anything	MODNet (512²), FBA con buen trimap	SDMatte, UIM
D. Productos / e-commerce	RMBG-2.0 (entrenado con e-commerce/stock) o BiRefNet-general	InSPyReNet	—
E. Objetos / estructuras finas	BiRefNet (entrenado en DIS5K)	IS-Net, InSPyReNet	ZIM
F. Matting alta precisión (estudio)	ViTMatte + pseudo-trimap de SAM	FBA, MatteFormer, MEMatte	SDMatte
G. Refinamiento interactivo	SAM 2 + matting head; Matte Anything	MAM, HQ-SAM	ZIM, MAM2 (video)
H. Video personas	MatAnyone (SOTA)	RVM (GPL, 4K 76 FPS), BGMv2 (si hay fondo capturado)	MatAnyone 2, GVM
I. Video cualquier objeto	MAM2	SAM 2 + refiner	GVM
7. Madurez tecnológica
Madura para producción hoy:
BiRefNet — MIT (código y pesos), verificado SOTA en DIS/COD/HRSOD, integrado en HF transformers, rembg y FAL .
BRIA RMBG-2.0 — si se paga la licencia comercial (pesos abiertos son CC BY-NC; API desde $0.018/imagen).
U2-Net/U2NetP — Apache-2.0; líder de adopción; aceptable solo para casos simples.
InSPyReNet (MIT), MODNet, SAM/SAM 2 (Apache-2.0).
RVM/BGMv2 — probados en producción de video (TikTok usa RVM), con límites de licencia claros.
Prometedora con condiciones:
ViTMatte (máxima precisión, pero pipeline compuesto con pseudo-trimap).
MatAnyone/MatAnyone 2 (SOTA video, licencia académica NTU S-Lab restrictiva ).
ZIM (ICCV'25 Highlight; zero-shot real; falta validación industrial amplia).
Experimental:
MAM2 (video matting de cualquier objeto, ICLR 2026).
GVM (difusión; ordenes de magnitud más lento que RVM).
SDMatte/UIM/MEMatte (publicados, sin ecosistema de despliegue).
Transparencias extremas y descontaminación de color: problema abierto declarado .
8. Recomendación de arquitectura
[EVIDENCIA]:
BiRefNet-general y RMBG-2.0 comparten arquitectura y encabezan comparativas públicas; BiRefNet es el mejor open-source con licencia permisiva (MIT).
La comunidad ya estandarizó BiRefNet/RMBG como punto de partida; U2-Net queda para dispositivos mínimos (rembg documenta bordes "blocky" de U2-Net vs. modelos mayores ).
SAM 2 es el estándar de facto para interacción y video (Apache-2.0).
Las métricas que predicen satisfacción del usuario son Grad/Conn/HCE, no SAD sola.
En video matting, MAM2 domina las tablas: MAD 1.19 vs 3.50 de RVM-Large y dtSSD 1.23 vs 2.08 en YouTubeMatte ; MatAnyone supera a RVM en todo .
[OPINIÓN] — arquitectura recomendada:
Pipeline principal de imágenes: BiRefNet-general (o RMBG-2.0 si el presupuesto de licencia es aceptable y necesitas el plus legal/calidad) como extractor automático, mínimo 1024×1024, usando el logit suave como alpha (no binarizar) con threshold configurable por caso de uso.
Modo "alta precisión": SAM (o ZIM) → máscara inicial → pseudo-trimap (dilate/erode) → ViTMatte. Es el patrón Matte Anything y logra calidad de estudio con clicks.
Modo interactivo: SAM 2 nativo (clicks positivos/negativos, propagación a video) con la máscara resultante como guía del refiner.
Video: MatAnyone (o RVM si la GPL encaja o prima la velocidad). Monitoring con dtSSD.
Edge-aware refinement: supervisión de gradiente en cualquier fine-tuning (lección BiRefNet); guided filter solo como pulido final.
Evaluación interna: DIS5K-TE + AIM-500 + P3M-500-NP + subset propio de dominio; reportar MAD, Grad, Conn, SAD-T, HCE + estudio humano pareado (los benchmarks sintéticos sobreestiman la calidad percibida).
Riesgos a vigilar: licencias (RMBG-2.0 = CC BY-NC, RVM = GPL-3.0, MatAnyone = NTU S-Lab; los pesos heredan licencia propia independiente del wrapper rembg MIT ), color contamination en composición (predicción de F o descontaminación post-hoc), y degradación en multi-objeto/NSO.
9. Selecciones finales
Mejores papers: U2-Net (PR'20) · DIS/IS-Net (ECCV'22) · InSPyReNet (ACCV'22) · BiRefNet (CAAI AIR'24) · MODNet (AAAI'22) · BGMv2 (CVPR'21) · RVM (WACV'22) · ViTMatte (Inf. Fusion'24) · SAM (ICCV'23) · SAM 2 (ICLR'25) · ZIM (ICCV'25) · MatAnyone (CVPR'25) · MAM2 (ICLR'26) · Survey "Deep Image Matting: A Comprehensive Survey" (2023).
Mejores repositorios: xuebinqin/U-2-Net · ZhengPeng7/BiRefNet · Bria-AI/RMBG-2.0 · danielgatis/rembg · PeterL1n/RobustVideoMatting · PeterL1n/BackgroundMattingV2 · hustvl/ViTMatte · pq-yang/MatAnyone · naver-ai/ZIM · facebookresearch/sam2 · SHI-Labs/Matting-Anything · plemeri/InSPyReNet · PaddlePaddle/PaddleSeg.
Mejores datasets: DIS5K · DUTS · AIM-500 · Composition-1k · Human-2k · P3M-10k · HIM2k · Trans-460/TOM · VideoMatte240K · VM800/NOVM · SA-V · SA1B-Matte/MicroMat-3K.
Mejores métricas: Grad + Conn + SAD-T (primarias), MAD/MSE (secundarias), HCE (operativa), dtSSD (video).
Más prometedora: la línea SAM 2 → ZIM/MAM2 (matting promptable zero-shot unificado imagen+video) y, en paralelo, BiRefNet/RMBG como extractor automático.
Suficientemente madura: BiRefNet, RMBG-2.0 (con licencia), U2-Net, InSPyReNet, MODNet, SAM/SAM 2, RVM/BGMv2.
Experimental: MAM2, MatAnyone 2, GVM, matting de transparencias extremas, descontaminación de color.


# Estado del arte: Background Removal, Image Matting y Salient Object Detection (2018–2026)

Informe técnico — investigación académica. Fecha de corte: octubre 2026.

---

## 1. Timeline del desarrollo tecnológico

| Año | Hito | Relevancia para producción |
| --- | --- | --- |
| 2017 | Deep Image Matting (DIM, CVPR'17) + Adobe Composition-1k | Establece el paradigma trimap-based y el benchmark Composition-1k |
| 2018–2019 | IndexNet (ICCV'19), GCA Matting (AAAI'20), DIM dataset (HATT-646) | Primeras CNNs end-to-end para alpha matting |
| 2019 | BASNet (CVPR'19) | Precursor de U2-Net |
| 2020 | **U2-Net (PR'20)**; AlphaGAN (BMVC'18); FBA Matting (2020) | U2-Net se convierte en el estándar de-facto de background removal (rembg) |
| 2020 | Background Matting "World is Your Green Screen" (CVPR'20) | Matting con frame de fondo capturado (videollamadas) |
| 2020–2021 | MODNet (AAAI'22, arXiv 2020); BSHM (CVPR'20) | Portrait matting trimap-free en tiempo real (67 FPS) |
| 2021 | **BackgroundMattingV2 (CVPR'21, Best Student Paper HM)**; HDMatt (AAAI'21); MG Matting (CVPR'21); Human-2k, SIM datasets | BGMv2: 30fps en 4K; matting guiado por máscara; datasets HR |
| 2021 | **RVM (WACV'22, arXiv 2021)** | Video matting recurrente, 4K 76 FPS, sin inputs auxiliares |
| 2021 | AIM-500 (IJCAI'21) + AIM-Net; TransMatting (ECCV'22) | Primer benchmark de imágenes naturales reales; matting de objetos transparentes |
| 2022 | **DIS + IS-Net (ECCV'22) + DIS5K** | Define la tarea Dichotomous Image Segmentation; métrica HCE |
| 2022 | PP-Matting / PP-MattingV2 (PaddleSeg) | Matting industrial trimap-free de Baidu |
| 2022 | InSPyReNet (ACCV'22) | SOD de alta resolución vía pirámide de imágenes |
| 2023 | **SAM (ICCV'23)**; Matte Anything (2023); Matting Anything (MAM); MatteFormer (CVPR'23, arXiv 2022) | Era de los foundation models; matting interactivo sobre SAM |
| 2023 | **ViTMatte** (arXiv 2023; pub. Information Fusion 2024) | SOTA en Composition-1k con ViT preentrenado + conv neck |
| 2023 | P3M-10k / P3M-Net (MM'21, IJCV'22), RIM/RefMatte (CVPR'23) | Matting de retratos con privacidad facial; matting por lenguaje |
| 2024 | **BiRefNet (CAAI AIR'24)**; **BRIA RMBG-1.4 → RMBG-2.0 (nov 2024)** | Nuevo SOTA open-source en DIS; RMBG-2.0 se vuelve el modelo comercial de referencia |
| 2024 | **SAM 2 (2024, ICLR'25)** + SA-V dataset | Segmentación promptable en imagen y video; memoria streaming |
| 2024 | TransMatting publicado ECCV'22; SDMatte (CVPR'24): unifica automático + interactivo | Grafting de ViTs preentrenados para matting |
| 2025 | **ZIM (ICCV'25, Highlight)** | Matting zero-shot sobre arquitectura SAM; dataset SA1B-Matte |
| 2025 | **MatAnyone (CVPR'25)**; MatAnyone 2 (CVPR'26, arXiv dic 2025); GVM (2025) | Video matting con memoria consistente; enfoque generativo con difusión |
| 2025–2026 | **Matting Anything 2 / MAM2 (ICLR'26)** + NOVM dataset; MEMatte; UIM (ACM 2026) | Video matting de cualquier objeto (no solo humanos) con prompts tipo SAM 2 |

---

## 2. Tabla de modelos

| Modelo | Año / Paper | Arquitectura / Backbone | Input | Output / Resolución | Datasets | Métricas clave | Fortalezas | Debilidades | Licencia / disponibilidad |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **U2-Net** | 2020, Pattern Recognition (Qin et al.) | U-Net anidado de 2 niveles con bloques RSU; sin backbone ImageNet | RGB 320×320 (arbitrario tras fix) | Saliency map binario 1 canal | DUTS-TR; eval en ECSSD, DUT-OMRON, HKU-IS, PASCAL-S, SOD, DUTS-TE | maxFβ, MAE, E-measure, S-measure; relaxFβ de frontera | Precio/calidad imbatible; entrena from scratch; 176 MB, 30 FPS (1080Ti) | Sin alpha real (bordes duros); fondos complejos y objetos múltiples difíciles; sin cabello fino | Apache-2.0 (repo oficial); pesos libres; rembg lo empaqueta en ONNX |
| **U2NetP** | 2020 (mismo paper) | Igual, versión reducida | RGB 320×320 | Igual | Igual | Igual | 4.7 MB, 40 FPS; ideal para móvil/CPU | Calidad de borde claramente inferior ("blocky") | Apache-2.0 |
| **IS-Net** | 2022, ECCV (Qin et al.) | U2-Net + supervisión intermedia a nivel feature y máscara | RGB (HR) | Máscara binaria de alta precisión | DIS5K (5,470 imágenes 2K/4K) | F, E, S, MAE, **HCE** | SOTA inicial en DIS; muy preciso en objetos "meticulous" | Multi-etapa (lento); binario, no matting; desactualizado vs BiRefNet | Código abierto (repo U-2-Net) |
| **DIS5K** (dataset) | 2022, ECCV | — | — | HR con anotaciones finísimas | 3,000 train / 2,470 test en 4 splits | HCE, Fβ, MAE | Estándar para DIS y background removal de alta precisión | Sesgo hacia objetos no-humanos "meticulous" | Público |
| **InSPyReNet** | 2022, ACCV (Kim et al.) | Encoder Swin-B/Res2Net + decodificador piramidal; pyramid blending LR+HR | RGB (LR entrenamiento, HR inferencia) | Saliency HR | DUTS, HRSOD, UHRSD, DIS5K, etc. | Fβ, MAE, S, E; mBA (boundary) | Excelente en HR; inferencia a 384 o HD; según comparativas comunitarias (ComfyUI, HF) superior a BRIA/U2Net/ISNet en bordes | Multi-etapa → lento; binario; consumo de VRAM alto en HD (~6 GB) | MIT — uso comercial permitido |
| **MODNet** | AAAI 2022 (arXiv 2020) (Ke et al.) | Descomposición de objetivos: rama semántica (MobileNetV2 + e-ASPP), rama detalle, rama fusión; estrategia SOC auto-supervisada | RGB solamente | Alpha matte 512×512 | Adobe Matting, PPM-100 (propio), SPD | MSE, MAD, SAD | 67 FPS en 1080Ti; trimap-free; calidad de cabello sorprendente para su tamaño | Optimizado solo para retratos; a 512×512 pierde detalle en imágenes grandes; dominio limitado | Código + pesos públicos (repo ZHKKKe) |
| **BackgroundMattingV2 (BGMv2)** | CVPR 2021 (Lin et al.) | Dos redes: base LR + refiner HR por parches | RGB **+ frame de fondo capturado** | Alpha + foreground, 4K | VideoMatte240K, PhotoMatte85 (13K) | SAD, MSE, Grad, Conn, dtSSD | 30 FPS a 4K; detalle de hebra de cabello excelente | Requiere capturar el fondo sin sujeto — inviable en fotos sueltas | MIT (actualizado a propósito para uso comercial) |
| **RVM** | WACV 2022 (arXiv 2021) (Lin et al., ByteDance) | RNN recurrente con memoria temporal (ConvGRU); encoder MobileNetV3/ResNet-50 | Frames de video | Alpha matte temporalmente coherente | VideoMatte240K | SAD, MSE, Grad, Conn, dtSSD | 4K 76 FPS / HD 104 FPS (1080Ti); sin trimap ni fondo; exporta a ONNX/TF.js | Solo humanos; parpadeo en escenas multi-persona ambiguas; licencia copyleft | GPL-3.0 |
| **FBA Matting** | 2020 (arXiv) (Forte & Pitié) | Encoder-decoder ResNet que predice **F, B y α** conjuntamente | RGB + trimap | Alpha + colores FG/BG | DIM-481 (Composition-1k) | SAD, MSE, Grad, Conn | Mejor en Composition-1k en su momento; recuperar F resuelve contaminación de color | Necesita trimap bueno; lento a HR | Código público |
| **PP-Matting / V2** | 2022 (arXiv 2204.09433), PaddleSeg | Dos ramas: HRDB (detalle HR) + SCB (contexto semántico), fusión por guidance flow | RGB | Alpha | Composition-1k, Distinctions-646 | SAD, MSE, Grad, Conn | Trimap-free competitivo con métodos trimap-based; buen cabello; V2 es lite-SOTA | Ecosistema PaddlePaddle; infrautilizado fuera de China | Apache-2.0 (PaddleSeg) |
| **ViTMatte** | 2023 (arXiv) / Information Fusion 2024 (Yao et al.) | **ViT plano preentrenado (MAE)** + conv neck + Detail Capture Module (DCM); solo 8% de parámetros en decoder | RGB + trimap (o máscara de SDMatte/Matte Anything) | Alpha | Composition-1k, Distinctions-646 | SAD, MSE, Grad, Conn | SOTA con gran margen en Composition-1k; hereda pretraining y estrategias de ViT; >4M descargas/mes vía HF | Requiere trimap/máscara guía; costoso (ViT) sin guía | Código y pesos públicos |
| **Matting Anything (MAM)** | 2023 (arXiv) / CVPRW 2024 (Li, Jain, Shi) | Features de SAM + módulo ligero Mask-to-Matte (M2M, 2.7M params) con refinamiento iterativo | RGB + prompt (box/punto/texto) | Alpha | Composition-1k, AIM-500, P3M | SAD, MSE, MAD, Grad, Conn | Un solo modelo para semántico/instancia/referring matting; interacción trivial | Calidad comparable pero no superior a especialistas; depende de SAM | Open-source (SHI-Labs) |
| **Matte Anything (MatAny)** | 2024, Image & Vision Computing (Yao et al.) | Pipeline: SAM + GroundingDINO → pseudo-trimap (con corrección de transparencia) → **ViTMatte** | RGB + prompt | Alpha | Composition-1k | SAD, MSE, Grad, Conn | Calidad de trimap-based con interacción de clic; cero entrenamiento | Costo computacional de 2 foundation models; pipeline complejo | Código público |
| **SAM** | ICCV 2023 (Meta) | ViT image encoder + prompt encoder + mask decoder | RGB + prompt (punto/caja/máscara) | Máscara binaria (no alpha) | SA-1B (1,100 M máscaras) | mIoU zero-shot | Generalización sin precedentes; ecosistema enorme | Máscaras duras; sin transparencia; artefactos checkerboard en bordes | Apache-2.0 |
| **SAM 2** | 2024 (Meta); ICLR 2025 | Hiera (MAE-pretrained) + memoria streaming + memory attention; decoder promptable | RGB o video + prompt | Masklets binarios | SA-1B + SA-V (51K videos, 643K masklets) | J&F, mIoU; 6× más rápido que SAM en imagen | Unificado imagen+video; correcciones con clic en cualquier frame; tracking | Salida binaria (no matting); necesita refinador para alpha | Apache-2.0 |
| **BiRefNet** | CAAI AIR 2024 (Zheng et al.) | Localization Module (backbone **Swin Transformer**) + Reconstruction Module con **referencia bilateral**: parches de imagen original (source ref) + mapa de gradientes (target ref) + supervisión auxiliar de gradiente | RGB (1024×1024; versión lite-2K a 2560×1440) | Máscara/alpha de alta resolución | DIS5K, HRSOD, COD, salient obj.; variantes: general, portrait, matting, DIS, COD, massive | Fβ, MAE, E, S, HCE; **SOTA en DIS/COD/HRSOD** | Mejor open-source para extracción de foreground HR; captura detalles finísimos; ONNX export; integrado en HF transformers y rembg | Aún es segmentación dicotómica (matting requiere la variante matting); coste de cómputo alto en HR | **MIT (código + pesos)** — uso comercial libre |
| **BRIA RMBG-1.4 / 2.0** | 2023 / nov 2024 (BRIA AI) | **Arquitectura BiRefNet** + dataset propietario licenciado y esquema de entrenamiento propio | RGB 1024×1024 | **Alpha 8-bit no binaria (256 niveles)** — transición suave | >12K (v1.4) / >15K (v2.0) imágenes HR licenciadas: e-commerce, stock, gaming, ads | Benchmark propio vs competencia; métricas DIS/matting | Muy superior en cabello, transparencias, telas; legalmente limpio para empresa; v1.4: >5M descargas; v2.0 soporta multi-objeto | CC BY-NC 4.0 → **licencia comercial de pago obligatoria**; cierre parcial (no es 100% open weights con libertad plena) | Source-available; API en fal.ai ($0.018/imagen), Replicate, ComfyUI |
| **ZIM** | ICCV 2025 Highlight (NAVER) | SAM + pixel decoder jerárquico (stride 2) + prompt-aware masked attention; entrenado en **SA1B-Matte** (labels matte micro-nivel convertidos automáticamente de SA1B) | RGB + prompt punto/caja (o texto vía GroundingDINO) | Matte de micro-detalle | MicroMat-3K (nuevo), zero-shot en 23+ datasets | SAD, MSE, MAE, Grad, Conn | MSE 1.893 vs 11.057 de SAM (box prompt, MicroMat-3K fine); zero-shot real; solo +10 ms sobre SAM | Nivel de "matte suave" no equivale a matting con trimap calidad ViTMatte en transparencias extremas | Open-source (naver-ai/ZIM); pesos ViT-B/L |
| **MatAnyone** | CVPR 2025 (Yang et al., NTU S-Lab) | Basado en Cutie: memoria banco + Consistent Memory Propagation (fusión de memoria region-adaptativa por probabilidad de cambio) | Video + máscara del primer frame | Alpha estable en el tiempo | Nuevo dataset VM800 (mayor y más diverso que VideoMatte240K) | MAD, MSE, Grad, dtSSD | Supera a RVM/MaGGle en todos los benchmarks; tolera máscaras iniciales imperfectas | Requiere máscara inicial; licencia institucional restrictiva | NTU S-Lab License 1.0 (no comercial sin acuerdo) |
| **Matting Anything 2 (MAM2)** | ICLR 2026 (arXiv 2511, preprint) | SAM2 finetune (LoRA) + Promptable Dual-mode Decoder (máscara+trimap) + Memory-Separable Siamese + mater ligero MEMatte | Video + prompt (punto/caja/máscara) | Alpha de cualquier objeto | Nuevo benchmark **NOVM** (50 clips, objetos naturales: animales, humo, fuego, agua); YouTubeMatte, VM240K | MAD, MSE, Grad, dtSSD | SOTA amplio: MAD 1.19 vs 3.50 de RVM-Large (YouTubeMatte); cualquier objeto, no solo humanos; prompts tipo SAM 2 | Reciente/experimental; coste (SAM2 + memoria); transparencias extremas aún fallan | Código anunciado (Matting-Anything-2) |
| **MatAnyone 2** | CVPR 2026 (arXiv dic 2025) | MatAnyone + Matting Quality Evaluator (DINOv3+DPT) que pondera referencia de frames | Video + máscara | Alpha | VMReal | MAD, MSE, Grad, dtSSD | Mejora detalle y estabilidad en cabello al viento e iluminación compleja | Muy reciente | Académico |
| **Generative Video Matting (GVM)** | 2025 (arXiv 2508.07905) | Stable Video Diffusion + flow matching para denoising de alpha latents | Video | Alpha | VideoMatte240K, V-HIM60 | MSE, SAD, Grad, Conn, dtSSD | SOTA en Grad y dtSSD; robusto en fondos complejos y cabello | 10–50× más lento que RVM; experimental | Investigación |

**Otros modelos relevantes encontrados:** MatteFormer (CVPR'23, trimap-based con Swin), SDMatte (CVPR'24: unifica automático+interactivo con ViTs preentrenados), HDMatt (AAAI'21: matting HR por parches), GFM/IJCV'22 y AIM-Net (IJCAI'21: matting automático encoder-sharing), P3M-Net (matting de retrato preservando privacidad facial), TransMatting (ECCV'22: matting de objetos transparentes, SAD 3.1 en alphamatting.com), UIM (ACM 2026: matting unificado interactivo con decoupling segmentación/transparencia).

---

## 3. Métricas: qué miden y cuáles importan para un producto

**Segmentación binaria (SOD/DIS):**

- **IoU**: intersección sobre unión de la máscara. Base de todo.
- **mIoU**: promedio de IoU entre clases/imágenes.
- **F-score (Fβ, β²=0.3)**: media armónica precisión–recall con énfasis en precisión; hay versión "weighted" y "max/adaptive" (maxFβ, wFβ).
- **MAE / M**: error absoluto medio del mapa de saliencia.
- **S-measure**: similitud estructural región-objeto (más alineada con percepción).
- **E-measure**: error combinado a nivel pixel + imagen.
- **HCE (Human Correction Efforts)**: aproxima el número de clics de ratón para corregir errores — la métrica más cercana al coste real de un flujo de edición <REF>cite✦web_search:4#0:~:text=we design a new metric called human correction efforts</REF>.
- **relaxFβ / mBA (mean Boundary Accuracy)**: calidad de frontera.

**Alpha matting (Rhemann et al., CVPR 2009 — estándar):**

- **SAD**: suma de diferencias absolutas |α−α*|. Engloba todo pero domina por regiones grandes.
- **MSE**: error cuadrático medio; penaliza desviaciones grandes.
- **MAD**: variante media (SAD/N); estándar en benchmarks automáticos (AIM-500, P3M).
- **SAD-T**: SAD solo en la zona de transición — crítico: los papers muestran que la mayor parte del error SAD total vive en la zona de transición <REF>cite✦web_search:3#0:~:text=the SAD-T metric...accounts for a significant portion</REF>.
- **Gradient error**: diferencia de gradientes entre mattes; mide nitidez estructural de bordes.
- **Connectivity error**: penaliza fragmentación del objeto (hebras de cabello cortadas, islas).
- **dtSSD**: coherencia temporal (video).

**Correlación con percepción humana (clave para su pregunta):** el estudio del benchmark alphamatting.com (Rhemann et al. 2009) validó que Gradient y Connectivity se correlacionan ~0.75 con el juicio humano, mientras SAD/MSE apenas ~0.28–0.51 <REF>cite✦web_search:3#11:~:text=SAD and MSE have weak correlation...Gradient and ConnectivityError measures correlate much better</REF>. Microsoft Research lo enunció de forma pionera: SAD/MSE "no siempre correlacionan con la calidad visual percibida por humanos" <REF>cite✦web_search:3#5:~:text=evaluation...tied to simple pixel-wise error measures</REF>.

**Métrica relevante para una herramienta de eliminación de fondos (conclusión):**

1. Primaria: **Grad + Conn + SAD-T** (lo que el ojo ve: bordes, hebras, transparencias).
2. Secundaria: MAD/MSE global (corrección de desastres semánticos).
3. Operativa: **HCE** (cuánto tendrá que corregir el usuario) y, si hay video, **dtSSD**.
4. Un modelo con Fβ/IoU idéntico pero mejor Grad/Conn/HCE *se verá* mejor: produce bordes nítidos y continuidad, no solo "área correcta".

---

## 4. Datasets: cuál sirve para qué

| Dataset | Año/venue | Contenido | Sirve para | Notas |
| --- | --- | --- | --- | --- |
| **DUTS** (TR/TE) | CVPR'17 (arXiv 2017) | 10,553 train / 5,019 test, objetos salientes variados | SOD general; entrenamiento de U2-Net/InSPyReNet | El estándar SOD; BSD-licensed |
| **DUT-OMRON** | CVPR'13 | 5,168 imágenes | SOD eval | Objetos complejos, fondos estructurados |
| **ECSSD** | PRL'12/13 | 1,000 imágenes | SOD eval rápido | Escenas semánticas complejas |
| **HKU-IS, PASCAL-S, SOD, MSRA-10K, FSS-1000** | 2014–2020 | Varios | SOD eval | Complementarios |
| **HRSOD / UHRSD / DAVIS-S** | 2020–2021 | SOD de alta resolución | DIS/SOD-HR | Eval de InSPyReNet, BiRefNet |
| **COD / COD10K, CAMO, NC4K** | 2019–2022 | Objetos camuflados | COD | El caso extremo de bajo contraste |
| **DIS5K** | ECCV 2022 | 5,470 imágenes HR (2K/4K), objetos "meticulous" (cabello, patas de pulpo, redes) | **Background removal de alta precisión, objetos, estructuras finas, fondos complejos** | Anotaciones extremadamente finas; métrica HCE |
| **DIM / Adobe Image Matting (Composition-1k)** | CVPR 2017 | 431 FG train + 50 FG test compuestos sobre 1,000+100 bg de COCO/VOC | Matting con trimap (objetos) | Sintético: composición perfecta, dominio no real |
| **AlphaMatting.com (Rhemann'09)** | CVPR 2009 | 27 train / 8 test HR naturales con trimaps | Benchmark online clásico | Imágenes muy difíciles (textura, color similar) |
| **AIM-500** | IJCAI 2021 | 500 imágenes **naturales reales** (100 retrato, 200 animal, 34 transparentes, 75 plantas, 45 muebles, 36 juguetes, 10 frutas) | Generalización real de matting automático | Primer test de imágenes no compuestas <REF>cite✦web_search:3#2:~:text=500 diverse natural images...manually label</REF> |
| **Human-2k** | ICCV 2021 | 2,000 train / 100 test HR (2112×2075), humanos | Matting de personas/cabello | Sintético pero HR y detallado |
| **HIM2k / P3M-10k (9,421+1,000) / RWP-636 / PPM-100** | 2021–2022 | Humanos reales (P3M: 5,382 con rostros pixelados por privacidad) | Retratos, cabello, dominio real | P3M = benchmark real estándar de portrait matting |
| **AM-2k** (animales), **SIM** (objetos matting 20 clases), **Trans-460 / TOM** (transparentes), **PhotoMatte85 / VideoMatte240K / VM800 / YouTubeMatte / NOVM** (video) | 2018–2025 | Dominios específicos | Animales, transparencias, video | Trans-460/TOM: lo único para vidrio/agua; VideoMatte240K=240K clips sintéticos para video |
| **RefMatte** | CVPR 2023 | 45,000 train / 2,500 test + texto | Matting por lenguaje (referring) | FG de datasets públicos + BG-20k |
| **SA1B-Matte / MicroMat-3K** | ICCV 2025 | SA1B con labels matte micro-nivel convertidos | Zero-shot matting (ZIM) | Escala sin anotación manual |

**Matriz rápida:** personas+cabello → Human-2k, HIM2k, P3M-10k, RWP-636, PPM-100 · objetos → DIS5K, SIM, AIM-500 · transparencias → Trans-460, TOM-876, AIM-500(34) · matting alto precisión → Composition-1k + Distinctions-646 + AIM-500 · fondos complejos/reales → AIM-500, P3M-500-NP, DIS-TE4 · video → VideoMatte240K, YouTubeMatte, VM800, NOVM.

---

## 5. Por qué modelos con métricas similares se ven distintos (análisis)

1. **Las métricas globales ocultan la frontera.** SAD/MSE promedian toda la imagen; un error de 0.05 en 5% de píxeles de borde pesa poco numéricamente y mucho visualmente. Dos modelos con SAD igual pueden diferir totalmente en Grad/Conn. Por eso el benchmark de Rhemann introdujo medidas perceptuales validadas con usuarios <REF>cite✦web_search:3#5:~:text=concentrate on two properties...connectivity of the foreground object</REF>.
2. **Boundary quality vs. área correcta.** U2-Net optimiza Fβ global con un saliency map a 320×320; su borde es "blocky" tras resize. BiRefNet/InSPyReNet incorporan supervisión de gradiente (BiRefNet: gradient maps como referencia explícita <REF>cite✦web_search:8#2:~:text=gradient maps serve as the target reference</REF>) y entrenan con anotaciones finísimas (DIS5K) — la señal de entrenamiento decide la calidad visual, no la métrica.
3. **Cabello y estructuras finas.** Exigen (a) anotaciones de nivel hebra en training (Human-2k, DIS5K), (b) resolución de inferencia ≥1024, (c) supervisión explícita de detalle (rama D de MODNet, DCM de ViTMatte, gradient supervision de BiRefNet). Sin esas tres, el modelo aprende "hebras = ruido" y suaviza.
4. **Transparencias.** Vidrio/tela requere alpha parcial real, no máscara binaria threshold-eada. BRIA RMBG-2.0 salida alpha 8-bit no binaria <REF>cite✦web_search:8#0:~:text=single-channel 8-bit grayscale alpha matte</REF>; los modelos binarios generan bordes duros antiestéticos <REF>cite✦web_search:8#11:~:text=binary masks that create harsh, artificial looking edges</REF>.
5. **Color contamination y halos.** Cuando se extrae F multiplicando la imagen por α (F=α·I), el borde hereda color del fondo original → halo al componer sobre fondo claro/oscuro. FBA lo resuelve prediciendo F y B conjuntamente <REF>cite✦web_search:1#10:~:text=also estimating the foreground colours</REF>; MAM2 lo señala como problema abierto del campo <REF>cite✦web_search:10#3:~:text=retains some background color...open problem in the field of matting</REF>. Mitigación práctica: descontaminar color post-hoc o usar modelos con predicción de F.
6. **Errores semánticos vs. errores de detalle.** Un modelo puede tener mejor MAD global pero "comerse" hebras (mejor connexidad peor) o segmentar el objeto equivocado en escenas multi-objeto (AIM-Net vs. especialistas en NSO). El tipo de error pesa más que la magnitud media: un error semántico gigante es peor que 0.01 de MAE difusa.
7. **Dependencia de umbral.** Modelos tipo U2-Net/IS-Net/BiRefNet emiten logits; el threshold (0.5 por defecto) cambia radicalmente el look final. BiRefNet-RMBG permite threshold custom por uso <REF>cite✦web_search:8#0:~:text=define custom thresholds for foreground-background separation</REF>.
8. **Resolución efectiva.** Inferir a 512 y reescalar destruye detalle antes de que cualquier métrica lo note si la imagen se evalúa reescalada. InSPyReNet existe precisamente porque entrenar/inferir LR mata la SOD-HR <REF>cite✦web_search:7#1:~:text=Salient object detection...studied less for high-resolution</REF>.

---

## 6. Estado del arte actual por caso de uso

| Caso | Mejor opción actual | Alternativas maduras | Experimental prometedor |
| --- | --- | --- | --- |
| **A. Background removal general (fotos, cualquier objeto)** | **BRIA RMBG-2.0** (mejor calidad; ojo licencia) / **BiRefNet-general** (MIT, casi igual) | InSPyReNet (MIT), IS-Net, U2-Net para bajo coste | ZIM (zero-shot con prompts) |
| **B. Personas (retratos)** | BiRefNet-portrait / RMBG-2.0; MODNet si hay GPU débil/tiempo real | PP-MattingV2, P3M-Net | — |
| **C. Cabello de alta precisión** | RMBG-2.0 o BiRefNet-matting a 1024+; para máximo: MatAny (SAM+ViTMatte) | MODNet (sorprendentemente bueno en 512), FBA con buen trimap | SDMatte, UIM |
| **D. Productos (e-commerce)** | **RMBG-2.0** (entrenado con ~45% objetos + e-commerce) o BiRefNet-general | InSPyReNet | — |
| **E. Objetos/estructuras finas** | BiRefNet (entrenado en DIS5K: patas, redes, bordes) | IS-Net, InSPyReNet | ZIM |
| **F. Matting de alta precisión (estudio/foto)** | ViTMatte (con trimap/pseudo-trimap de SAM) — SOTA Composition-1k por amplio margen <REF>cite✦web_search:5#12:~:text=state-of-the-art performance and outperforms prior matting works</REF> | FBA, MatteFormer, MEMatte | SDMatte |
| **G. Refinamiento interactivo** | **SAM 2** (clicks en cualquier frame, propaga) + matting head; **Matte Anything** (SAM+GroundingDINO+ViTMatte) | MAM (Matting Anything), HQ-SAM | ZIM, MAM2 (video) |
| **H. Video personas** | **MatAnyone** (CVPR'25, SOTA); RVM para tiempo real con licencia GPL acceptable | RVM (GPL-3.0, 4K76FPS), BGMv2 (si puedes capturar fondo) | MatAnyone 2, GVM (difusión) |
| **I. Video cualquier objeto** | **MAM2** (ICLR'26) | SAM 2 + propagación + refinador | — |

---

## 7. Clasificación por madurez

**Madura para producción hoy (evidencia: papers top + adopción industrial + licencias claras):**

- BiRefNet (MIT; en rembg, HF transformers, FAL; SOTA verificado en DIS/COD/HRSOD) <REF>cite✦web_search:11#9:~:text=BiRefNet itself...code and weights under MIT, free for commercial use</REF>
- BRIA RMBG-2.0 (si se paga licencia comercial; >5M descargas de v1.4, API en fal.ai/Replicate)
- U2-Net/U2NetP (Apache-2.0; líder incuestionable de adopción: Pixelmator, rembg; aceptable solo para casos simples)
- InSPyReNet (MIT; muy fuerte en comparativas comunitarias)
- MODNet, RVM, BackgroundMattingV2 (licencias y límites claros; RVM/BGMv2 probados en producción de video)
- SAM/SAM 2 (Apache-2.0; ecosistema, soporte, infraestructura maduros)

**Prometedora pero con condiciones:**

- ViTMatte (máxima precisión, pero exige trimap/pseudo-trimap → pipeline compuesto)
- MatAnyone/MatAnyone 2 (SOTA video, licencia académica restrictiva)
- ZIM (recién ICCV'25; zero-shot real; falta validación industrial amplia)

**Todavía experimental:**

- MAM2 (video matting de cualquier objeto; ICLR 2026)
- GVM (matting generativo con difusión; ordenes de magnitud más lento que RVM <REF>cite✦web_search:2#0:~:text=inferior speed with RVM due to our model is much larger</REF>)
- SDMatte/UIM/MEMatte (publicados pero sin ecosistema de despliegue)
- Matting de transparencias extremas y color decontamination en general: problema abierto declarado <REF>cite✦web_search:10#3:~:text=we consider this an open problem</REF>

---

## 8. Recomendación de arquitectura (evidencia vs. opinión)

**Sobre evidencia:**

1. BiRefNet-general y RMBG-2.0 comparten arquitectura y encabezan las comparativas cualitativas y cuantitativas públicas de eliminación de fondos; BiRefNet es SOTA verificado en tres benchmarks (DIS/COD/HRSOD).
2. La comunidad y herramientas (rembg, ComfyUI, FAL) ya estandarizaron BiRefNet/RMBG como el punto de partida; U2-Net queda relegado a dispositivos mínimos.
3. SAM 2 es el estándar de facto para interacción (clicks, cajas) y video, con licencia Apache-2.0.
4. Las métricas que predicen satisfacción de usuario son Grad/Conn/HCE, no SAD solo — tu evaluación interna debe usarlas.
5. MatAnyone domina los benchmarks de video matting (MAD 3.70 vs 4.37 RVM en YouTubeMatte, y mejores dtSSD) <REF>cite✦web_search:10#3:~:text=MatAnyone Yang et al. (2025)|3.70|2.35|11.45|1.81</REF>.

**Opinión (marcada como tal):** para una aplicación real de procesamiento de imágenes construiría:

1. **Pipeline principal imágenes:** BiRefNet-general (o RMBG-2.0 si el presupuesto de licencia es aceptable y necesitas el plus legal/calidad) como extractor automático, a 1024×1024 mínimo, con salida alpha no binarizada (usar el logit suave como alpha, threshold configurable).
2. **Modo "alta precisión":** SAM (o ZIM) para máscara inicial → pseudo-trimap (dilate/erode de la máscara) → ViTMatte. Es exactamente el patrón Matte Anything <REF>cite✦web_search:6#11:~:text=pseudo-trimap...processed by ViTMatte</REF> y logra calidad de estudio con clicks.
3. **Modo interactivo:** integrar SAM 2 nativamente (clicks positivos/negativos, propagación a video) y usar la máscara resultante como guía del refiner (ViTMatte/BiRefNet-matting).
4. **Video:** MatAnyone (o RVM si la licencia GPL encaja o necesitas máxima velocidad). Mantener dtSSD en el monitoring.
5. **Refinamiento edge-aware:** supervisión/loss de gradiente en cualquier fine-tuning (lección BiRefNet); post-proceso tipo guided filter solo como pulido final.
6. **Evaluación interna:** suite con DIS5K-TE, AIM-500, P3M-500-NP + subset propio de dominio; reportar MAD, Grad, Conn, SAD-T, HCE y *estudio humano pareado* (los benchmarks sintéticos sobreestiman la calidad percibida).
7. **Riesgos a vigilar:** licencias (RMBG-2.0 = CC BY-NC; RVM = GPL-3.0; MatAnyone = NTU S-Lab), color contamination en composición (considerar predicción de F o descontaminación), y degradación en multi-objeto/escenas NSO donde los modelos automáticos aún fallan (caso AIM-500 tipo NS) <REF>cite✦web_search:6#1:~:text=performance drops seriously for non-salient images</REF>.

---

## 9. Mejores papers, repositorios y datasets (selección)

**Papers clave:** U2-Net (PR'20) · DIS/IS-Net (ECCV'22) · InSPyReNet (ACCV'22) · BiRefNet (CAAI AIR'24) · MODNet (AAAI'22) · BGMv2 (CVPR'21) · RVM (WACV'22) · FBA (2020) · ViTMatte (Inf. Fusion'24) · SAM (ICCV'23) · SAM 2 (ICLR'25) · ZIM (ICCV'25) · MatAnyone (CVPR'25) · MAM2 (ICLR'26) · Survey: "Deep Image Matting: A Comprehensive Survey" (2023).

**Repositorios:** xuebinqin/U-2-Net · ZhengPeng7/BiRefNet (+ HF ZhengPeng7/BiRefNet) · Bria-AI/RMBG-2.0 · danielgatis/rembg · PeterL1n/RobustVideoMatting · PeterL1n/BackgroundMattingV2 · hustvl/ViTMatte · pq-yang/MatAnyone · naver-ai/ZIM · facebookresearch/sam2 · SHI-Labs/Matting-Anything · plemeri/InSPyReNet · PaddlePaddle/PaddleSeg (PP-Matting).

**Datasets esenciales:** DIS5K · DUTS · AIM-500 · Composition-1k (DIM) · Human-2k · P3M-10k · HIM2k · Trans-460/TOM · VideoMatte240K · YouTubeMatte/VM800/NOVM · SA-V (video) · SA1B-Matte/MicroMat-3K (zero-shot matting).