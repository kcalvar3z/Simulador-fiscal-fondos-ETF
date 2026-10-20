"""Abre la app publicada y, si Streamlit Community Cloud la ha puesto en reposo, la despierta.

La ejecuta la tarea programada `.github/workflows/despertar-app.yml`. Hace falta un navegador
de verdad: la app solo se despierta al pulsar el botón de la pantalla de reposo.

Uso: python despertar_app.py <url>
Termina con error si la app no muestra el simulador en el tiempo de espera, para que GitHub
marque la ejecución como fallida y avise por correo.
"""

import re
import sys
import time

from playwright.sync_api import Page, sync_playwright

TEXTO_DE_LA_APP = "Vender un fondo o un ETF"  # título de la cabecera de app.py
BOTON_DESPERTAR = re.compile(r"get this app back up", re.IGNORECASE)
ESPERA_MAXIMA_S = 300  # al despertar, la app puede tardar un par de minutos en arrancar
INTERVALO_S = 10


def app_cargada(pagina: Page) -> bool:
    """La app va dentro de un iframe en Streamlit Community Cloud: se busca en todos los marcos."""
    for marco in pagina.frames:
        try:
            if TEXTO_DE_LA_APP in marco.inner_text("body", timeout=2000):
                return True
        except Exception:  # marcos que aún cargan o ya no existen
            continue
    return False


def despertar(url: str) -> bool:
    with sync_playwright() as p:
        navegador = p.chromium.launch()
        pagina = navegador.new_page()
        pagina.goto(url, wait_until="domcontentloaded", timeout=90_000)
        inicio = time.monotonic()
        pulsado = False
        while time.monotonic() - inicio < ESPERA_MAXIMA_S:
            if app_cargada(pagina):
                estado = "despertada" if pulsado else "ya estaba activa"
                print(f"App {estado} en {time.monotonic() - inicio:.0f} s.")
                navegador.close()
                return True
            boton = pagina.get_by_role("button", name=BOTON_DESPERTAR)
            if not pulsado and boton.count() > 0:
                print("La app estaba en reposo: se pulsa el botón para despertarla.")
                boton.first.click()
                pulsado = True
            time.sleep(INTERVALO_S)
        print(f"La app no cargó en {ESPERA_MAXIMA_S} s.", file=sys.stderr)
        pagina.screenshot(path="estado-app.png", full_page=True)
        navegador.close()
        return False


if __name__ == "__main__":
    sys.exit(0 if despertar(sys.argv[1]) else 1)
