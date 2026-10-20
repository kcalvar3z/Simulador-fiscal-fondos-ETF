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
from simulador.calculo import TramoAplicado, desglose_cuota
from simulador.escenarios import (
    Escenario,
    Posicion,
    ResultadoEscenario,
    ResultadoPlan,
    comparar_escenarios,
    simular_plan,
)
from simulador.lotes import Lote, TipoProducto, Venta
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
INFORME_DEVUELTO = "#f8dedb"  # fondo del rayado de la retención que se devuelve (tinte de INFORME_RETENCION)
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
    retencion: Decimal  # retención que queda como impuesto del año
    en_renta: Decimal
    rotulo: str  # cifra encima de la barra
    devuelto: Decimal = Decimal("0")  # retención de más, que se devuelve en la Renta

    @property
    def total(self) -> Decimal:
        return self.retencion + self.en_renta + self.devuelto


TITULO_FONDO_FRENTE_A_ETF = "Con un fondo puedes aplazar el impuesto. Con un ETF, no."
_TITULO_EJE_CUOTA = f"Cuota de IRPF por la venta, {normativa.EJERCICIO} (€)"
_TITULO_EJE_RETENCION_Y_CUOTA = f"Retención y cuota de IRPF, {normativa.EJERCICIO} (€)"
_TIPO_RETENCION = tipo_impositivo(normativa.TIPO_RETENCION_REEMBOLSO_FONDO)


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


def texto_tramos(tramos: Sequence[TramoAplicado], retencion: Decimal, impuesto_latente: Decimal) -> str:
    """Panel del caso con una ganancia alta: la cuota por tramos frente a la retención fija."""
    cuota = sum((tramo.cuota for tramo in tramos), Decimal("0"))
    lineas = "".join(
        f"{euros(tramo.importe)} al {tipo_impositivo(tramo.tipo)}: {euros(tramo.cuota)}<br>" for tramo in tramos
    )
    return (
        "<b>¿Por qué no basta la retención?</b><br><br>"
        "La escala del ahorro es progresiva:<br>"
        f"{lineas}"
        f"<b>Total: {euros(cuota)}</b><br><br>"
        f"La gestora retiene un {_TIPO_RETENCION} fijo<br>"
        f"({euros(retencion)}). Los {euros(cuota - retencion)} restantes<br>"
        "se pagan en la Renta.<br><br>"
        "Con un traspaso, 0 € hoy: los<br>"
        f"{euros(impuesto_latente)} quedan aplazados."
    )


def texto_compensacion(ganancia: Decimal, perdida: Decimal, retencion: Decimal, devolucion: Decimal) -> str:
    """Panel del caso con dos fondos, uno con ganancia y otro con pérdida (`perdida` en positivo)."""
    return (
        "<b>¿Por qué pagan distinto?</b><br><br>"
        "Si los dos se reembolsan el mismo<br>"
        "año, la pérdida compensa la<br>"
        "ganancia (art. 49 LIRPF): tributan<br>"
        f"{euros(ganancia)} − {euros(perdida)} = {euros(ganancia - perdida)}.<br><br>"
        "La gestora retiene fondo a fondo:<br>"
        f"el {_TIPO_RETENCION} de la ganancia ({euros(retencion)}),<br>"
        f"sin restar la pérdida. Los {euros(devolucion)}<br>"
        "de más se devuelven en la Renta.<br><br>"
        "Si el fondo con pérdida se traspasa,<br>"
        "su pérdida también se aplaza."
    )


