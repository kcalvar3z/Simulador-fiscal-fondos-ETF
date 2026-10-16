"""Interfaz web del simulador (Streamlit).

Solo recoge datos, llama a las funciones de `simulador/` y presenta los resultados:
aquí no hay cálculo fiscal. Ejecutar con: streamlit run app.py
"""

from datetime import date
from decimal import Decimal

import pandas as pd
import streamlit as st

from simulador import normativa
from simulador.calculo import redondear_centimos
from simulador.compensacion import SaldoPendiente
from simulador.escenarios import (
    Aviso,
    Escenario,
    OtrasRentasAhorro,
    ResultadoEscenario,
    comparar_escenarios,
    escenarios_disponibles,
)
from simulador.lotes import Lote, TipoProducto, Venta

AVISO_LEGAL = "Cálculo orientativo con fines divulgativos. No constituye asesoramiento fiscal ni financiero."

NOMBRE_PRODUCTO = {TipoProducto.FONDO: "Fondo de inversión", TipoProducto.ETF: "ETF"}
NOMBRE_ESCENARIO = {
    Escenario.REEMBOLSO_FONDO: "Reembolso del fondo",
    Escenario.TRASPASO_FONDO: "Traspaso a otro fondo",
    Escenario.VENTA_ETF: "Venta del ETF",
}
NO_DISPONIBLE = "No disponible"

SUPUESTOS = f"""
- IRPF de residentes en territorio común, ejercicio {normativa.EJERCICIO}. No cubre País Vasco ni Navarra,
  no residentes, personas jurídicas ni el Impuesto sobre el Patrimonio.
- Contribuyente con un salario estándar: su base general absorbe el mínimo personal y familiar, que por
  eso no reduce la cuota del ahorro (art. 66.1.2.º LIRPF). Con rentas del trabajo muy bajas, la cuota real
  sería menor.
- Todas las participaciones del producto están en una sola entidad (art. 97.2 RIRPF).
- La cuota mostrada es la atribuible a la operación: la de tu base del ahorro con la operación menos la
  que tendrías sin ella.
"""


# --- Conversión y formato -------------------------------------------------------------------------


def a_decimal(valor: float) -> Decimal:
    """Convierte la entrada de Streamlit (float) a Decimal pasando por texto.

    Decimal(0.1) arrastraría el error binario del float; Decimal(str(0.1)) es exactamente 0.1.
    """
    return Decimal(str(valor))


def formato_euros(importe: Decimal) -> str:
    """Formato español con céntimos: Decimal("1980") → "1.980,00 €"."""
    redondeado = redondear_centimos(importe)
    if redondeado == 0:
        redondeado = abs(redondeado)  # evita "-0,00 €"
    texto = f"{redondeado:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"{texto} €"


# --- Entradas -------------------------------------------------------------------------------------


def lotes_ejemplo() -> pd.DataFrame:
    """Caso B: 20.000 € invertidos (1.000 participaciones a 20 €) que hoy valen 30.000 €."""
    return pd.DataFrame(
        {
            "fecha": [date(2023, 1, 15)],
            "participaciones": [1000.0],
            "precio_unitario": [20.0],
            "comision": [0.0],
        }
    )


def pendientes_vacios() -> pd.DataFrame:
    primero = normativa.EJERCICIO - normativa.EJERCICIOS_ARRASTRE_SALDOS_NEGATIVOS
    ejercicios = list(range(primero, normativa.EJERCICIO))
    return pd.DataFrame(
        {
            "ejercicio": ejercicios,
            "perdidas": [0.0] * len(ejercicios),
            "rendimientos": [0.0] * len(ejercicios),
        }
    )


def leer_lotes(tabla: pd.DataFrame) -> list[Lote]:
    """Convierte las filas completas de la tabla en lotes; ignora las filas a medio rellenar."""
    completas = tabla.dropna(subset=["fecha", "participaciones", "precio_unitario"])
    return [
        Lote(
            fecha=pd.Timestamp(fila.fecha).date(),
            participaciones=a_decimal(fila.participaciones),
            precio_unitario=a_decimal(fila.precio_unitario),
            comision=a_decimal(fila.comision) if pd.notna(fila.comision) else Decimal("0"),
        )
        for fila in completas.itertuples()
    ]


