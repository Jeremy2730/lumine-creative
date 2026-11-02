deactivate
Remove-Item -Recurse -Force .\.venv
py -0p
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python --version
python -m pip install --upgrade pip
python -m pip --version
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
python -m pip check

python main.py

dir
npx repomix


git diff --check     detecta errores comunes de espacios en los cambios.
git status           confirma los archivos modificados, eliminados y nuevos.
git add -A           publicar el estado



## Método **LANCZOS** 

¿Quéhace? 

Analiza una zona relativamente amplia de píxeles para calcular los nuevos.

Resultado: Alta calidad, buen detalle         


## Método **BICUBIC**  

¿Quéhace? 

Usa una interpolación más suave basada en píxeles vecinos    

Resultado: Suave, buena calidad    


## Método **BILINEAR** 

¿Quéhace? 

Usa una interpolación más sencilla entre   vecinos  

Resultado: Más rápida, pero menos detalle   


## Método **NEAREST**

¿Quéhace? 

Toma el píxel más cercano y lo copia

Resultado: Muy duro/pixelado; útil para gráficos donde no quieres mezclar colores
