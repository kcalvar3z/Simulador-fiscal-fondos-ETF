"""Ganancia patrimonial, cuota de la base del ahorro y retención.

Todas las funciones trabajan con importes sin redondear; solo se redondea a
céntimos al presentar el resultado (`redondear_centimos`).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from simulador import normativa
from simulador.lotes import Lote, TipoProducto, Venta, asignar_fifo
from simulador.normativa import Tramo

CENTIMO = Decimal("0.01")


@dataclass(frozen=True)
class ResultadoVenta:
    valor_transmision: Decimal
    valor_adquisicion: Decimal
    ganancia_patrimonial: Decimal
    lotes_restantes: tuple[Lote, ...]


def calcular_ganancia(lotes: Sequence[Lote], venta: Venta) -> ResultadoVenta:
    """Ganancia o pérdida = valor de transmisión − valor de adquisición FIFO (arts. 34, 35 y 37.2 LIRPF)."""
    if any(lote.fecha > venta.fecha for lote in lotes):
        raise ValueError("Hay lotes con fecha de compra posterior a la venta.")
    asignacion = asignar_fifo(lotes, venta.participaciones)
    return ResultadoVenta(
        valor_transmision=venta.valor_transmision,
        valor_adquisicion=asignacion.valor_adquisicion,
        ganancia_patrimonial=venta.valor_transmision - asignacion.valor_adquisicion,
        lotes_restantes=asignacion.lotes_restantes,
    )


def cuota_ahorro(
    base_liquidable_ahorro: Decimal,
    escala: Sequence[Tramo] = normativa.ESCALA_AHORRO_2026,
) -> Decimal:
    """Aplica la escala progresiva tramo a tramo: cada tramo tributa a su propio tipo.

    Supuesto del simulador: contribuyente con un salario estándar (medio o más frecuente),
    cuya base general absorbe íntegramente el mínimo personal y familiar; por eso este no
    minora la cuota del ahorro (art. 66.1.2.º LIRPF).
    """
    if base_liquidable_ahorro < 0:
        raise ValueError("La base liquidable del ahorro no puede ser negativa.")
    cuota = Decimal("0")
    desde = Decimal("0")
    for tramo in escala:
        hasta = base_liquidable_ahorro if tramo.hasta is None else min(base_liquidable_ahorro, tramo.hasta)
        if hasta <= desde:
            break
        cuota += (hasta - desde) * tramo.tipo
        desde = hasta
    return cuota


@dataclass(frozen=True)
class TramoAplicado:
    """Parte de la base que cae en un tramo de la escala y su cuota (negativa si la base baja)."""

    desde: Decimal
    hasta: Decimal
    tipo: Decimal
    cuota: Decimal

    @property
    def importe(self) -> Decimal:
        return self.hasta - self.desde


def desglose_cuota(
    base_sin_venta: Decimal,
    base_con_venta: Decimal,
    escala: Sequence[Tramo] = normativa.ESCALA_AHORRO_2026,
) -> tuple[TramoAplicado, ...]:
    """Tramos que recorre la base al pasar de `base_sin_venta` a `base_con_venta`.

    La suma de las cuotas es `cuota_incremental`. Si la base baja (una pérdida), las cuotas
    son negativas: es impuesto que se deja de pagar.
    """
    for base in (base_sin_venta, base_con_venta):
        if base < 0:
            raise ValueError("La base liquidable del ahorro no puede ser negativa.")
    signo = 1 if base_con_venta >= base_sin_venta else -1
    inferior, superior = sorted((base_sin_venta, base_con_venta))
    tramos = []
    desde_tramo = Decimal("0")
    for tramo in escala:
        hasta_tramo = superior if tramo.hasta is None else tramo.hasta
        desde = max(inferior, desde_tramo)
        hasta = min(superior, hasta_tramo)
        if hasta > desde:
            tramos.append(TramoAplicado(desde, hasta, tramo.tipo, signo * (hasta - desde) * tramo.tipo))
        if tramo.hasta is None or hasta_tramo >= superior:
            break
        desde_tramo = hasta_tramo
    return tuple(tramos)


def cuota_incremental(base_sin_venta: Decimal, base_con_venta: Decimal) -> Decimal:
    """Cuota atribuible a la venta: aísla su efecto del resto de rentas del ahorro."""
    return cuota_ahorro(base_con_venta) - cuota_ahorro(base_sin_venta)


def retencion(ganancia_patrimonial: Decimal, tipo_producto: TipoProducto) -> Decimal:
    """Pago a cuenta al vender o reembolsar. Se descuenta en la Renta; no es la cuota final.

    Fondo: 19 % de la ganancia (art. 101.6 LIRPF). ETF: sin retención (art. 75.3.j RIRPF).
    Si hay pérdida no hay nada que retener.
    """
    if ganancia_patrimonial <= 0:
        return Decimal("0")
    tipo = {
        TipoProducto.FONDO: normativa.TIPO_RETENCION_REEMBOLSO_FONDO,
        TipoProducto.ETF: normativa.TIPO_RETENCION_VENTA_ETF,
    }[tipo_producto]
    return ganancia_patrimonial * tipo


def redondear_centimos(importe: Decimal) -> Decimal:
    return importe.quantize(CENTIMO, rounding=ROUND_HALF_UP)