def leer_pendientes(tabla: pd.DataFrame, columna: str) -> tuple[SaldoPendiente, ...]:
    return tuple(
        SaldoPendiente(int(fila.ejercicio), a_decimal(getattr(fila, columna)))
        for fila in tabla.itertuples()
        if pd.notna(getattr(fila, columna)) and getattr(fila, columna) > 0
    )


def fecha_venta_por_defecto() -> date:
    hoy = date.today()
    return hoy if hoy.year == normativa.EJERCICIO else date(normativa.EJERCICIO, 12, 31)


# --- Resultados -----------------------------------------------------------------------------------


def titulo_columna(escenario: Escenario, tipo: TipoProducto) -> str:
    nombre = NOMBRE_ESCENARIO[escenario]
    if escenario in escenarios_disponibles(tipo):
        return f"{nombre} (tu caso)"
    if tipo is TipoProducto.ETF and escenario is Escenario.TRASPASO_FONDO:
        return nombre
    otro = "un ETF" if tipo is TipoProducto.FONDO else "un fondo"
    return f"{nombre} (si fuera {otro})"


def tabla_comparativa(tipo: TipoProducto, resultados: tuple[ResultadoEscenario, ...]) -> pd.DataFrame:
    conceptos = [
        f"Cuota de IRPF en {normativa.EJERCICIO}",
        "Retención al vender (pago a cuenta)",
        "Efecto en la Renta (cuota − retención)",
        "Impuesto latente (diferido)",
    ]
    columnas = {}
    for resultado in resultados:
        if tipo is TipoProducto.ETF and resultado.escenario is Escenario.TRASPASO_FONDO:
            valores = [NO_DISPONIBLE] * len(conceptos)
        else:
            valores = [
                formato_euros(resultado.cuota),
                formato_euros(resultado.retencion),
                formato_euros(resultado.regularizacion_renta),
                formato_euros(resultado.impuesto_latente),
            ]
        columnas[titulo_columna(resultado.escenario, tipo)] = valores
    return pd.DataFrame(columnas, index=conceptos)


def mensaje_clave(tipo: TipoProducto, resultados: dict[Escenario, ResultadoEscenario]) -> str:
    reembolso = resultados[Escenario.REEMBOLSO_FONDO]
    traspaso = resultados[Escenario.TRASPASO_FONDO]
    etf = resultados[Escenario.VENTA_ETF]
    lineas = [
        f"- **Reembolso del fondo y venta del ETF pagan la misma cuota ({formato_euros(reembolso.cuota)}).** "
        f"Solo cambia cuándo: el fondo retiene {formato_euros(reembolso.retencion)} al reembolsar y el resto "
        f"se ajusta en la Renta; el ETF no retiene y lo pagas entero en la declaración.",
    ]
    if tipo is TipoProducto.FONDO:
        lineas.append(
            f"- **Con el traspaso no tributas ahora:** la ganancia se difiere. El impuesto latente "
            f"({formato_euros(traspaso.impuesto_latente)}, calculado como si reembolsaras hoy) aflora cuando "
            f"reembolses, porque las nuevas participaciones conservan el valor y la fecha de compra originales."
        )
    else:
        lineas.append(
            "- **Un ETF no admite traspaso:** vender siempre tributa en el ejercicio (art. 94 LIRPF). "
            f"Si fuera un fondo, podrías diferir {formato_euros(traspaso.impuesto_latente)} con un traspaso."
        )
    if etf.cuota != 0:
        lineas.append(
            "- Una retención no es un impuesto extra: es un pago a cuenta que se descuenta en la Renta."
        )
    return "\n".join(lineas)


