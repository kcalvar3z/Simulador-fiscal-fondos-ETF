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
from simulador.graficos import figura_cascada, figura_rentabilidad, pasos_cascada, porcentaje
from simulador.lotes import Lote, TipoProducto, Venta
from simulador.rentabilidad import rentabilidad

AVISO_LEGAL = "Cálculo orientativo con fines divulgativos. No constituye asesoramiento fiscal ni financiero."
PRIVACIDAD = "Tus datos no se guardan: solo existen mientras tienes la página abierta."

TIPO_POR_ETIQUETA = {"Fondo de inversión": TipoProducto.FONDO, "ETF": TipoProducto.ETF}
REEMBOLSAR = "Reembolsar"
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


@dataclass(frozen=True)
class DatosProducto:
    """Lo que el usuario ha rellenado en la tarjeta de un producto, todavía sin validar."""

    nombre: str
    tipo: TipoProducto
    operacion: Escenario
    # Modo sencillo: toda la inversión como un único lote.
    invertido: float = 0.0
    fecha_compra: date | None = None
    valor_hoy: float = 0.0  # valor actual de toda la inversión
    porcentaje_vendido: int = 100
    # Modo detallado: una fila por compra y venta por participaciones.
    lotes: pd.DataFrame | None = None
    participaciones_vendidas: float = 0.0  # 0 = todas
    precio_venta: float = 0.0
    comision_venta: float = 0.0


def fecha_venta_por_defecto() -> date:
    hoy = date.today()
    return hoy if hoy.year == normativa.EJERCICIO else date(normativa.EJERCICIO, 12, 31)


def lotes_ejemplo() -> pd.DataFrame:
    """1.000 participaciones a 20 €: los mismos 20.000 € del ejemplo sencillo."""
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


