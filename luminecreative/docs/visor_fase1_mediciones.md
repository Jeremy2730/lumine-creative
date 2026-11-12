# Visor interactivo, fase 1 — mediciones y problemas pendientes

Medido con `python scripts/benchmark_viewport_render.py` (2 CPU, contenedor Linux, Pillow 12.x,
imagen RGBA, viewport 1200×700). **Solo mide `ViewportRenderer.render`** (recorte + remuestreo, sin Tk).
El coste de `ImageTk.PhotoImage` y del canvas no se pudo medir aquí (no hay Tk); la aplicación lo
registra en `ImagePanel.render_timings` / `render_stats()` y, si un repintado pasa de 100 ms, en el log (INFO).

| Imagen | Primer render | Rueda (20 pasos) media / p95 | Paneo 100 % | Paneo 25 % | Paneo 600 % media / p95 |
|---|---|---|---|---|---|
| 4000×3000 (12 MP) | 59 ms | 21 / 56 ms | 0,4 ms | 0,0 ms | 17 / 22 ms |
| 8000×6000 (48 MP) | 378 ms | 56 / 282 ms | 0,5 ms | 2,2 ms | 51 / 61 ms |
| 12000×9000 (108 MP) | 502 ms | 103 / 923 ms | 0,5 ms | 6,5 ms | 340 / 401 ms |

## Problema 1 (pendiente): con zoom alto el coste depende del tamaño de la imagen RGBA

`ViewportRenderer._pixels` llama a `level.resize(size, BICUBIC, box=box)` sobre la imagen completa.
Con modo RGBA, Pillow premultiplica el alfa de TODA la imagen antes de remuestrear, aunque `box` sea
un trozo pequeño. Medido en 12000×9000:

- `resize(box=…)` sobre la imagen entera: **322 ms** (RGBA) frente a 2 ms (RGB).
- recortar primero un rectángulo entero con margen y luego `resize(box=…)`: **2 ms** (RGBA y RGB).

El docstring del renderizador afirma que con zoom ≥ 1 «el coste no depende del tamaño de la imagen»;
con RGBA no se cumple. Efecto: paneo y rueda a zoom alto (≥ 200 %) en imágenes de más de ~40 MP
caen por debajo de ~20 fps. No se corrigió en esta fase (regla: no tocar el renderizador sin
una decisión explícita ni improvisar); la corrección propuesta es pequeña y localizada en `_pixels`.

## Problema 2 (pendiente): construir niveles reducidos bloquea el hilo de la interfaz

El primer render ajustado y el primer paso de zoom a cada nivel nuevo construyen `Image.reduce(2**k)`
de la imagen completa en el hilo de Tk (378 ms con 48 MP, 502 ms con 108 MP; hasta 923 ms en un paso de
rueda en 108 MP). Es lo que el propio renderizador deja anotado como «fase posterior»
(niveles en segundo plano). Durante ese tiempo la ventana no responde.

## Qué sí está acotado en esta fase

- Paneo al 100 % y a zooms bajos: ≤ 7 ms incluso con 108 MP.
- Una ráfaga de eventos de rueda/arrastre produce un solo repintado por cada 16 ms.