def texto_aviso(aviso: Aviso, resultado: ResultadoEscenario) -> str:
    if aviso is Aviso.REGLA_RECOMPRA:
        return (
            "**Venta con pérdida.** Si recompras valores homogéneos en los "
            f"{normativa.PLAZO_RECOMPRA_MESES_MERCADO_REGULADO} meses anteriores o posteriores "
            f"({normativa.PLAZO_RECOMPRA_MESES_OTROS} meses si no cotizan en un mercado regulado), "
            "la pérdida no se computa ahora: se integra cuando vendas los valores recomprados "
            "(art. 33.5 LIRPF). El plazo aplicable a fondos no cotizados está pendiente de verificar."
        )
    if aviso is Aviso.REGIMEN_TRANSITORIO_ETF:
        return (
            "**Lotes anteriores a 2022.** Si el ETF es extranjero y no cotiza en bolsa española, esas "
            "participaciones podrían traspasarse a un fondo no cotizado por el régimen transitorio "
            "(DT 36.ª LIRPF). El simulador no lo calcula."
        )
    caducado = (
        resultado.compensacion.perdidas_patrimoniales_caducadas
        + resultado.compensacion.rendimientos_negativos_caducados
    )
    ejercicio = normativa.EJERCICIO - normativa.EJERCICIOS_ARRASTRE_SALDOS_NEGATIVOS
    return (
        f"**Saldos que caducan.** Con «{NOMBRE_ESCENARIO[resultado.escenario]}» quedan sin compensar "
        f"{formato_euros(caducado)} de saldos negativos de {ejercicio}, que ya no podrás usar "
        "(art. 49 LIRPF)."
    )


def tabla_saldos_pendientes(tipo: TipoProducto, resultados: tuple[ResultadoEscenario, ...]) -> pd.DataFrame | None:
    columnas = {}
    for resultado in resultados:
        if tipo is TipoProducto.ETF and resultado.escenario is Escenario.TRASPASO_FONDO:
            continue
        c = resultado.compensacion
        columnas[titulo_columna(resultado.escenario, tipo)] = [
            sum((s.importe for s in c.perdidas_patrimoniales_pendientes), Decimal("0")),
            sum((s.importe for s in c.rendimientos_negativos_pendientes), Decimal("0")),
            c.perdidas_patrimoniales_caducadas + c.rendimientos_negativos_caducados,
        ]
    if all(valor == 0 for valores in columnas.values() for valor in valores):
        return None
    conceptos = [
        "Pérdidas patrimoniales para años siguientes",
        "Rendimientos negativos para años siguientes",
        "Caducan este año",
    ]
    return pd.DataFrame(
        {titulo: [formato_euros(v) for v in valores] for titulo, valores in columnas.items()},
        index=conceptos,
    )


def mostrar_resultados(tipo: TipoProducto, resultados: tuple[ResultadoEscenario, ...]) -> None:
    por_escenario = {resultado.escenario: resultado for resultado in resultados}
    ganancia = resultados[0].ganancia_patrimonial

    st.subheader("Resultado")
    st.metric("Ganancia patrimonial" if ganancia >= 0 else "Pérdida patrimonial", formato_euros(abs(ganancia)))
    st.dataframe(tabla_comparativa(tipo, resultados), width="stretch")
    st.markdown(mensaje_clave(tipo, por_escenario))

    saldos = tabla_saldos_pendientes(tipo, resultados)
    if saldos is not None:
        st.markdown("**Saldos negativos tras la operación**")
        st.dataframe(saldos, width="stretch")

    avisos_mostrados = set()
    for escenario in escenarios_disponibles(tipo):
        resultado = por_escenario[escenario]
        for aviso in resultado.avisos:
            texto = texto_aviso(aviso, resultado)
            if texto not in avisos_mostrados:
                avisos_mostrados.add(texto)
                st.warning(texto)

    with st.expander("Cómo leer la tabla"):
        st.markdown(
            "- **Cuota**: lo que la operación añade a tu IRPF del año (negativa si una pérdida lo reduce).\n"
            "- **Retención**: lo que la gestora ingresa a Hacienda al reembolsar. Es un adelanto, no un "
            "impuesto adicional.\n"
            "- **Efecto en la Renta**: cuota menos retención. Positivo: lo que te queda por pagar en la "
            "declaración por esta operación. Negativo: lo que reduce tu resultado.\n"
            "- **Impuesto latente**: la cuota que el traspaso aplaza, calculada como si reembolsaras hoy. "
            "La real dependerá del valor y de tus rentas el año en que reembolses."
        )
    with st.expander("Supuestos y alcance"):
        st.markdown(SUPUESTOS)


# --- Página ---------------------------------------------------------------------------------------


