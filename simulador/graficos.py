"""Gráficos del simulador: el de LinkedIn y los de la app.

Las figuras dibujan los resultados del simulador; no calculan nada, así que sus cifras
son siempre las de `escenarios.py`.

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
from simulador.calculo import desglose_cuota
from simulador.escenarios import Escenario, ResultadoEscenario, ResultadoPlan, comparar_escenarios
from simulador.lotes import Lote, Venta
from simulador.rentabilidad import Rentabilidad

# Estética de la app (terminal financiera). Los colores de las series están validados con la
# skill dataviz en modo oscuro sobre FONDO: banda de luminosidad, croma, separación con
# daltonismo (ΔE ≥ 8) y contraste ≥ 3:1.
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

# Estética del gráfico de LinkedIn: informe analítico sobre blanco, apaisado. Colores validados
# con la skill dataviz en modo claro sobre blanco (todas las parejas, sin avisos).
INFORME_ANCHO, INFORME_ALTO = 1200, 600
INFORME_ESCALA = 2  # se exporta a 2400 × 1200 px para que se vea nítido
INFORME_FONDO = "#ffffff"
INFORME_TEXTO = "#222222"
INFORME_TEXTO_SECUNDARIO = "#666666"
INFORME_EJES = "#a0a0a0"
INFORME_REJILLA = "#e6e6e6"
INFORME_RETENCION = "#c0392b"
INFORME_RENTA = "#cf7f00"
INFORME_APLAZADO = "#3b6aa0"  # filete del panel del diferimiento
INFORME_PANEL = "#f4f5f7"
INFORME_FUENTE = "DejaVu Sans, Liberation Sans, Arial, sans-serif"

PIE = (
    f"Elaboración propia. IRPF {normativa.EJERCICIO}, territorio común. "
    "Cálculo orientativo; no constituye asesoramiento fiscal."
)


def euros(importe: Decimal) -> str:
    """Formato del post, sin céntimos: Decimal("1980") → "1.980 €"."""
    unidades = importe.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return f"{unidades:,}".replace(",", ".") + " €"


def euros_con_signo(importe: Decimal) -> str:
    """Decimal("-1140") → "-1.140 €"; Decimal("10000") → "+10.000 €"."""
    texto = euros(importe)
    return texto if texto.startswith("-") or texto == "0 €" else f"+{texto}"


def porcentaje(valor: Decimal) -> str:
    """Rentabilidad con signo y un decimal: Decimal("0.5") → "+50,0 %"."""
    texto = f"{(valor * 100).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP):+.1f}"
    return texto.replace(".", ",") + " %"


def tipo_impositivo(tipo: Decimal) -> str:
    """Tipo de la escala: Decimal("0.19") → "19 %"."""
    return f"{(tipo * 100).normalize():f}".replace(".", ",") + " %"


# --- Gráfico de LinkedIn ----------------------------------------------------------------------------


@dataclass(frozen=True)
class _Barra:
    escenario: str
    detalle: str
    retencion: Decimal
    en_renta: Decimal
    rotulo: str  # cifra encima de la barra

    @property
    def total(self) -> Decimal:
        return self.retencion + self.en_renta


def texto_diferimiento(impuesto_latente: Decimal) -> str:
    """Explicación del panel lateral; los saltos de línea son manuales porque Plotly no ajusta texto."""
    return (
        "<b>¿Por qué 0 € con el traspaso?</b><br><br>"
        "El traspaso entre fondos no tributa:<br>"
        "la ganancia se <b>difiere</b>, es decir, se<br>"
        "aplaza hasta que reembolses.<br><br>"
        f"Los {euros(impuesto_latente)} no desaparecen: se<br>"
        "pagan al reembolsar el nuevo fondo,<br>"
        "que conserva el coste y la fecha de<br>"
        "compra originales (art. 94 LIRPF).<br><br>"
        "Un ETF no admite traspaso: venderlo<br>"
        "siempre tributa en el ejercicio."
    )


def figura_fondo_frente_a_etf(resultados: Sequence[ResultadoEscenario], descripcion_caso: str) -> go.Figure:
    """Barras apiladas con lo que se paga este año en cada escenario.

    La barra del traspaso queda vacía (no se paga nada hoy) y un panel lateral explica el
    diferimiento con el impuesto latente. Pensado para una venta con ganancia.
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
            f"{euros(reembolso.retencion)} de retención + {euros(reembolso.regularizacion_renta)} en la Renta",
            reembolso.retencion,
            reembolso.regularizacion_renta,
            f"{euros(reembolso.cuota)} este año",
        ),
        _Barra("Traspasar a otro fondo", "Sin impuesto ni retención hoy", cero, cero, "0 € este año"),
        _Barra("Vender el ETF", "Sin retención; no admite traspaso", cero, etf.cuota, f"{euros(etf.cuota)} este año"),
    ]
    # Escenario y, debajo, su detalle en gris, como etiqueta del eje.
    categorias = [
        f"<b>{barra.escenario}</b><br><span style='font-size:13px;color:{INFORME_TEXTO_SECUNDARIO}'>"
        f"{barra.detalle}</span>"
        for barra in barras
    ]

    figura = go.Figure()
    for nombre, campo, color in [
        ("Retención al vender", "retencion", INFORME_RETENCION),
        ("Pago IRPF", "en_renta", INFORME_RENTA),
    ]:
        figura.add_bar(
            x=categorias,
            y=[getattr(barra, campo) for barra in barras],
            name=nombre,
            width=0.42,
            marker={"color": color, "line": {"color": INFORME_FONDO, "width": 2}},
            hoverinfo="skip",
        )
    for categoria, barra in zip(categorias, barras):
        figura.add_annotation(
            x=categoria,
            y=barra.total,
            yshift=6,
            yanchor="bottom",
            showarrow=False,
            text=barra.rotulo,
            font={"size": 16, "color": INFORME_TEXTO},
        )

    # Cabecera y pie, a 24 px del borde izquierdo de la imagen.
    for desde_arriba, texto, fuente in [
        (18, "<b>Con un fondo puedes aplazar el impuesto. Con un ETF, no.</b>", {"size": 22, "color": INFORME_TEXTO}),
        (52, descripcion_caso, {"size": 14, "color": INFORME_TEXTO_SECUNDARIO}),
        (INFORME_ALTO - 26, PIE, {"size": 12, "color": INFORME_TEXTO_SECUNDARIO}),
    ]:
        figura.add_annotation(
            xref="paper",
            yref="paper",
            x=_x_informe(24),
            y=_y_informe(desde_arriba),
            xanchor="left",
            yanchor="top",
            align="left",
            showarrow=False,
            text=texto,
            font=fuente,
        )

    # Panel lateral con la explicación del diferimiento: fondo gris claro y filete azul a la izquierda.
    izquierda, derecha = INFORME_ANCHO - _INFORME_MARGEN_DERECHO + 30, INFORME_ANCHO - 24
    arriba, abajo = _INFORME_MARGEN_SUPERIOR, INFORME_ALTO - _INFORME_MARGEN_INFERIOR
    figura.add_shape(
        type="rect",
        xref="paper",
        yref="paper",
        x0=_x_informe(izquierda),
        x1=_x_informe(derecha),
        y0=_y_informe(abajo),
        y1=_y_informe(arriba),
        fillcolor=INFORME_PANEL,
        line={"width": 0},
        layer="below",
    )
    figura.add_shape(
        type="line",
        xref="paper",
        yref="paper",
        x0=_x_informe(izquierda),
        x1=_x_informe(izquierda),
        y0=_y_informe(abajo),
        y1=_y_informe(arriba),
        line={"color": INFORME_APLAZADO, "width": 4},
    )
    figura.add_annotation(
        xref="paper",
        yref="paper",
        x=_x_informe(izquierda + 20),
        y=_y_informe(arriba + 20),
        xanchor="left",
        yanchor="top",
        align="left",
        showarrow=False,
        text=texto_diferimiento(traspaso.impuesto_latente),
        font={"size": 14, "color": INFORME_TEXTO},
    )

    maximo = max(barra.total for barra in barras)
    eje = {"showline": True, "linecolor": INFORME_EJES, "linewidth": 1, "ticks": "outside", "tickcolor": INFORME_EJES}
    figura.update_layout(
        width=INFORME_ANCHO,
        height=INFORME_ALTO,
        barmode="stack",
        separators=",.",
        paper_bgcolor=INFORME_FONDO,
        plot_bgcolor=INFORME_FONDO,
        font={"family": INFORME_FUENTE, "color": INFORME_TEXTO, "size": 14},
        margin={
            "l": _INFORME_MARGEN_IZQUIERDO,
            "r": _INFORME_MARGEN_DERECHO,
            "t": _INFORME_MARGEN_SUPERIOR,
            "b": _INFORME_MARGEN_INFERIOR,
        },
        legend={
            "orientation": "h",
            "x": 0.01,
            "y": 1.0,
            "xanchor": "left",
            "yanchor": "top",
            "bgcolor": "rgba(0,0,0,0)",
            "font": {"size": 14, "color": INFORME_TEXTO},
            "traceorder": "normal",
        },
        xaxis={**eje, "tickfont": {"size": 14, "color": INFORME_TEXTO}},
        yaxis={
            **eje,
            "title": {"text": f"Impuesto en el IRPF {normativa.EJERCICIO} (€)", "font": {"size": 14}},
            "range": [0, maximo * Decimal("1.4")],  # aire para la leyenda y las cifras
            "tickformat": ",d",
            "ticksuffix": " €",
            "tickfont": {"size": 13, "color": INFORME_TEXTO_SECUNDARIO},
            "gridcolor": INFORME_REJILLA,
            "zeroline": False,
        },
    )
    return figura


