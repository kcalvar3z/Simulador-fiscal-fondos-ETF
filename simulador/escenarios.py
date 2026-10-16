"""Escenarios para deshacer una inversión y su coste fiscal en el ejercicio.

- Reembolso de fondo: la ganancia tributa en el ejercicio y lleva retención del 19 %.
- Traspaso de fondo: la ganancia se difiere (art. 94.1.a LIRPF), no lleva retención
  (art. 101.6 LIRPF) y queda un impuesto latente.
- Venta de ETF: la ganancia tributa en el ejercicio, sin retención (art. 75.3.j RIRPF).
  No admite traspaso (art. 94.1.a, último párrafo, y 94.2.a LIRPF).

La cuota de cada escenario es la atribuible a la operación: cuota de la base del
ahorro con la operación menos cuota sin ella, tras compensar con el resto de
rentas del ahorro del ejercicio. Los importes salen sin redondear.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from simulador import normativa
from simulador.calculo import calcular_ganancia, cuota_incremental, retencion
from simulador.compensacion import ResultadoCompensacion, SaldoPendiente, compensar_base_ahorro
from simulador.lotes import Lote, TipoProducto, Venta

CERO = Decimal("0")


class Escenario(Enum):
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
    """Rentas del ahorro del ejercicio distintas de la operación simulada."""

    saldo_rendimientos: Decimal = CERO
    saldo_ganancias_perdidas: Decimal = CERO
    rendimientos_negativos_anteriores: tuple[SaldoPendiente, ...] = ()
    perdidas_patrimoniales_anteriores: tuple[SaldoPendiente, ...] = ()


@dataclass(frozen=True)
class ResultadoEscenario:
    escenario: Escenario
    ganancia_patrimonial: Decimal  # de la operación, tribute hoy o no
    cuota: Decimal  # atribuible a la operación en este ejercicio; negativa si la pérdida ahorra impuesto
    retencion: Decimal
    impuesto_latente: Decimal  # cuota diferida en el traspaso, calculada como si se reembolsara hoy
    compensacion: ResultadoCompensacion  # base del ahorro y saldos pendientes resultantes
    avisos: tuple[Aviso, ...] = ()

    @property
    def regularizacion_renta(self) -> Decimal:
        """Lo que la operación añade a pagar (positivo) o a devolver (negativo) en la Renta."""
        return self.cuota - self.retencion


def escenarios_disponibles(tipo_producto: TipoProducto) -> tuple[Escenario, ...]:
    return tuple(escenario for escenario, producto in _PRODUCTO.items() if producto is tipo_producto)


def calcular_escenario(
    escenario: Escenario,
    lotes: Sequence[Lote],
    venta: Venta,
    otras_rentas: OtrasRentasAhorro = OtrasRentasAhorro(),
) -> ResultadoEscenario:
    if venta.fecha.year != normativa.EJERCICIO:
        raise ValueError(f"El simulador solo cubre el ejercicio {normativa.EJERCICIO}.")

    ganancia = calcular_ganancia(lotes, venta).ganancia_patrimonial
    sin_operacion = _compensar(otras_rentas, CERO)
    con_operacion = _compensar(otras_rentas, ganancia)
    cuota_si_tributa = cuota_incremental(sin_operacion.base_ahorro, con_operacion.base_ahorro)

    if escenario is Escenario.TRASPASO_FONDO:
        cuota, retenido, latente, compensacion = CERO, CERO, cuota_si_tributa, sin_operacion
    else:
        cuota, retenido, latente, compensacion = (
            cuota_si_tributa,
            retencion(ganancia, _PRODUCTO[escenario]),
            CERO,
            con_operacion,
        )

    return ResultadoEscenario(
        escenario=escenario,
        ganancia_patrimonial=ganancia,
        cuota=cuota,
        retencion=retenido,
        impuesto_latente=latente,
        compensacion=compensacion,
        avisos=_avisos(escenario, lotes, ganancia, compensacion),
    )


def comparar_escenarios(
    lotes: Sequence[Lote],
    venta: Venta,
    otras_rentas: OtrasRentasAhorro = OtrasRentasAhorro(),
) -> tuple[ResultadoEscenario, ...]:
    """Los tres escenarios con los mismos datos, para compararlos (fondo frente a ETF)."""
    return tuple(calcular_escenario(escenario, lotes, venta, otras_rentas) for escenario in Escenario)


def _compensar(otras_rentas: OtrasRentasAhorro, ganancia: Decimal) -> ResultadoCompensacion:
    return compensar_base_ahorro(
        saldo_rendimientos=otras_rentas.saldo_rendimientos,
        saldo_ganancias_perdidas=otras_rentas.saldo_ganancias_perdidas + ganancia,
        rendimientos_negativos_anteriores=otras_rentas.rendimientos_negativos_anteriores,
        perdidas_patrimoniales_anteriores=otras_rentas.perdidas_patrimoniales_anteriores,
    )


def _avisos(
    escenario: Escenario,
    lotes: Sequence[Lote],
    ganancia: Decimal,
    compensacion: ResultadoCompensacion,
) -> tuple[Aviso, ...]:
    avisos = []
    if ganancia < 0 and escenario is not Escenario.TRASPASO_FONDO:
        avisos.append(Aviso.REGLA_RECOMPRA)
    if escenario is Escenario.VENTA_ETF and any(
        lote.fecha < normativa.FECHA_EXCLUSION_TRASPASO_ETF_EXTRANJEROS for lote in lotes
    ):
        avisos.append(Aviso.REGIMEN_TRANSITORIO_ETF)
    if compensacion.rendimientos_negativos_caducados or compensacion.perdidas_patrimoniales_caducadas:
        avisos.append(Aviso.SALDOS_CADUCADOS)
    return tuple(avisos)
