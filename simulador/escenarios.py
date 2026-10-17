"""Escenarios para deshacer una inversión y su coste fiscal en el ejercicio.

- Reembolso de fondo: la ganancia tributa en el ejercicio y lleva retención del 19 %.
- Traspaso de fondo: la ganancia se difiere (art. 94.1.a LIRPF), no lleva retención
  (art. 101.6 LIRPF) y queda un impuesto latente.
- Venta de ETF: la ganancia tributa en el ejercicio, sin retención (art. 75.3.j RIRPF).
  No admite traspaso (art. 94.1.a, último párrafo, y 94.2.a LIRPF).

Un plan asigna una operación a cada posición (cada fondo o ETF, con su propia cola
FIFO). Las ganancias y pérdidas de todas las posiciones se integran juntas en la
base del ahorro, así que la cuota y el impuesto latente solo existen en total: con
una escala progresiva, repartirlos entre posiciones no tiene una respuesta única.
La retención sí se calcula posición a posición (art. 97.1 RIRPF).

Los importes salen sin redondear.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from simulador import normativa
from simulador.calculo import calcular_ganancia, cuota_ahorro, retencion
from simulador.compensacion import ResultadoCompensacion, SaldoPendiente, compensar_base_ahorro
from simulador.lotes import Lote, TipoProducto, Venta

CERO = Decimal("0")


class Escenario(Enum):
    """Operación que se hace con una posición."""

    REEMBOLSO_FONDO = "reembolso_fondo"
    TRASPASO_FONDO = "traspaso_fondo"
    VENTA_ETF = "venta_etf"


_PRODUCTO = {
    Escenario.REEMBOLSO_FONDO: TipoProducto.FONDO,
    Escenario.TRASPASO_FONDO: TipoProducto.FONDO,
    Escenario.VENTA_ETF: TipoProducto.ETF,
}


class Aviso(Enum):
    """Situaciones que el simulador detecta pero no calcula. El texto lo pone la app."""

    REGLA_RECOMPRA = "regla_recompra"  # pérdida computada: art. 33.5.f y g LIRPF
    REGIMEN_TRANSITORIO_ETF = "regimen_transitorio_etf"  # ETF con lotes anteriores a 2022: DT 36.ª LIRPF
    SALDOS_CADUCADOS = "saldos_caducados"  # saldos negativos que no se compensan y se pierden


@dataclass(frozen=True)
class OtrasRentasAhorro:
    """Rentas del ahorro del ejercicio distintas de las operaciones simuladas."""

    saldo_rendimientos: Decimal = CERO
    saldo_ganancias_perdidas: Decimal = CERO
    rendimientos_negativos_anteriores: tuple[SaldoPendiente, ...] = ()
    perdidas_patrimoniales_anteriores: tuple[SaldoPendiente, ...] = ()


@dataclass(frozen=True)
class Posicion:
    """Un fondo (una clase concreta) o un ETF: sus compras y la venta que se simula."""

    nombre: str
    tipo: TipoProducto
    lotes: tuple[Lote, ...]
    venta: Venta


@dataclass(frozen=True)
class ResultadoPosicion:
    nombre: str
    operacion: Escenario
    ganancia_patrimonial: Decimal  # tribute hoy o no
    retencion: Decimal
    avisos: tuple[Aviso, ...] = ()


@dataclass(frozen=True)
class ResultadoPlan:
    posiciones: tuple[ResultadoPosicion, ...]
    cuota: Decimal  # atribuible a las operaciones que tributan hoy; negativa si las pérdidas ahorran impuesto
    impuesto_latente: Decimal  # cuota diferida por los traspasos, calculada como si se reembolsaran hoy
    compensacion: ResultadoCompensacion  # base del ahorro y saldos pendientes resultantes
    avisos: tuple[Aviso, ...] = ()  # los que afectan al plan entero

    @property
    def retencion(self) -> Decimal:
        return sum((posicion.retencion for posicion in self.posiciones), CERO)

    @property
    def regularizacion_renta(self) -> Decimal:
        """Lo que el plan añade a pagar (positivo) o a devolver (negativo) en la Renta."""
        return self.cuota - self.retencion


@dataclass(frozen=True)
class ResultadoEscenario:
    """Resultado de una única posición con una operación. Ver `calcular_escenario`."""

    escenario: Escenario
    ganancia_patrimonial: Decimal
    cuota: Decimal
    retencion: Decimal
    impuesto_latente: Decimal
    compensacion: ResultadoCompensacion
    avisos: tuple[Aviso, ...] = ()

    @property
    def regularizacion_renta(self) -> Decimal:
        """Lo que la operación añade a pagar (positivo) o a devolver (negativo) en la Renta."""
        return self.cuota - self.retencion


def escenarios_disponibles(tipo_producto: TipoProducto) -> tuple[Escenario, ...]:
    return tuple(escenario for escenario, producto in _PRODUCTO.items() if producto is tipo_producto)


# --- Planes con varias posiciones -----------------------------------------------------------------


def simular_plan(
    posiciones: Sequence[Posicion],
    operaciones: Mapping[str, Escenario],
    otras_rentas: OtrasRentasAhorro = OtrasRentasAhorro(),
) -> ResultadoPlan:
    """Calcula el coste fiscal de aplicar a cada posición la operación indicada por su nombre."""
    _validar_plan(posiciones, operaciones)

    ganancias = {p.nombre: calcular_ganancia(p.lotes, p.venta).ganancia_patrimonial for p in posiciones}
    ganancia_hoy = sum(
        (ganancias[p.nombre] for p in posiciones if operaciones[p.nombre] is not Escenario.TRASPASO_FONDO),
        CERO,
    )
    ganancia_total = sum(ganancias.values(), CERO)

    sin_operaciones = _compensar(otras_rentas, CERO)
    con_operaciones_de_hoy = _compensar(otras_rentas, ganancia_hoy)
    reembolsando_todo = _compensar(otras_rentas, ganancia_total)
    cuota_sin = cuota_ahorro(sin_operaciones.base_ahorro)
    cuota_hoy = cuota_ahorro(con_operaciones_de_hoy.base_ahorro)
    cuota_todo = cuota_ahorro(reembolsando_todo.base_ahorro)

    resultados = tuple(
        _resultado_posicion(posicion, operaciones[posicion.nombre], ganancias[posicion.nombre])
        for posicion in posiciones
    )
    avisos = (Aviso.SALDOS_CADUCADOS,) if _hay_caducados(con_operaciones_de_hoy) else ()
    return ResultadoPlan(
        posiciones=resultados,
        cuota=cuota_hoy - cuota_sin,
        impuesto_latente=cuota_todo - cuota_hoy,
        compensacion=con_operaciones_de_hoy,
        avisos=avisos,
    )


def operaciones_reembolsar_todo(posiciones: Sequence[Posicion]) -> dict[str, Escenario]:
    """Plan de referencia: reembolsar todos los fondos y vender todos los ETF."""
    return {p.nombre: _operacion_si_se_vende(p.tipo) for p in posiciones}


def operaciones_traspasar_fondos(posiciones: Sequence[Posicion]) -> dict[str, Escenario]:
    """Plan de referencia: traspasar todos los fondos; los ETF, que no admiten traspaso, se venden."""
    return {
        p.nombre: Escenario.TRASPASO_FONDO if p.tipo is TipoProducto.FONDO else Escenario.VENTA_ETF
        for p in posiciones
    }


# --- Una sola posición ----------------------------------------------------------------------------


def calcular_escenario(
    escenario: Escenario,
    lotes: Sequence[Lote],
    venta: Venta,
    otras_rentas: OtrasRentasAhorro = OtrasRentasAhorro(),
) -> ResultadoEscenario:
    """Atajo para una única posición: aplica `escenario` a esas compras y esa venta."""
    posicion = Posicion("posicion", _PRODUCTO[escenario], tuple(lotes), venta)
    plan = simular_plan([posicion], {posicion.nombre: escenario}, otras_rentas)
    (resultado,) = plan.posiciones
    return ResultadoEscenario(
        escenario=escenario,
        ganancia_patrimonial=resultado.ganancia_patrimonial,
        cuota=plan.cuota,
        retencion=plan.retencion,
        impuesto_latente=plan.impuesto_latente,
        compensacion=plan.compensacion,
        avisos=resultado.avisos + plan.avisos,
    )


def comparar_escenarios(
    lotes: Sequence[Lote],
    venta: Venta,
    otras_rentas: OtrasRentasAhorro = OtrasRentasAhorro(),
) -> tuple[ResultadoEscenario, ...]:
    """Los tres escenarios con los mismos datos, para compararlos (fondo frente a ETF)."""
    return tuple(calcular_escenario(escenario, lotes, venta, otras_rentas) for escenario in Escenario)


# --- Auxiliares -----------------------------------------------------------------------------------


def _validar_plan(posiciones: Sequence[Posicion], operaciones: Mapping[str, Escenario]) -> None:
    if not posiciones:
        raise ValueError("No hay ninguna posición que simular.")
    nombres = [posicion.nombre for posicion in posiciones]
    if len(nombres) != len(set(nombres)):
        raise ValueError("Hay dos posiciones con el mismo nombre.")
    for posicion in posiciones:
        if posicion.nombre not in operaciones:
            raise ValueError(f"Falta indicar qué se hace con «{posicion.nombre}».")
        if operaciones[posicion.nombre] not in escenarios_disponibles(posicion.tipo):
            if posicion.tipo is TipoProducto.ETF:
                raise ValueError(f"«{posicion.nombre}» es un ETF: no admite traspaso (art. 94 LIRPF).")
            raise ValueError(f"«{posicion.nombre}» es un fondo: se reembolsa o se traspasa.")
        if posicion.venta.fecha.year != normativa.EJERCICIO:
            raise ValueError(f"El simulador solo cubre el ejercicio {normativa.EJERCICIO}.")


def _resultado_posicion(posicion: Posicion, operacion: Escenario, ganancia: Decimal) -> ResultadoPosicion:
    se_traspasa = operacion is Escenario.TRASPASO_FONDO
    avisos = []
    if ganancia < 0 and not se_traspasa:
        avisos.append(Aviso.REGLA_RECOMPRA)
    if posicion.tipo is TipoProducto.ETF and any(
        lote.fecha < normativa.FECHA_EXCLUSION_TRASPASO_ETF_EXTRANJEROS for lote in posicion.lotes
    ):
        avisos.append(Aviso.REGIMEN_TRANSITORIO_ETF)
    return ResultadoPosicion(
        nombre=posicion.nombre,
        operacion=operacion,
        ganancia_patrimonial=ganancia,
        retencion=CERO if se_traspasa else retencion(ganancia, posicion.tipo),
        avisos=tuple(avisos),
    )


def _operacion_si_se_vende(tipo: TipoProducto) -> Escenario:
    return Escenario.REEMBOLSO_FONDO if tipo is TipoProducto.FONDO else Escenario.VENTA_ETF


def _compensar(otras_rentas: OtrasRentasAhorro, ganancia: Decimal) -> ResultadoCompensacion:
    return compensar_base_ahorro(
        saldo_rendimientos=otras_rentas.saldo_rendimientos,
        saldo_ganancias_perdidas=otras_rentas.saldo_ganancias_perdidas + ganancia,
        rendimientos_negativos_anteriores=otras_rentas.rendimientos_negativos_anteriores,
        perdidas_patrimoniales_anteriores=otras_rentas.perdidas_patrimoniales_anteriores,
    )


def _hay_caducados(compensacion: ResultadoCompensacion) -> bool:
    return bool(compensacion.rendimientos_negativos_caducados or compensacion.perdidas_patrimoniales_caducadas)