# Geometría del informe (px). El área del gráfico va de los márgenes hacia dentro; a la
# derecha queda sitio para el panel del diferimiento.
_INFORME_MARGEN_IZQUIERDO = 90
_INFORME_MARGEN_DERECHO = 370
_INFORME_MARGEN_SUPERIOR = 100
_INFORME_MARGEN_INFERIOR = 110


def _x_informe(desde_izquierda_px: float) -> float:
    """Convierte una distancia en píxeles desde el borde izquierdo a coordenada `paper` de Plotly."""
    ancho_grafico = INFORME_ANCHO - _INFORME_MARGEN_IZQUIERDO - _INFORME_MARGEN_DERECHO
    return (desde_izquierda_px - _INFORME_MARGEN_IZQUIERDO) / ancho_grafico


def _y_informe(desde_arriba_px: float) -> float:
    """Convierte una distancia en píxeles desde el borde superior a coordenada `paper` de Plotly."""
    alto_grafico = INFORME_ALTO - _INFORME_MARGEN_SUPERIOR - _INFORME_MARGEN_INFERIOR
    return 1 - (desde_arriba_px - _INFORME_MARGEN_SUPERIOR) / alto_grafico


# --- Gráficos de la app ----------------------------------------------------------------------------


def _estilo_app(figura: go.Figure, alto: int) -> go.Figure:
    """Fondo transparente y tipografía de la app; los colores de texto son los del tema oscuro."""
    figura.update_layout(
        height=alto,
        separators=",.",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": FUENTE, "color": TEXTO, "size": 14},
        margin={"l": 10, "r": 10, "t": 40, "b": 10},
        legend={"orientation": "h", "x": 0, "y": 1.02, "xanchor": "left", "yanchor": "bottom"},
        hoverlabel={"font": {"family": FUENTE}},
    )
    return figura


