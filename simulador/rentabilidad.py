"""Rentabilidad de una inversión: total y anual (TIR).

No es cálculo fiscal, pero sigue las mismas reglas que el resto de `simulador/`:
importes en Decimal y funciones puras.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from simulador.lotes import Lote

DIAS_POR_ANIO = Decimal("365")
_ITERACIONES_TIR = 200
_TASA_MINIMA = Decimal("-0.9999")
_TASA_MAXIMA = Decimal("100")


@dataclass(frozen=True)
class Rentabilidad:
    invertido: Decimal  # incluye las comisiones de compra
    valor_actual: Decimal
    anual: Decimal | None  # TIR; None si la primera compra tiene menos de un año

    @property
    def ganancia(self) -> Decimal:
        return self.valor_actual - self.invertido

    @property
    def total(self) -> Decimal:
        return self.ganancia / self.invertido


def rentabilidad(lotes: Sequence[Lote], precio_actual: Decimal, fecha: date) -> Rentabilidad:
    """Rentabilidad de todas las participaciones de `lotes` valoradas a `precio_actual` en `fecha`.

    La anual es la TIR: la tasa que iguala lo invertido, en la fecha de cada compra, con el
    valor actual. Con una sola compra coincide con (valor / invertido) ^ (1 / años) − 1.
    No se anualiza por debajo de un año: con periodos cortos da cifras engañosas.
    """
    if not lotes:
        raise ValueError("No hay compras para calcular la rentabilidad.")
    if any(lote.fecha > fecha for lote in lotes):
        raise ValueError("Hay compras posteriores a la fecha de valoración.")
    invertido = sum((lote.valor_adquisicion for lote in lotes), Decimal("0"))
    if invertido <= 0:
        raise ValueError("Lo invertido debe ser positivo para calcular la rentabilidad.")
    participaciones = sum((lote.participaciones for lote in lotes), Decimal("0"))
    valor_actual = participaciones * precio_actual

    primera = min(lote.fecha for lote in lotes)
    if (fecha - primera).days < DIAS_POR_ANIO:
        anual = None
    elif valor_actual == 0:
        anual = Decimal("-1")
    else:
        flujos = [(_anios(lote.fecha, fecha), -lote.valor_adquisicion) for lote in lotes]
        flujos.append((Decimal("0"), valor_actual))
        anual = _tir(flujos)
    return Rentabilidad(invertido=invertido, valor_actual=valor_actual, anual=anual)


def _anios(desde: date, hasta: date) -> Decimal:
    return Decimal((hasta - desde).days) / DIAS_POR_ANIO


def _tir(flujos: Sequence[tuple[Decimal, Decimal]]) -> Decimal:
    """Tasa anual que anula el valor de los flujos llevados a la fecha de valoración.

    Cada flujo es (años antes de la fecha de valoración, importe): las compras en negativo
    y el valor actual en positivo. Ese valor baja al subir la tasa (las compras capitalizadas
    pesan más), así que basta una bisección.
    """

    def valor(tasa: Decimal) -> Decimal:
        return sum((importe * (1 + tasa) ** anios for anios, importe in flujos), Decimal("0"))

    bajo, alto = _TASA_MINIMA, _TASA_MAXIMA
    for _ in range(_ITERACIONES_TIR):
        medio = (bajo + alto) / 2
        if valor(medio) > 0:  # las compras capitalizadas aún no alcanzan el valor actual
            bajo = medio
        else:
            alto = medio
    return (bajo + alto) / 2