def construir_posicion(datos: DatosProducto, fecha_venta: date) -> Posicion:
    nombre = datos.nombre.strip()
    if not nombre:
        raise ValueError("Pon un nombre a cada inversión.")

    if datos.lotes is None:
        # Modo sencillo: un único lote de una unidad que cuesta lo invertido. Vender un porcentaje es
        # vender esa fracción de la unidad, así que el coste se imputa en la misma proporción.
        if datos.fecha_compra is None:
            raise ValueError(f"Indica cuándo invertiste en «{nombre}».")
        lotes = (Lote(datos.fecha_compra, Decimal("1"), a_decimal(datos.invertido)),)
        venta = Venta(fecha_venta, Decimal(datos.porcentaje_vendido) / 100, a_decimal(datos.valor_hoy))
    else:
        lotes = tuple(leer_lotes(datos.lotes))
        if not lotes:
            raise ValueError(f"«{nombre}» no tiene ninguna compra completa.")
        vendidas = (
            a_decimal(datos.participaciones_vendidas)
            if datos.participaciones_vendidas
            else sum((lote.participaciones for lote in lotes), Decimal("0"))
        )
        venta = Venta(fecha_venta, vendidas, a_decimal(datos.precio_venta), a_decimal(datos.comision_venta))
    return Posicion(nombre, datos.tipo, lotes, venta)


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

    lineas = []
    if "seleccion" in por_clave:
        s = por_clave["seleccion"].resultado
        latente = (
            f"un ahorro latente de {formato_euros(-s.impuesto_latente)}: la pérdida que aplazas reducirá tu "
            "impuesto cuando reembolses"
            if s.impuesto_latente < 0
            else f"un impuesto latente de {formato_euros(s.impuesto_latente)}"
        )
        lineas.append(
            f"- **Tu selección:** pagas {formato_euros(s.cuota)} de cuota este año, con "
            f"{formato_euros(s.retencion)} de retención, y dejas {latente}."
        )
    lineas.append(
        f"- **{reembolsar.titulo}:** la cuota es {formato_euros(r.cuota)}. Al reembolsar se retienen "
        f"{formato_euros(r.retencion)}, que se descuentan en la Renta"
        + (" (los ETF no tienen retención)." if hay_etf else ".")
    )
    if len(posiciones) > 1 and r.retencion > r.cuota and r.retencion > 0:
        lineas.append(
            "- **Las retenciones superan la cuota** porque se calculan fondo a fondo y no descuentan las "
            "pérdidas de otros productos: la diferencia se devuelve en la Renta."
        )
    t = por_clave["traspasar"].resultado
    linea_traspaso = (
        f"- **{por_clave['traspasar'].titulo}:** "
        + ("no tributas ahora" if len(posiciones) == 1 else "los fondos no tributan ahora")
        + "; la ganancia se difiere. "
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


def mostrar_tarjetas(planes: list[PlanMostrado]) -> None:
    """Una tarjeta por plan con la cuota en grande y el resto de cifras debajo."""
    for columna, plan in zip(st.columns(len(planes)), planes):
        with columna.container(border=True):
            st.markdown(f'<div class="titulo-plan">{plan.titulo}</div>', unsafe_allow_html=True)
            r = plan.resultado
            if r is None:
                st.metric(f"Cuota de IRPF en {normativa.EJERCICIO}", NO_DISPONIBLE)
                st.caption("Un ETF no se puede traspasar: venderlo siempre tributa en el ejercicio (art. 94 LIRPF).")
                continue
            st.metric(f"Cuota de IRPF en {normativa.EJERCICIO}", formato_euros(r.cuota))
            filas = [
                ("Retención al vender", r.retencion),
                ("Efecto en la Renta", r.regularizacion_renta),
                ("Impuesto latente", r.impuesto_latente),
            ]
            html = "".join(
                f'<div class="fila"><span>{concepto}</span><span class="cifra">{formato_euros(importe)}</span></div>'
                for concepto, importe in filas
            )
            st.markdown(f'<div class="cifras">{html}</div>', unsafe_allow_html=True)


def mostrar_resultados(posiciones: list[Posicion], planes: list[PlanMostrado]) -> None:
    st.subheader("Lo que pagas en cada caso")
    mostrar_tarjetas(planes)
    st.markdown(mensaje_clave(posiciones, planes))

    if len(posiciones) > 1:
        st.markdown("**Por inversión**")
        st.dataframe(tabla_por_producto(posiciones, planes), width="stretch")

    saldos = tabla_saldos_pendientes(planes)
    if saldos is not None:
        st.markdown("**Saldos negativos tras la operación**")
        st.dataframe(saldos, width="stretch")

    for texto in textos_avisos(planes):
        st.warning(texto)

    mostrar_visualizacion(posiciones, planes)

    with st.expander("Ver la tabla completa"):
        st.dataframe(tabla_comparativa(planes), width="stretch")
    with st.expander("Cómo leer el resultado"):
        st.markdown(
            "- **Cuota**: lo que la operación añade a tu IRPF del año (negativa si una pérdida lo reduce).\n"
            "- **Retención**: lo que la gestora ingresa a Hacienda al reembolsar. Es un adelanto, no un "
            "impuesto adicional.\n"
            "- **Efecto en la Renta**: cuota menos retención. Positivo: lo que te queda por pagar en la "
            "declaración. Negativo: lo que reduce tu resultado.\n"
            "- **Impuesto latente**: la cuota que el traspaso aplaza, calculada como si reembolsaras hoy. "
            "La real dependerá del valor y de tus rentas el año en que reembolses. Si es negativo, es un ahorro "
            "futuro: una pérdida que el traspaso aplaza.\n"
            "- **Tu selección** aparece cuando combinas operaciones distintas (por ejemplo, reembolsar un fondo "
            "y traspasar otro)."
        )
    with st.expander("Supuestos y alcance"):
        st.markdown(SUPUESTOS)


def resumen_neto(plan: ResultadoPlan) -> tuple[Decimal, Decimal, Decimal] | None:
    """(ganancia de lo que se vende, invertido en lo que se vende, neto tras el IRPF), o None si no se vende nada."""
    vendidas = [p for p in plan.posiciones if p.operacion is not Escenario.TRASPASO_FONDO]
    if not vendidas:
        return None
    ganancia = sum((p.ganancia_patrimonial for p in vendidas), Decimal("0"))
    invertido = sum((p.valor_adquisicion for p in vendidas), Decimal("0"))
    return ganancia, invertido, ganancia - plan.cuota


def nota_plan(plan: ResultadoPlan) -> str:
    """Retención, efecto en la Renta y ganancia aplazada del plan, en una o dos frases."""
    frases = []
    if plan.retencion > 0:
        frases.append(
            f"Al reembolsar se retienen {formato_euros(plan.retencion)}; el efecto en la Renta es de "
            f"{formato_euros(plan.regularizacion_renta)} (cuota menos retención)."
        )
    traspasadas = [p for p in plan.posiciones if p.operacion is Escenario.TRASPASO_FONDO]
    if traspasadas:
        aplazada = sum((p.ganancia_patrimonial for p in traspasadas), Decimal("0"))
        frases.append(
            f"Con el traspaso aplazas {formato_euros(aplazada)} de ganancia; el impuesto latente es de "
            f"{formato_euros(plan.impuesto_latente)}."
        )
    return " ".join(frases)


def mostrar_visualizacion(posiciones: list[Posicion], planes: list[PlanMostrado]) -> None:
    st.subheader("Tus inversiones, de un vistazo")

    st.markdown("**Rentabilidad de tus inversiones**")
    filas = [(p.nombre, rentabilidad(p.lotes, p.venta.precio_unitario, p.venta.fecha)) for p in posiciones]
    st.plotly_chart(figura_rentabilidad(filas), width="stretch", config={"displayModeBar": False})
    st.caption(
        "Antes de impuestos, con todas tus participaciones valoradas al precio de hoy. La rentabilidad anual "
        "(TIR) solo se muestra a partir de un año desde la primera compra."
    )

    st.markdown("**De la ganancia al neto tras el IRPF**")
    disponibles = [plan for plan in planes if plan.resultado is not None]
    titulo = st.radio("Plan", [plan.titulo for plan in disponibles], horizontal=True, label_visibility="collapsed")
    plan = next(plan.resultado for plan in disponibles if plan.titulo == titulo)

    resumen = resumen_neto(plan)
    if resumen is None:
        st.info(f"Con este plan no vendes nada, así que hoy no hay impuesto. {nota_plan(plan)}")
        return
    ganancia, invertido, neto = resumen
    st.plotly_chart(figura_cascada(pasos_cascada(plan)), width="stretch", config={"displayModeBar": False})
    antes, impuesto, despues = st.columns(3)
    antes.metric("Ganancia antes de impuestos", formato_euros(ganancia))
    antes.caption(f"{porcentaje(ganancia / invertido)} sobre lo invertido en lo que vendes")
    impuesto.metric(f"IRPF {normativa.EJERCICIO}", formato_euros(plan.cuota))
    despues.metric("Neto tras impuestos", formato_euros(neto))
    despues.caption(f"{porcentaje(neto / invertido)} sobre lo invertido en lo que vendes")
    nota = nota_plan(plan)
    if nota:
        st.caption(nota)


# --- Página ---------------------------------------------------------------------------------------

# Los bordes y textos secundarios salen del color del texto del tema activo (currentColor).
# Donde hace falta un color propio, light-dark(claro, oscuro) lo elige según el modo: Streamlit
# declara color-scheme en .stApp. El resto de colores están en .streamlit/config.toml.
ESTILOS = """
<style>
.cabecera {
    border-top: 4px solid #16b182;
    padding: 1.25rem 0 1.25rem;
    margin-bottom: 1rem;
    border-bottom: 1px solid color-mix(in srgb, currentColor 18%, transparent);
}
.cabecera .contexto { font-size: 0.9rem; opacity: 0.7; }
.cabecera h1 { font-size: 2.4rem; line-height: 1.15; margin: 0.4rem 0 0.5rem; padding: 0; }
.cabecera p { opacity: 0.8; margin: 0; max-width: 46rem; }
.stApp h1, .stApp h2, .stApp h3 { color: light-dark(#153a31, #e9efed); }
.titulo-plan { font-weight: 600; margin-bottom: 0.25rem; color: light-dark(#307163, #16b182); }
[data-testid="stMetricValue"] { font-variant-numeric: tabular-nums; }
.cifras .fila {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    padding: 0.4rem 0;
    border-top: 1px solid color-mix(in srgb, currentColor 14%, transparent);
}
.cifras .cifra { font-variant-numeric: tabular-nums; white-space: nowrap; }
</style>
"""

CABECERA = f"""
<div class="cabecera">
  <div class="contexto">IRPF {normativa.EJERCICIO} · Territorio común · Simulador divulgativo</div>
  <h1>Vender un fondo o un ETF: qué pagas en el IRPF</h1>
  <p>Introduce tus inversiones y compara reembolsar, traspasar o vender. {PRIVACIDAD}</p>
</div>
"""


def _ids_productos() -> list[int]:
    if "productos" not in st.session_state:
        st.session_state.productos = [0]
        st.session_state.siguiente_producto = 1
    return st.session_state.productos


def _anadir_producto() -> None:
    st.session_state.productos.append(st.session_state.siguiente_producto)
    st.session_state.siguiente_producto += 1


def _quitar_producto(id_producto: int) -> None:
    st.session_state.productos.remove(id_producto)


def tarjeta_producto(id_producto: int, numero: int, varios: bool) -> DatosProducto:
    """Tarjeta con las preguntas de un producto. Las claves de los widgets llevan su id."""
    primero = id_producto == 0
    clave = lambda campo: f"{campo}_{id_producto}"  # noqa: E731

    with st.container(border=True):
        izquierda, derecha = st.columns([4, 1], vertical_alignment="bottom")
        nombre = izquierda.text_input(
            "Nombre", value="Mi inversión" if primero else f"Inversión {numero}", key=clave("nombre")
        )
        if varios:
            derecha.button("Quitar", key=clave("quitar"), on_click=_quitar_producto, args=(id_producto,))
        tipo = TIPO_POR_ETIQUETA[
            st.radio("¿Qué es?", list(TIPO_POR_ETIQUETA), horizontal=True, key=clave("tipo"))
        ]

        if st.toggle("Tengo varias compras en fechas distintas", key=clave("detallado")):
            st.caption("Una fila por compra. Si vendes solo una parte, se venden primero las más antiguas.")
            datos_venta = dict(
                lotes=st.data_editor(
                    lotes_ejemplo(),
                    key=clave("lotes"),
                    num_rows="dynamic",
                    hide_index=True,
                    column_config={
                        "fecha": st.column_config.DateColumn("Fecha", format="DD/MM/YYYY", required=True),
                        "participaciones": st.column_config.NumberColumn("Participaciones", min_value=0, format="%.4f"),
                        "precio_unitario": st.column_config.NumberColumn("Precio (€)", min_value=0, format="%.4f"),
                        "comision": st.column_config.NumberColumn(
                            "Comisión (€)", min_value=0, format="%.2f", default=0.0
                        ),
                    },
                )
            )
            c1, c2, c3 = st.columns(3)
            datos_venta["participaciones_vendidas"] = c1.number_input(
                "Participaciones que vendes",
                min_value=0.0,
                value=0.0,
                step=1.0,
                format="%.4f",
                help="Déjalo en 0 para venderlas todas.",
                key=clave("participaciones"),
            )
            datos_venta["precio_venta"] = c2.number_input(
                "Precio de venta hoy (€)", min_value=0.0, value=30.0, format="%.4f", key=clave("precio")
            )
            datos_venta["comision_venta"] = c3.number_input(
                "Comisión de venta (€)", min_value=0.0, value=0.0, format="%.2f", key=clave("comision")
            )
        else:
            c1, c2 = st.columns(2)
            datos_venta = dict(
                invertido=c1.number_input(
                    "Cuánto invertiste (€)",
                    min_value=0.0,
                    value=20000.0 if primero else 10000.0,
                    step=500.0,
                    format="%.0f",
                    key=clave("invertido"),
                ),
                valor_hoy=c2.number_input(
                    "Cuánto vale hoy (€)",
                    min_value=0.0,
                    value=30000.0 if primero else 10000.0,
                    step=500.0,
                    format="%.0f",
                    key=clave("valor_hoy"),
                ),
                fecha_compra=c1.date_input(
                    "Cuándo invertiste",
                    value=date(2023, 1, 15),
                    min_value=date(1990, 1, 1),
                    max_value=date(normativa.EJERCICIO, 12, 31),
                    format="DD/MM/YYYY",
                    key=clave("fecha_compra"),
                ),
                porcentaje_vendido=c2.slider(
                    "Qué parte vendes", min_value=1, max_value=100, value=100, format="%d %%", key=clave("porcentaje")
                ),
            )

        if tipo is TipoProducto.ETF:
            operacion = Escenario.VENTA_ETF
            if varios:
                st.caption("Un ETF no admite traspaso: se vende y tributa este año.")
        elif varios:
            elegida = st.radio("¿Qué harías con él?", [REEMBOLSAR, TRASPASAR], horizontal=True, key=clave("operacion"))
            operacion = Escenario.TRASPASO_FONDO if elegida == TRASPASAR else Escenario.REEMBOLSO_FONDO
        else:
            operacion = Escenario.REEMBOLSO_FONDO  # con un solo producto se muestran las dos opciones

    return DatosProducto(nombre=nombre, tipo=tipo, operacion=operacion, **datos_venta)


def main() -> None:
    st.set_page_config(page_title="Simulador fiscal: fondo vs. ETF", layout="wide")
    st.markdown(ESTILOS, unsafe_allow_html=True)
    st.markdown(CABECERA, unsafe_allow_html=True)
    st.info(AVISO_LEGAL)

    izquierda, derecha = st.columns([3, 2], gap="large")
    with izquierda:
        st.subheader("Tus inversiones")
        ids = _ids_productos()
        datos = [tarjeta_producto(id_producto, n, len(ids) > 1) for n, id_producto in enumerate(ids, start=1)]
        st.button("+ Añadir otro fondo o ETF", key="anadir", on_click=_anadir_producto)

    with derecha:
        st.subheader(f"Tu situación en {normativa.EJERCICIO}")
        st.caption("Opcional. Si no lo sabes, déjalo como está: el cálculo supone que no tienes otras rentas del ahorro.")
        fecha_venta = st.date_input(
            "Fecha de la venta",
            value=fecha_venta_por_defecto(),
            min_value=date(normativa.EJERCICIO, 1, 1),
            max_value=date(normativa.EJERCICIO, 12, 31),
            format="DD/MM/YYYY",
        )
        rendimientos = st.number_input(
            "Intereses y dividendos del año (€)",
            value=0.0,
            step=100.0,
            format="%.0f",
            help="Saldo de rendimientos del capital mobiliario. Si es negativo, ponlo con signo menos.",
        )
        otras_ganancias = st.number_input(
            "Otras ganancias o pérdidas por ventas del año (€)",
            value=0.0,
            step=100.0,
            format="%.0f",
            help="Saldo de otras ganancias y pérdidas patrimoniales. Las pérdidas, con signo menos.",
        )
        with st.expander("Pérdidas pendientes de años anteriores"):
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

    st.divider()
    try:
        posiciones = [construir_posicion(d, fecha_venta) for d in datos]
        operaciones = {posicion.nombre: d.operacion for posicion, d in zip(posiciones, datos)}
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
