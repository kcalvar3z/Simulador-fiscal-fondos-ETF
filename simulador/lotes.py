"""Compras por lotes y asignación FIFO (arts. 37.2 y 94.1.a LIRPF).

Cuando existen valores homogéneos, se consideran transmitidos los adquiridos en
primer lugar. Cada simulación trabaja con un único grupo de valores homogéneos
(una sola clase de un fondo o un solo ETF), es decir, una única cola FIFO.
"""

from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from enum import Enum


class TipoProducto(Enum):
    FONDO = "fondo"
    ETF = "etf"


def _validar_operacion(participaciones: Decimal, precio_unitario: Decimal, comision: Decimal) -> None:
    if participaciones <= 0:
        raise ValueError("El número de participaciones debe ser positivo.")
    if precio_unitario < 0:
        raise ValueError("El precio unitario no puede ser negativo.")
    if comision < 0:
        raise ValueError("La comisión no puede ser negativa.")


@dataclass(frozen=True)
class Lote:
    """Compra de participaciones. La comisión forma parte del valor de adquisición (art. 35 LIRPF)."""

    fecha: date
    participaciones: Decimal
    precio_unitario: Decimal
    comision: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        _validar_operacion(self.participaciones, self.precio_unitario, self.comision)

    @property
    def valor_adquisicion(self) -> Decimal:
        return self.participaciones * self.precio_unitario + self.comision


@dataclass(frozen=True)
class Venta:
    """Venta o reembolso. La comisión minora el valor de transmisión (art. 35 LIRPF)."""

    fecha: date
    participaciones: Decimal
    precio_unitario: Decimal
    comision: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        _validar_operacion(self.participaciones, self.precio_unitario, self.comision)

    @property
    def valor_transmision(self) -> Decimal:
        return self.participaciones * self.precio_unitario - self.comision


@dataclass(frozen=True)
class AsignacionFIFO:
    """Resultado de asignar una venta a los lotes por orden de antigüedad."""

    valor_adquisicion: Decimal
    lotes_restantes: tuple[Lote, ...]


def valor_adquisicion_total(lotes: Sequence[Lote]) -> Decimal:
    return sum((lote.valor_adquisicion for lote in lotes), Decimal("0"))


def asignar_fifo(lotes: Sequence[Lote], participaciones: Decimal) -> AsignacionFIFO:
    """Consume los lotes del más antiguo al más reciente.

    Si un lote se vende en parte, su comisión de compra se imputa en proporción a
    las participaciones vendidas y el resto queda en el lote restante.
    """
    if participaciones <= 0:
        raise ValueError("El número de participaciones vendidas debe ser positivo.")
    disponibles = sum((lote.participaciones for lote in lotes), Decimal("0"))
    if participaciones > disponibles:
        raise ValueError(
            f"Se venden {participaciones} participaciones y solo hay {disponibles} en cartera."
        )

    # sorted() es estable: dos lotes con la misma fecha conservan el orden en que se introdujeron.
    pendientes = participaciones
    valor_adquisicion = Decimal("0")
    lotes_restantes: list[Lote] = []
    for lote in sorted(lotes, key=lambda lote: lote.fecha):
        if pendientes == 0:
            lotes_restantes.append(lote)
            continue
        vendidas = min(pendientes, lote.participaciones)
        comision_imputada = lote.comision * vendidas / lote.participaciones
        valor_adquisicion += vendidas * lote.precio_unitario + comision_imputada
        pendientes -= vendidas
        if vendidas < lote.participaciones:
            lotes_restantes.append(
                replace(
                    lote,
                    participaciones=lote.participaciones - vendidas,
                    comision=lote.comision - comision_imputada,
                )
            )
    return AsignacionFIFO(valor_adquisicion, tuple(lotes_restantes))