def main() -> None:
    st.set_page_config(page_title="Simulador fiscal: fondo vs. ETF", layout="wide")
    st.title("Vender un fondo o un ETF: qué cuesta en el IRPF")
    st.caption(f"IRPF, territorio común, ejercicio {normativa.EJERCICIO}.")
    st.info(AVISO_LEGAL)

    entrada, salida = st.columns([2, 3], gap="large")

    with entrada:
        st.subheader("1. Tu inversión")
        tipo = st.radio(
            "Producto", list(TipoProducto), format_func=NOMBRE_PRODUCTO.get, horizontal=True, key="producto"
        )
        st.markdown("**Compras** (una fila por compra; se venden primero las más antiguas)")
        tabla_lotes = st.data_editor(
            lotes_ejemplo(),
            key="lotes",
            num_rows="dynamic",
            hide_index=True,
            column_config={
                "fecha": st.column_config.DateColumn("Fecha", format="DD/MM/YYYY", required=True),
                "participaciones": st.column_config.NumberColumn("Participaciones", min_value=0, format="%.4f"),
                "precio_unitario": st.column_config.NumberColumn("Precio (€)", min_value=0, format="%.4f"),
                "comision": st.column_config.NumberColumn("Comisión (€)", min_value=0, format="%.2f"),
            },
        )

        st.subheader("2. La venta")
        fecha_venta = st.date_input(
            "Fecha",
            value=fecha_venta_por_defecto(),
            min_value=date(normativa.EJERCICIO, 1, 1),
            max_value=date(normativa.EJERCICIO, 12, 31),
            format="DD/MM/YYYY",
        )
        vender_todo = st.checkbox("Vender todas las participaciones", value=True)
        participaciones = st.number_input(
            "Participaciones a vender", min_value=0.0, value=0.0, step=1.0, format="%.4f", disabled=vender_todo
        )
        col_precio, col_comision = st.columns(2)
        precio_venta = col_precio.number_input("Precio de venta (€)", min_value=0.0, value=30.0, format="%.4f")
        comision_venta = col_comision.number_input("Comisión de venta (€)", min_value=0.0, value=0.0, format="%.2f")

        st.subheader(f"3. Tus otras rentas del ahorro en {normativa.EJERCICIO}")
        rendimientos = st.number_input(
            "Saldo de rendimientos del capital mobiliario (intereses, dividendos…), €",
            value=0.0,
            step=100.0,
            format="%.2f",
        )
        otras_ganancias = st.number_input(
            "Saldo de otras ganancias y pérdidas patrimoniales, €", value=0.0, step=100.0, format="%.2f"
        )
        with st.expander("Saldos negativos pendientes de años anteriores"):
            tabla_pendientes = st.data_editor(
                pendientes_vacios(),
                key="pendientes",
                num_rows="fixed",
                hide_index=True,
                disabled=["ejercicio"],
                column_config={
                    "ejercicio": st.column_config.NumberColumn("Ejercicio", format="%d"),
                    "perdidas": st.column_config.NumberColumn("Pérdidas patrimoniales (€)", min_value=0, format="%.2f"),
                    "rendimientos": st.column_config.NumberColumn(
                        "Rendimientos negativos (€)", min_value=0, format="%.2f"
                    ),
                },
            )

    with salida:
        try:
            lotes = leer_lotes(tabla_lotes)
            if not lotes:
                raise ValueError("Añade al menos una compra para ver el resultado.")
            vendidas = (
                sum((lote.participaciones for lote in lotes), Decimal("0"))
                if vender_todo
                else a_decimal(participaciones)
            )
            venta = Venta(fecha_venta, vendidas, a_decimal(precio_venta), a_decimal(comision_venta))
            otras_rentas = OtrasRentasAhorro(
                saldo_rendimientos=a_decimal(rendimientos),
                saldo_ganancias_perdidas=a_decimal(otras_ganancias),
                rendimientos_negativos_anteriores=leer_pendientes(tabla_pendientes, "rendimientos"),
                perdidas_patrimoniales_anteriores=leer_pendientes(tabla_pendientes, "perdidas"),
            )
            resultados = comparar_escenarios(lotes, venta, otras_rentas)
        except ValueError as error:
            st.error(str(error))
        else:
            mostrar_resultados(tipo, resultados)

    st.divider()
    st.caption(AVISO_LEGAL)


if __name__ == "__main__":
    main()
