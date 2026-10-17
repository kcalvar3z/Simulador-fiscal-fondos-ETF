"""Gráficos del simulador para LinkedIn.

`figura_fondo_frente_a_etf` dibuja los resultados del simulador; no calcula nada, así que
las cifras del gráfico son siempre las de `escenarios.py`.

`python -m simulador.graficos` regenera las imágenes de `contenido/` con los casos de los
posts. Exportar a PNG requiere Chrome: instálalo una vez con `plotly_get_chrome`.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import plotly.graph_objects as go

from simulador import normativa
from simulador.escenarios import Escenario, ResultadoEscenario, comparar_escenarios
from simulador.lotes import Lote, Venta

ANCHO, ALTO = 1080, 1350  # formato vertical de LinkedIn

# Estética de la app (terminal financiera). Los tres colores de las series están validados
# con la skill dataviz en modo oscuro sobre FONDO: banda de luminosidad, croma, separación
# con daltonismo (ΔE ≥ 8) y contraste ≥ 3:1.
FONDO = "#0a0a0a"
TITULOS = "#ffffff"
TEXTO = "#e8e8ed"
TEXTO_SECUNDARIO = "#a0a0a8"
ACENTO = "#f5aa20"
REJILLA = "#1f1f24"
COLOR_RETENCION = "#ca7c18"
COLOR_RENTA = "#00a0b4"
COLOR_APLAZADO = "#5b6ee8"
FUENTE = "IBM Plex Sans, Liberation Sans, Arial, sans-serif"
FUENTE_CIFRAS = "IBM Plex Mono, DejaVu Sans Mono, monospace"

# Geometría (px). El área del gráfico va de _MARGEN_SUPERIOR a ALTO − _MARGEN_INFERIOR.
_MARGEN_LATERAL = 70
_MARGEN_SUPERIOR = 470
_MARGEN_INFERIOR = 150
_GROSOR_BARRA = 0.26  # fracción del hueco de cada escenario
_MEDIA_BARRA_PX = round(_GROSOR_BARRA * (ALTO - _MARGEN_SUPERIOR - _MARGEN_INFERIOR) / 3 / 2)


def _y(desde_arriba_px: float) -> float:
    """Convierte una distancia en píxeles desde el borde superior a coordenada `paper` de Plotly."""
    alto_grafico = ALTO - _MARGEN_SUPERIOR - _MARGEN_INFERIOR
    return 1 - (desde_arriba_px - _MARGEN_SUPERIOR) / alto_grafico


PIE = (
    f"Elaboración propia. IRPF {normativa.EJERCICIO}, territorio común. "
    "Cálculo orientativo; no constituye asesoramiento fiscal."
)


def euros(importe: Decimal) -> str:
    """Formato del post, sin céntimos: Decimal("1980") → "1.980 €"."""
    unidades = importe.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return f"{unidades:,}".replace(",", ".") + " €"


@dataclass(frozen=True)
class _Barra:
    escenario: str
    detalle: str
    retencion: Decimal
    en_renta: Decimal
    aplazado: Decimal
    rotulo: str  # cifra al final de la barra

    @property
    def total(self) -> Decimal:
        return self.retencion + self.en_renta + self.aplazado


def figura_fondo_frente_a_etf(resultados: Sequence[ResultadoEscenario], descripcion_caso: str) -> go.Figure:
    """Barras apiladas: qué se paga hoy (retención y Renta) y qué se aplaza en cada escenario.

    Pensado para una venta con ganancia: la retención no supera la cuota y el latente es positivo.
    """
    por_escenario = {resultado.escenario: resultado for resultado in resultados}
    reembolso = por_escenario[Escenario.REEMBOLSO_FONDO]
    traspaso = por_escenario[Escenario.TRASPASO_FONDO]
    etf = por_escenario[Escenario.VENTA_ETF]
    if reembolso.ganancia_patrimonial <= 0 or not 0 <= reembolso.retencion <= reembolso.cuota:
        raise ValueError("Este gráfico representa una venta con ganancia; el caso indicado no lo es.")

    cero = Decimal("0")
    barras = [
        _Barra(
            "Reembolsar el fondo",
            f"{euros(reembolso.retencion)} de retención al vender + "
            f"{euros(reembolso.regularizacion_renta)} en la Renta",
            reembolso.retencion,
            reembolso.regularizacion_renta,
            cero,
            f"{euros(reembolso.cuota)} este año",
        ),
        _Barra(
            "Traspasar a otro fondo",
            "Sin impuesto ni retención hoy: tributa cuando reembolses",
            cero,
            cero,
            traspaso.impuesto_latente,
            f"0 € hoy<br>{euros(traspaso.impuesto_latente)} aplazados",
        ),
        _Barra(
            "Vender el ETF",
            f"Sin retención: {euros(etf.cuota)} en la Renta. No admite traspaso",
            cero,
            etf.cuota,
            cero,
            f"{euros(etf.cuota)} este año",
        ),
    ]
    categorias = [barra.escenario for barra in barras]

    figura = go.Figure()
    for nombre, campo, color in [
        ("Retención al vender", "retencion", COLOR_RETENCION),
        ("Pago en la Renta", "en_renta", COLOR_RENTA),
        ("Aplazado con el traspaso", "aplazado", COLOR_APLAZADO),
    ]:
        figura.add_bar(
            y=categorias,
            x=[getattr(barra, campo) for barra in barras],
            name=nombre,
            orientation="h",
            width=_GROSOR_BARRA,
            marker={"color": color, "line": {"color": FONDO, "width": 2}},
            hoverinfo="skip",
        )

    maximo = max(barra.total for barra in barras)
    for barra in barras:
        # Escenario y detalle encima de cada barra; la cifra, al final.
        figura.add_annotation(
            x=0,
            y=barra.escenario,
            yshift=_MEDIA_BARRA_PX + 8,
            xanchor="left",
            yanchor="bottom",
            align="left",
            showarrow=False,
            text=f"<b>{barra.escenario}</b><br><span style='color:{TEXTO_SECUNDARIO}'>{barra.detalle}</span>",
            font={"size": 25, "color": TITULOS},
        )
        figura.add_annotation(
            x=barra.total,
            y=barra.escenario,
            xshift=14,
            xanchor="left",
            align="left",
            showarrow=False,
            text=barra.rotulo,
            font={"family": FUENTE_CIFRAS, "size": 25, "color": TEXTO},
        )

    # Cabecera y pie colocados en píxeles desde el borde superior de la imagen.
    figura.add_shape(
        type="line", xref="paper", yref="paper", x0=0, x1=1, y0=_y(56), y1=_y(56), line={"color": ACENTO, "width": 6}
    )
    for desde_arriba, texto, fuente in [
        (92, f"IRPF {normativa.EJERCICIO} · FONDO FRENTE A ETF", {"family": FUENTE_CIFRAS, "size": 22, "color": ACENTO}),
        (134, "<b>Con un fondo puedes aplazar el impuesto.<br>Con un ETF, no.</b>", {"size": 46, "color": TITULOS}),
        (284, descripcion_caso, {"size": 24, "color": TEXTO_SECUNDARIO}),
        (ALTO - 80, PIE, {"size": 19, "color": TEXTO_SECUNDARIO}),
    ]:
        figura.add_annotation(
            xref="paper",
            yref="paper",
            x=0,
            y=_y(desde_arriba),
            xanchor="left",
            yanchor="top",
            align="left",
            showarrow=False,
            text=texto,
            font=fuente,
        )

    figura.update_layout(
        width=ANCHO,
        height=ALTO,
        barmode="stack",
        barcornerradius=4,
        separators=",.",
        paper_bgcolor=FONDO,
        plot_bgcolor=FONDO,
        font={"family": FUENTE, "color": TEXTO},
        margin={"l": _MARGEN_LATERAL, "r": _MARGEN_LATERAL, "t": _MARGEN_SUPERIOR, "b": _MARGEN_INFERIOR},
        legend={
            "orientation": "h",
            "x": 0,
            "y": _y(372),
            "xanchor": "left",
            "yanchor": "top",
            "font": {"size": 21, "color": TEXTO},
            "traceorder": "normal",
        },
        xaxis={
            "range": [0, maximo * Decimal("1.55")],  # deja sitio a la cifra del final de cada barra
            "ticksuffix": " €",
            "tickformat": ",d",
            "tickfont": {"family": FUENTE_CIFRAS, "size": 18, "color": TEXTO_SECUNDARIO},
            "gridcolor": REJILLA,
            "zeroline": True,
            "zerolinecolor": "#2d2d32",
            "showline": False,
        },
        yaxis={
            "categoryorder": "array",
            "categoryarray": categorias,
            "autorange": "reversed",
            "showticklabels": False,
            "showgrid": False,
        },
    )
    return figura


# --- Casos de los posts ---------------------------------------------------------------------------

DESCRIPCION_CASO_B = (
    "Inversión de 20.000 € que hoy vale 30.000 € (ganancia de 10.000 €),<br>"
    f"sin otras rentas del ahorro. Ejercicio {normativa.EJERCICIO}."
)


def caso_b() -> tuple[ResultadoEscenario, ...]:
    """Caso B de examples.md: 20.000 € invertidos que hoy valen 30.000 €, sin otras rentas."""
    lotes = [Lote(date(2023, 1, 15), Decimal("1000"), Decimal("20"))]
    venta = Venta(date(2026, 10, 16), Decimal("1000"), Decimal("30"))
    return comparar_escenarios(lotes, venta)


def main() -> None:
    carpeta = Path(__file__).resolve().parent.parent / "contenido" / "2026-10-17-fondo-vs-etf"
    carpeta.mkdir(parents=True, exist_ok=True)
    figura = figura_fondo_frente_a_etf(caso_b(), DESCRIPCION_CASO_B)
    figura.write_image(carpeta / "grafico.png", width=ANCHO, height=ALTO)


if __name__ == "__main__":
    main()