def figura_rentabilidad(filas: Sequence[tuple[str, Rentabilidad]]) -> go.Figure:
    """Barras por inversión: lo invertido frente a lo que vale hoy, con la rentabilidad al final."""
    nombres = [nombre for nombre, _ in filas]
    figura = go.Figure()
    for serie, campo, color in [
        ("Invertido", "invertido", COLOR_APLAZADO),
        ("Valor hoy", "valor_actual", COLOR_RENTA),
    ]:
        importes = [getattr(r, campo) for _, r in filas]
        figura.add_bar(
            y=nombres,
            x=importes,
            name=serie,
            orientation="h",
            marker={"color": color, "line": {"color": FONDO, "width": 2}},
            customdata=[euros(importe) for importe in importes],
            hovertemplate="%{y}<br>" + serie + ": %{customdata}<extra></extra>",
        )
    maximo = max(max(r.invertido, r.valor_actual) for _, r in filas)
    for nombre, r in filas:
        anual = f"{porcentaje(r.anual)} anual" if r.anual is not None else "menos de un año"
        figura.add_annotation(
            x=max(r.invertido, r.valor_actual),
            y=nombre,
            xshift=10,
            xanchor="left",
            showarrow=False,
            text=f"{euros_con_signo(r.ganancia)} · {porcentaje(r.total)} · {anual}",
            font={"family": FUENTE_CIFRAS, "size": 14, "color": TEXTO},
        )
    figura.update_layout(
        barmode="group",
        bargap=0.35,
        bargroupgap=0.08,
        barcornerradius=4,
        xaxis={
            "range": [0, maximo * Decimal("1.7")],  # sitio para la rentabilidad
            "ticksuffix": " €",
            "tickformat": ",d",
            "gridcolor": REJILLA,
            "zerolinecolor": "#2d2d32",
            "tickfont": {"family": FUENTE_CIFRAS, "color": TEXTO_SECUNDARIO},
        },
        yaxis={"autorange": "reversed", "tickfont": {"size": 15, "color": TEXTO}},
    )
    return _estilo_app(figura, alto=110 + 95 * len(filas))


