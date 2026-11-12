"""main.py

Responsabilidad:
    - Arrancar la aplicación (crear DesignApplication y ejecutarla).

No conoce:
    - GUI, motor de procesamiento ni configuración; todo eso lo arma
      app/application.py.
"""
from app.application import DesignApplication


def main() -> None:
    DesignApplication().run()


if __name__ == "__main__":
    main()