def figura_fondo_frente_a_etf(
    resultados: Sequence[ResultadoEscenario],
    descripcion_caso: str,
    titulo: str = TITULO_FONDO_FRENTE_A_ETF,
    panel: str | None = None,
) -> go.Figure:
    """Barras apiladas con lo que se paga este año en cada escenario.

    La barra del traspaso queda vacía (no se paga nada hoy) y un panel lateral explica, por
    defecto, el diferimiento con el impuesto latente. Pensado para una venta con ganancia.
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
            f"{euros(reembolso.retencion)} de retención<br>+ {euros(reembolso.regularizacion_renta)} a ingresar en la Renta",
            reembolso.retencion,
            reembolso.regularizacion_renta,
            f"{euros(reembolso.cuota)} este año",
        ),
        _Barra("Traspasar a otro fondo", "Sin impuesto ni retención hoy", cero, cero, "0 € este año"),
        _Barra("Vender el ETF", "Sin retención; no admite traspaso", cero, etf.cuota, f"{euros(etf.cuota)} este año"),
    ]
    panel = panel if panel is not None else texto_diferimiento(traspaso.impuesto_latente)
    return _figura_informe(barras, titulo, descripcion_caso, panel, _TITULO_EJE_CUOTA)


def figura_planes(
    planes: Sequence[tuple[str, ResultadoPlan]], descripcion_caso: str, titulo: str, panel: str
) -> go.Figure:
    """Como `figura_fondo_frente_a_etf`, pero con planes de varias inversiones.

    Si la retención supera la cuota, la parte que se devuelve en la Renta se dibuja rayada
    encima de la que queda como impuesto, para que la barra mida lo retenido.
    """
    cero = Decimal("0")
    barras = []
    for nombre, plan in planes:
        if plan.cuota < 0:
            raise ValueError("Este gráfico representa planes con cuota positiva o nula.")
        regularizacion = plan.regularizacion_renta
        rotulo = f"{euros(plan.cuota)} este año"
        if regularizacion < 0:
            detalle = f"{euros(plan.retencion)} de retención<br>− {euros(-regularizacion)} a devolver en la Renta"
            barras.append(_Barra(nombre, detalle, plan.cuota, cero, rotulo, devuelto=-regularizacion))
            continue
        if plan.retencion > 0:
            detalle = f"{euros(plan.retencion)} de retención<br>+ {euros(regularizacion)} a ingresar en la Renta"
        elif regularizacion > 0:
            detalle = "Sin retención: todo en la Renta"
        elif plan.impuesto_latente > 0:
            detalle = f"Sin impuesto hoy<br>{euros(plan.impuesto_latente)} aplazados"
        else:
            detalle = "Sin impuesto hoy"
        barras.append(_Barra(nombre, detalle, plan.retencion, regularizacion, rotulo))
    return _figura_informe(barras, titulo, descripcion_caso, panel, _TITULO_EJE_RETENCION_Y_CUOTA)


def _figura_informe(
    barras: Sequence[_Barra], titulo: str, descripcion_caso: str, panel: str, titulo_eje: str
) -> go.Figure:
    """Composición común de los gráficos de LinkedIn: barras, cabecera, pie y panel lateral."""
    # Escenario y, debajo, su detalle en gris, como etiqueta del eje.
    categorias = [
        f"<b>{barra.escenario}</b><br><span style='font-size:13px;color:{INFORME_TEXTO_SECUNDARIO}'>"
        f"{barra.detalle}</span>"
        for barra in barras
    ]

    figura = go.Figure()
    for nombre, campo, relleno in [
        ("Retención al vender (pago a cuenta)", "retencion", {"color": INFORME_RETENCION}),
        ("A ingresar en la declaración de la Renta", "en_renta", {"color": INFORME_RENTA}),
        # Mismo color que la retención, rayado: es retención, pero no se queda como impuesto.
        (
            "Retención que se devuelve en la Renta",
            "devuelto",
            {"color": INFORME_DEVUELTO, "pattern": {"shape": "/", "fgcolor": INFORME_RETENCION, "solidity": 0.4}},
        ),
    ]:
        valores = [getattr(barra, campo) for barra in barras]
        if not any(valores):
            continue  # sin serie vacía en la leyenda
        figura.add_bar(
            x=categorias,
            y=valores,
            name=nombre,
            width=0.42,
            marker={**relleno, "line": {"color": INFORME_FONDO, "width": 2}},
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
        (18, f"<b>{titulo}</b>", {"size": 22, "color": INFORME_TEXTO}),
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
        text=panel,
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
        # Márgenes fijos: sin automargin, Plotly no mueve la composición si una etiqueta es larga.
        xaxis={**eje, "tickangle": 0, "automargin": False, "tickfont": {"size": 14, "color": INFORME_TEXTO}},
        yaxis={
            **eje,
            "automargin": False,
            "title": {"text": titulo_eje, "font": {"size": 14}},
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
_INFORME_MARGEN_IZQUIERDO = 110
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


DESCRIPCION_CASO_I = (
    "Fondo A: 20.000 € que hoy valen 30.000 € (+10.000 €). Fondo B: 20.000 € que hoy valen 16.000 € "
    f"(−4.000 €). Sin otras rentas del ahorro. Ejercicio {normativa.EJERCICIO}."
)
TITULO_CASO_I = "Una pérdida solo rebaja el impuesto si también se materializa"


def caso_i() -> tuple[tuple[str, ResultadoPlan], ...]:
    """Caso I de examples.md: un fondo gana 10.000 € y otro pierde 4.000 €, en tres planes."""

    def fondo(nombre: str, precio_hoy: str) -> Posicion:
        lotes = (Lote(date(2023, 1, 15), Decimal("1000"), Decimal("20")),)
        return Posicion(nombre, TipoProducto.FONDO, lotes, Venta(date(2026, 10, 16), Decimal("1000"), Decimal(precio_hoy)))

    posiciones = [fondo("A", "30"), fondo("B", "16")]
    reembolsar, traspasar = Escenario.REEMBOLSO_FONDO, Escenario.TRASPASO_FONDO
    return (
        ("Reembolsar A y B", simular_plan(posiciones, {"A": reembolsar, "B": reembolsar})),
        ("Reembolsar A, traspasar B", simular_plan(posiciones, {"A": reembolsar, "B": traspasar})),
        ("Traspasar A y B", simular_plan(posiciones, {"A": traspasar, "B": traspasar})),
    )


def figura_caso_i() -> go.Figure:
    planes = caso_i()
    _, reembolsar_todo = planes[0]
    ganancias = [p.ganancia_patrimonial for p in reembolsar_todo.posiciones]
    panel = texto_compensacion(
        ganancia=sum((g for g in ganancias if g > 0), Decimal("0")),
        perdida=-sum((g for g in ganancias if g < 0), Decimal("0")),
        retencion=reembolsar_todo.retencion,
        devolucion=-reembolsar_todo.regularizacion_renta,
    )
    return figura_planes(planes, DESCRIPCION_CASO_I, TITULO_CASO_I, panel)


DESCRIPCION_CASO_A = (
    "Inversión de 40.000 € que hoy vale 100.000 € (ganancia de 60.000 €), "
    f"sin otras rentas del ahorro. Ejercicio {normativa.EJERCICIO}."
)
TITULO_CASO_A = f"Con ganancias altas, la retención del {_TIPO_RETENCION} se queda corta"


def caso_a() -> tuple[ResultadoEscenario, ...]:
    """Caso A de examples.md (base del ahorro de 60.000 €) como venta: 40.000 € que hoy valen 100.000 €."""
    lotes = [Lote(date(2023, 1, 15), Decimal("1000"), Decimal("40"))]
    venta = Venta(date(2026, 10, 16), Decimal("1000"), Decimal("100"))
    return comparar_escenarios(lotes, venta)


def figura_caso_a() -> go.Figure:
    resultados = caso_a()
    por_escenario = {resultado.escenario: resultado for resultado in resultados}
    reembolso = por_escenario[Escenario.REEMBOLSO_FONDO]
    # Sin otras rentas del ahorro, la base antes de la venta es 0.
    tramos = desglose_cuota(Decimal("0"), reembolso.compensacion.base_ahorro)
    panel = texto_tramos(tramos, reembolso.retencion, por_escenario[Escenario.TRASPASO_FONDO].impuesto_latente)
    return figura_fondo_frente_a_etf(resultados, DESCRIPCION_CASO_A, TITULO_CASO_A, panel)


def main() -> None:
    carpeta = Path(__file__).resolve().parent.parent / "contenido" / "2026-10-17-fondo-vs-etf"
    carpeta.mkdir(parents=True, exist_ok=True)
    figuras = {
        "grafico-1-fondo-etf.png": figura_fondo_frente_a_etf(caso_b(), DESCRIPCION_CASO_B),
        "grafico-2-compensacion.png": figura_caso_i(),
        "grafico-3-tramos.png": figura_caso_a(),
    }
    for fichero, figura in figuras.items():
        figura.write_image(carpeta / fichero, width=INFORME_ANCHO, height=INFORME_ALTO, scale=INFORME_ESCALA)


if __name__ == "__main__":
    main()