@dataclass(frozen=True)
class PasoCascada:
    etiqueta: str
    importe: Decimal
    total: bool = False  # True: subtotal o resultado; False: suma o resta


def pasos_cascada(plan: ResultadoPlan) -> tuple[PasoCascada, ...]:
    """De la ganancia de lo que se vende al neto tras el IRPF, en euros.

    El impuesto se desglosa por tramos como si la ganancia se sumara sin más a la base del
    ahorro; si las compensaciones (art. 49 LIRPF) lo reducen, la diferencia aparece como
    ahorro. Las posiciones traspasadas no entran: no tributan hoy. Vacío si no se vende nada.
    """
    vendidas = [p for p in plan.posiciones if p.operacion is not Escenario.TRASPASO_FONDO]
    if not vendidas:
        return ()
    pasos = [
        PasoCascada(f"{'Ganancia' if p.ganancia_patrimonial >= 0 else 'Pérdida'} · {p.nombre}", p.ganancia_patrimonial)
        for p in vendidas
    ]
    resultado = sum((p.ganancia_patrimonial for p in vendidas), Decimal("0"))
    if len(vendidas) > 1:
        pasos.append(PasoCascada("Resultado de la venta", resultado, total=True))

    base = plan.base_ahorro_sin_operaciones
    tramos = desglose_cuota(base, base + resultado) if resultado > 0 else ()
    for tramo in tramos:
        pasos.append(PasoCascada(f"IRPF · {euros(tramo.importe)} al {tipo_impositivo(tramo.tipo)}", -tramo.cuota))
    ahorro = sum((tramo.cuota for tramo in tramos), Decimal("0")) - plan.cuota
    if ahorro != 0:
        pasos.append(PasoCascada("Ahorro por compensaciones", ahorro))
    pasos.append(PasoCascada("Neto tras el IRPF", resultado - plan.cuota, total=True))
    return tuple(pasos)


def figura_cascada(pasos: Sequence[PasoCascada]) -> go.Figure:
    figura = go.Figure(
        go.Waterfall(
            x=[paso.etiqueta.replace(" · ", "<br>") for paso in pasos],
            y=[paso.importe for paso in pasos],
            measure=["total" if paso.total else "relative" for paso in pasos],
            text=[euros(paso.importe) if paso.total else euros_con_signo(paso.importe) for paso in pasos],
            textposition="outside",
            textfont={"family": FUENTE_CIFRAS, "color": TEXTO},
            increasing={"marker": {"color": COLOR_RENTA}},
            decreasing={"marker": {"color": COLOR_RETENCION}},
            totals={"marker": {"color": COLOR_APLAZADO}},
            connector={"line": {"color": "#2d2d32", "width": 1}},
            hovertemplate="%{x}: %{text}<extra></extra>",
        )
    )
    figura.update_layout(
        showlegend=False,
        yaxis={
            "ticksuffix": " €",
            "tickformat": ",d",
            "gridcolor": REJILLA,
            "zerolinecolor": "#2d2d32",
            "tickfont": {"family": FUENTE_CIFRAS, "color": TEXTO_SECUNDARIO},
        },
        xaxis={"tickfont": {"size": 13, "color": TEXTO}},
    )
    figura.update_yaxes(rangemode="tozero")
    return _estilo_app(figura, alto=440)


# --- Casos de los posts ---------------------------------------------------------------------------

DESCRIPCION_CASO_B = (
    "Inversión de 20.000 € que hoy vale 30.000 € (ganancia de 10.000 €), "
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
    figura.write_image(carpeta / "grafico.png", width=INFORME_ANCHO, height=INFORME_ALTO, scale=INFORME_ESCALA)


if __name__ == "__main__":
    main()
