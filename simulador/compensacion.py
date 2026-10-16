"""Integración y compensación de rentas en la base imponible del ahorro (art. 49 LIRPF).

Alcance actual: compensación dentro del ejercicio. Los saldos negativos que no se
pueden compensar se devuelven como pendientes para los cuatro años siguientes,
pero todavía no se aplican saldos pendientes de ejercicios anteriores.
"""

from dataclasses import dataclass
from decimal import Decimal

from simulador import normativa

CERO = Decimal("0")


@dataclass(frozen=True)
class ResultadoCompensacion:
    base_ahorro: Decimal
    rendimientos_negativos_pendientes: Decimal
    perdidas_patrimoniales_pendientes: Decimal


def compensar_base_ahorro(
    saldo_rendimientos: Decimal,
    saldo_ganancias_perdidas: Decimal,
) -> ResultadoCompensacion:
    """Compensa entre sí los dos saldos de la base del ahorro.

    Cada saldo llega ya integrado "exclusivamente entre sí": el de rendimientos del
    capital mobiliario y el de ganancias y pérdidas patrimoniales del ejercicio.
    Un saldo negativo se compensa con el positivo del otro bloque hasta el 25 % de
    este (art. 49.1.a y b), y por la cuantía máxima posible (art. 49.2).
    """
    limite = normativa.LIMITE_COMPENSACION_CRUZADA
    rendimientos = saldo_rendimientos
    ganancias = saldo_ganancias_perdidas
    perdidas_pendientes = CERO
    rendimientos_pendientes = CERO

    if ganancias < 0:  # art. 49.1.b
        compensado = min(-ganancias, max(rendimientos, CERO) * limite)
        rendimientos -= compensado
        perdidas_pendientes = -ganancias - compensado
        ganancias = CERO

    if rendimientos < 0:  # art. 49.1.a
        compensado = min(-rendimientos, ganancias * limite)
        ganancias -= compensado
        rendimientos_pendientes = -rendimientos - compensado
        rendimientos = CERO

    return ResultadoCompensacion(
        base_ahorro=rendimientos + ganancias,
        rendimientos_negativos_pendientes=rendimientos_pendientes,
        perdidas_patrimoniales_pendientes=perdidas_pendientes,
    )
