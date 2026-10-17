"""Interfaz web del simulador (Streamlit).

Solo recoge datos, llama a las funciones de `simulador/` y presenta los resultados:
aquí no hay cálculo fiscal. Ejecutar con: streamlit run app.py
"""

from dataclasses import dataclass
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
    Posicion,
    ResultadoPlan,
    operaciones_reembolsar_todo,
    operaciones_traspasar_fondos,
    simular_plan,
)
from simulador.lotes import Lote, TipoProducto, Venta

AVISO_LEGAL = "Cálculo orientativo con fines divulgativos. No constituye asesoramiento fiscal ni financiero."
PRIVACIDAD = "Tus datos no se guardan: solo existen mientras tienes la página abierta."

TIPO_POR_ETIQUETA = {"Fondo de inversión": TipoProducto.FONDO, "ETF": TipoProducto.ETF}
VENDER = "Reembolsar o vender"
TRASPASAR = "Traspasar"
NO_DISPONIBLE = "No disponible"

SUPUESTOS = f"""
- IRPF de residentes en territorio común, ejercicio {normativa.EJERCICIO}. No cubre País Vasco ni Navarra,
  no residentes, personas jurídicas ni el Impuesto sobre el Patrimonio.
- Contribuyente con un salario estándar: su base general absorbe el mínimo personal y familiar, que por
  eso no reduce la cuota del ahorro (art. 66.1.2.º LIRPF). Con rentas del trabajo muy bajas, la cuota real
  sería menor.
- Cada producto (un fondo, o una clase concreta de un fondo, o un ETF) tiene su propia cola FIFO, y todas
  sus participaciones están en una sola entidad (art. 97.2 RIRPF).
- La cuota es la atribuible a las operaciones: la de tu base del ahorro con ellas menos la que tendrías sin
  ellas. Con varios productos se muestra en total, porque con una escala progresiva no hay una forma única
  de repartirla entre ellos.
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


def fecha_venta_por_defecto() -> date:
    hoy = date.today()
    return hoy if hoy.year == normativa.EJERCICIO else date(normativa.EJERCICIO, 12, 31)


def compras_ejemplo() -> pd.DataFrame:
    """Caso B: 20.000 € invertidos (1.000 participaciones a 20 €) que hoy valen 30.000 €."""
    return pd.DataFrame(
        {
            "producto": ["Fondo A"],
            "fecha": [date(2023, 1, 15)],
            "participaciones": [1000.0],
            "precio_unitario": [20.0],
            "comision": [0.0],
        }
    )


def ventas_ejemplo() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "producto": ["Fondo A"],
            "tipo": ["Fondo de inversión"],
            "operacion": [VENDER],
            "fecha": [fecha_venta_por_defecto()],
            "participaciones": [None],
            "precio_unitario": [30.0],
            "comision": [0.0],
        }
    ).astype({"participaciones": "float64"})


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


def _texto(valor) -> str:
    return str(valor).strip() if pd.notna(valor) else ""


def leer_plan(compras: pd.DataFrame, ventas: pd.DataFrame) -> tuple[list[Posicion], dict[str, Escenario]]:
    """Convierte las dos tablas en posiciones y en la operación elegida para cada una.

    Ignora las filas a medio rellenar. Las compras de productos que no se venden no intervienen.
    """
    lotes: dict[str, list[Lote]] = {}
    for fila in compras.dropna(subset=["fecha", "participaciones", "precio_unitario"]).itertuples():
        nombre = _texto(fila.producto)
        if not nombre:
            raise ValueError("Hay una compra sin producto: indica a qué fondo o ETF pertenece.")
        lotes.setdefault(nombre, []).append(
            Lote(
                fecha=pd.Timestamp(fila.fecha).date(),
                participaciones=a_decimal(fila.participaciones),
                precio_unitario=a_decimal(fila.precio_unitario),
                comision=a_decimal(fila.comision) if pd.notna(fila.comision) else Decimal("0"),
            )
        )

    posiciones: list[Posicion] = []
    operaciones: dict[str, Escenario] = {}
    for fila in ventas.dropna(subset=["tipo", "operacion", "fecha", "precio_unitario"]).itertuples():
        nombre = _texto(fila.producto)
        if nombre not in lotes:
            raise ValueError(f"«{nombre}» no tiene compras: el nombre debe coincidir con el de la tabla de compras.")
        tipo = TIPO_POR_ETIQUETA[fila.tipo]
        vendidas = (
            sum((lote.participaciones for lote in lotes[nombre]), Decimal("0"))
            if pd.isna(fila.participaciones)
            else a_decimal(fila.participaciones)
        )
        venta = Venta(
            fecha=pd.Timestamp(fila.fecha).date(),
            participaciones=vendidas,
            precio_unitario=a_decimal(fila.precio_unitario),
            comision=a_decimal(fila.comision) if pd.notna(fila.comision) else Decimal("0"),
        )
        posiciones.append(Posicion(nombre, tipo, tuple(lotes[nombre]), venta))
        if fila.operacion == TRASPASAR:
            operaciones[nombre] = Escenario.TRASPASO_FONDO  # con un ETF, simular_plan explica que no se puede
        else:
            operaciones[nombre] = Escenario.REEMBOLSO_FONDO if tipo is TipoProducto.FONDO else Escenario.VENTA_ETF

    if not posiciones:
        raise ValueError("Indica en la tabla de ventas al menos un producto con su precio de venta.")
    return posiciones, operaciones


def leer_pendientes(tabla: pd.DataFrame, columna: str) -> tuple[SaldoPendiente, ...]:
    return tuple(
        SaldoPendiente(int(fila.ejercicio), a_decimal(getattr(fila, columna)))
        for fila in tabla.itertuples()
        if pd.notna(getattr(fila, columna)) and getattr(fila, columna) > 0
    )


# --- Planes que se muestran -----------------------------------------------------------------------


@dataclass(frozen=True)
class PlanMostrado:
    titulo: str
    clave: str  # "seleccion", "reembolsar" o "traspasar"
    resultado: ResultadoPlan | None  # None: no disponible (traspasar cuando solo hay ETF)


def calcular_planes(
    posiciones: list[Posicion], operaciones: dict[str, Escenario], otras_rentas: OtrasRentasAhorro
) -> list[PlanMostrado]:
    """La selección del usuario y los dos planes de referencia, sin repetir columnas iguales."""
    seleccion = simular_plan(posiciones, operaciones, otras_rentas)  # valida la selección
    reembolsar = operaciones_reembolsar_todo(posiciones)
    traspasar = operaciones_traspasar_fondos(posiciones)
    hay_fondos = any(p.tipo is TipoProducto.FONDO for p in posiciones)

    if len(posiciones) == 1:
        titulo_reembolsar = "Reembolso del fondo" if hay_fondos else "Venta del ETF"
        titulo_traspasar = "Traspaso a otro fondo"
    else:
        titulo_reembolsar = "Reembolsar o vender todo"
        titulo_traspasar = "Traspasar los fondos"

    planes = []
    if operaciones not in (reembolsar, traspasar):
        planes.append(PlanMostrado("Tu selección", "seleccion", seleccion))
    planes.append(PlanMostrado(titulo_reembolsar, "reembolsar", simular_plan(posiciones, reembolsar, otras_rentas)))
    planes.append(
        PlanMostrado(
            titulo_traspasar,
            "traspasar",
            simular_plan(posiciones, traspasar, otras_rentas) if hay_fondos else None,
        )
    )
    return planes


# --- Resultados -----------------------------------------------------------------------------------


def tabla_comparativa(planes: list[PlanMostrado]) -> pd.DataFrame:
    conceptos = [
        f"Cuota de IRPF en {normativa.EJERCICIO}",
        "Retención al vender (pago a cuenta)",
        "Efecto en la Renta (cuota − retención)",
        "Impuesto latente (diferido)",
    ]
    columnas = {}
    for plan in planes:
        r = plan.resultado
        columnas[plan.titulo] = (
            [NO_DISPONIBLE] * len(conceptos)
            if r is None
            else [
                formato_euros(r.cuota),
                formato_euros(r.retencion),
                formato_euros(r.regularizacion_renta),
                formato_euros(r.impuesto_latente),
            ]
        )
    return pd.DataFrame(columnas, index=conceptos)


def tabla_por_producto(posiciones: list[Posicion], planes: list[PlanMostrado]) -> pd.DataFrame:
    """Ganancia y retención de cada producto si se reembolsa o se vende: son exactas por producto."""
    reembolsar = next(plan.resultado for plan in planes if plan.clave == "reembolsar")
    etiqueta_tipo = {tipo: etiqueta for etiqueta, tipo in TIPO_POR_ETIQUETA.items()}
    return pd.DataFrame(
        {
            "Tipo": [etiqueta_tipo[p.tipo] for p in posiciones],
            "Ganancia o pérdida": [formato_euros(r.ganancia_patrimonial) for r in reembolsar.posiciones],
            "Retención si reembolsas o vendes": [formato_euros(r.retencion) for r in reembolsar.posiciones],
        },
        index=[p.nombre for p in posiciones],
    )


def mensaje_clave(posiciones: list[Posicion], planes: list[PlanMostrado]) -> str:
    por_clave = {plan.clave: plan for plan in planes}
    reembolsar = por_clave["reembolsar"]
    r = reembolsar.resultado
    hay_fondos = any(p.tipo is TipoProducto.FONDO for p in posiciones)
    hay_etf = any(p.tipo is TipoProducto.ETF for p in posiciones)

    if not hay_fondos:
        return (
            f"- **{reembolsar.titulo}:** la cuota ({formato_euros(r.cuota)}) se paga en la Renta del ejercicio. "
            "Los ETF no tienen retención al vender, así que no adelantas nada: lo pagas entero en la declaración.\n"
            "- **Un ETF no admite traspaso:** vender siempre tributa en el ejercicio (art. 94 LIRPF)."
        )

    lineas = [
        f"- **{reembolsar.titulo}:** la cuota es {formato_euros(r.cuota)}. Al reembolsar se retienen "
        f"{formato_euros(r.retencion)}, que se descuentan en la Renta"
        + (" (los ETF no tienen retención)." if hay_etf else ".")
    ]
    if len(posiciones) > 1 and r.retencion > r.cuota and r.retencion > 0:
        lineas.append(
            "- **Las retenciones superan la cuota** porque se calculan fondo a fondo y no descuentan las "
            "pérdidas de otros productos: la diferencia se devuelve en la Renta."
        )
    t = por_clave["traspasar"].resultado
    linea_traspaso = (
        f"- **{por_clave['traspasar'].titulo}:** los fondos no tributan ahora; la ganancia se difiere. "
        f"El impuesto latente ({formato_euros(t.impuesto_latente)}, calculado como si reembolsaras hoy) aflora "
        "cuando reembolses, porque las nuevas participaciones conservan el valor y la fecha de compra originales."
    )
    if hay_etf:
        linea_traspaso += (
            f" Los ETF no admiten traspaso: se venden igualmente y la cuota de hoy es {formato_euros(t.cuota)}."
        )
    lineas.append(linea_traspaso)
    if r.retencion != 0:
        lineas.append("- Una retención no es un impuesto extra: es un pago a cuenta que se descuenta en la Renta.")
    return "\n".join(lineas)


def textos_avisos(planes: list[PlanMostrado]) -> list[str]:
    con_perdida: list[str] = []
    etf_antiguos: list[str] = []
    textos: list[str] = []
    for plan in planes:
        if plan.resultado is None:
            continue
        for posicion in plan.resultado.posiciones:
            if Aviso.REGLA_RECOMPRA in posicion.avisos and posicion.nombre not in con_perdida:
                con_perdida.append(posicion.nombre)
            if Aviso.REGIMEN_TRANSITORIO_ETF in posicion.avisos and posicion.nombre not in etf_antiguos:
                etf_antiguos.append(posicion.nombre)
        if Aviso.SALDOS_CADUCADOS in plan.resultado.avisos:
            c = plan.resultado.compensacion
            caducado = c.perdidas_patrimoniales_caducadas + c.rendimientos_negativos_caducados
            ejercicio = normativa.EJERCICIO - normativa.EJERCICIOS_ARRASTRE_SALDOS_NEGATIVOS
            textos.append(
                f"**Saldos que caducan.** Con «{plan.titulo}» quedan sin compensar {formato_euros(caducado)} "
                f"de saldos negativos de {ejercicio}, que ya no podrás usar (art. 49 LIRPF)."
            )
    if con_perdida:
        textos.insert(
            0,
            f"**Venta con pérdida ({', '.join(con_perdida)}).** Si recompras valores homogéneos en los "
            f"{normativa.PLAZO_RECOMPRA_MESES_MERCADO_REGULADO} meses anteriores o posteriores "
            f"({normativa.PLAZO_RECOMPRA_MESES_OTROS} meses si no cotizan en un mercado regulado), la pérdida "
            "no se computa ahora: se integra cuando vendas los valores recomprados (art. 33.5 LIRPF). "
            "El plazo aplicable a fondos no cotizados está pendiente de verificar.",
        )
    if etf_antiguos:
        textos.insert(
            1 if con_perdida else 0,
            f"**Lotes anteriores a 2022 ({', '.join(etf_antiguos)}).** Si el ETF es extranjero y no cotiza en "
            "bolsa española, esas participaciones podrían traspasarse a un fondo no cotizado por el régimen "
            "transitorio (DT 36.ª LIRPF). El simulador no lo calcula.",
        )
    return textos


def tabla_saldos_pendientes(planes: list[PlanMostrado]) -> pd.DataFrame | None:
    columnas = {}
    for plan in planes:
        if plan.resultado is None:
            continue
        c = plan.resultado.compensacion
        columnas[plan.titulo] = [
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


def mostrar_resultados(posiciones: list[Posicion], planes: list[PlanMostrado]) -> None:
    st.subheader("Resultado")
    st.dataframe(tabla_comparativa(planes), width="stretch")
    st.markdown(mensaje_clave(posiciones, planes))

    if len(posiciones) > 1:
        st.markdown("**Por producto**")
        st.dataframe(tabla_por_producto(posiciones, planes), width="stretch")

    saldos = tabla_saldos_pendientes(planes)
    if saldos is not None:
        st.markdown("**Saldos negativos tras la operación**")
        st.dataframe(saldos, width="stretch")

    for texto in textos_avisos(planes):
        st.warning(texto)

    with st.expander("Cómo leer la tabla"):
        st.markdown(
            "- **Cuota**: lo que las operaciones añaden a tu IRPF del año (negativa si una pérdida lo reduce).\n"
            "- **Retención**: lo que la gestora ingresa a Hacienda al reembolsar. Es un adelanto, no un "
            "impuesto adicional.\n"
            "- **Efecto en la Renta**: cuota menos retención. Positivo: lo que te queda por pagar en la "
            "declaración. Negativo: lo que reduce tu resultado.\n"
            "- **Impuesto latente**: la cuota que el traspaso aplaza, calculada como si reembolsaras hoy. "
            "La real dependerá del valor y de tus rentas el año en que reembolses.\n"
            "- **Tu selección** aparece cuando combinas operaciones distintas (por ejemplo, reembolsar un fondo "
            "y traspasar otro)."
        )
    with st.expander("Supuestos y alcance"):
        st.markdown(SUPUESTOS)


# --- Página ---------------------------------------------------------------------------------------


def main() -> None:
    st.set_page_config(page_title="Simulador fiscal: fondo vs. ETF", layout="wide")
    st.title("Vender un fondo o un ETF: qué cuesta en el IRPF")
    st.caption(f"IRPF, territorio común, ejercicio {normativa.EJERCICIO}. {PRIVACIDAD}")
    st.info(AVISO_LEGAL)

    entrada, salida = st.columns([5, 4], gap="large")

    with entrada:
        st.subheader("1. Tus compras")
        st.caption(
            "Una fila por compra. Se venden primero las más antiguas de cada producto. Cada clase de un fondo "
            "es un producto distinto."
        )
        tabla_compras = st.data_editor(
            compras_ejemplo(),
            key="compras",
            num_rows="dynamic",
            hide_index=True,
            column_config={
                "producto": st.column_config.TextColumn("Producto", required=True),
                "fecha": st.column_config.DateColumn("Fecha", format="DD/MM/YYYY", required=True),
                "participaciones": st.column_config.NumberColumn("Participaciones", min_value=0, format="%.4f"),
                "precio_unitario": st.column_config.NumberColumn("Precio (€)", min_value=0, format="%.4f"),
                "comision": st.column_config.NumberColumn("Comisión (€)", min_value=0, format="%.2f", default=0.0),
            },
        )

        st.subheader("2. Qué haces con cada producto")
        st.caption(
            "Una fila por producto que vendes o traspasas, con el mismo nombre que en las compras. "
            "Deja «Participaciones» vacío para venderlas todas."
        )
        tabla_ventas = st.data_editor(
            ventas_ejemplo(),
            key="ventas",
            num_rows="dynamic",
            hide_index=True,
            column_config={
                "producto": st.column_config.TextColumn("Producto", required=True),
                "tipo": st.column_config.SelectboxColumn(
                    "Tipo", options=list(TIPO_POR_ETIQUETA), required=True, default="Fondo de inversión"
                ),
                "operacion": st.column_config.SelectboxColumn(
                    "Operación", options=[VENDER, TRASPASAR], required=True, default=VENDER
                ),
                "fecha": st.column_config.DateColumn(
                    "Fecha",
                    format="DD/MM/YYYY",
                    min_value=date(normativa.EJERCICIO, 1, 1),
                    max_value=date(normativa.EJERCICIO, 12, 31),
                    default=fecha_venta_por_defecto(),
                    required=True,
                ),
                "participaciones": st.column_config.NumberColumn("Participaciones", min_value=0, format="%.4f"),
                "precio_unitario": st.column_config.NumberColumn("Precio de venta (€)", min_value=0, format="%.4f"),
                "comision": st.column_config.NumberColumn("Comisión (€)", min_value=0, format="%.2f", default=0.0),
            },
        )

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
            posiciones, operaciones = leer_plan(tabla_compras, tabla_ventas)
            otras_rentas = OtrasRentasAhorro(
                saldo_rendimientos=a_decimal(rendimientos),
                saldo_ganancias_perdidas=a_decimal(otras_ganancias),
                rendimientos_negativos_anteriores=leer_pendientes(tabla_pendientes, "rendimientos"),
                perdidas_patrimoniales_anteriores=leer_pendientes(tabla_pendientes, "perdidas"),
            )
            planes = calcular_planes(posiciones, operaciones, otras_rentas)
        except ValueError as error:
            st.error(str(error))
        else:
            mostrar_resultados(posiciones, planes)

    st.divider()
    st.caption(AVISO_LEGAL)


if __name__ == "__main__":
    main()
