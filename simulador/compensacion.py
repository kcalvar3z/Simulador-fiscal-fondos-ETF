"""Integración y compensación de rentas en la base imponible del ahorro (art. 49 LIRPF).

Orden de compensación (AEAT, Manual práctico de Renta 2025, cap. 12):

1. Saldos del propio ejercicio: un saldo negativo se compensa con el saldo
   positivo del otro bloque, con el límite del 25 % de este (art. 49.1.a y b).
2. Saldos negativos pendientes de los cuatro ejercicios anteriores, primero con
   el saldo positivo de su mismo bloque, sin límite.
3. Lo que quede pendiente, con el saldo positivo restante del otro bloque. El
   límite del 25 % es conjunto con el del paso 1 y se calcula sobre el saldo
   positivo del ejercicio antes de compensaciones.

Lo que no se compensa se arrastra a los ejercicios siguientes hasta cumplir
cuatro años; después caduca (art. 49.1 y 49.2).
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import Decimal

from simulador import normativa

CERO = Decimal("0")


@dataclass(frozen=True)
class SaldoPendiente:
    """Saldo negativo de un ejercicio pendiente de compensar, expresado en positivo."""

    ejercicio: int
    importe: Decimal


@dataclass(frozen=True)
class ResultadoCompensacion:
    base_ahorro: Decimal
    rendimientos_negativos_pendientes: tuple[SaldoPendiente, ...] = ()
    perdidas_patrimoniales_pendientes: tuple[SaldoPendiente, ...] = ()
    rendimientos_negativos_caducados: Decimal = CERO
    perdidas_patrimoniales_caducadas: Decimal = CERO


def compensar_base_ahorro(
    saldo_rendimientos: Decimal,
    saldo_ganancias_perdidas: Decimal,
    rendimientos_negativos_anteriores: Sequence[SaldoPendiente] = (),
    perdidas_patrimoniales_anteriores: Sequence[SaldoPendiente] = (),
    ejercicio: int = normativa.EJERCICIO,
) -> ResultadoCompensacion:
    """Calcula la base del ahorro y los saldos negativos que quedan para años siguientes.

    `saldo_rendimientos` y `saldo_ganancias_perdidas` llegan ya integrados
    "exclusivamente entre sí": el de rendimientos del capital mobiliario y el de
    ganancias y pérdidas patrimoniales del ejercicio. Los saldos anteriores son
    los pendientes de los cuatro ejercicios previos.
    """
    _validar_anteriores(rendimientos_negativos_anteriores, ejercicio)
    _validar_anteriores(perdidas_patrimoniales_anteriores, ejercicio)

    rendimientos_pendientes = {p.ejercicio: p.importe for p in rendimientos_negativos_anteriores}
    perdidas_pendientes = {p.ejercicio: p.importe for p in perdidas_patrimoniales_anteriores}
    if saldo_rendimientos < 0:
        rendimientos_pendientes[ejercicio] = -saldo_rendimientos
    if saldo_ganancias_perdidas < 0:
        perdidas_pendientes[ejercicio] = -saldo_ganancias_perdidas

    rendimientos = max(saldo_rendimientos, CERO)
    ganancias = max(saldo_ganancias_perdidas, CERO)
    # Límite conjunto del 25 % para la compensación cruzada (pasos 1 y 3).
    cupo_sobre_rendimientos = rendimientos * normativa.LIMITE_COMPENSACION_CRUZADA
    cupo_sobre_ganancias = ganancias * normativa.LIMITE_COMPENSACION_CRUZADA

    # VERIFICAR: se compensan primero los ejercicios más antiguos. Es el orden que sigue el
    # caso práctico de la AEAT, pero el Manual no lo dice expresamente.
    anteriores = list(range(ejercicio - normativa.EJERCICIOS_ARRASTRE_SALDOS_NEGATIVOS, ejercicio))

    # Paso 1: saldos negativos del ejercicio contra el otro bloque (art. 49.1.a y b).
    compensado = _compensar(perdidas_pendientes, [ejercicio], min(rendimientos, cupo_sobre_rendimientos))
    rendimientos -= compensado
    cupo_sobre_rendimientos -= compensado
    compensado = _compensar(rendimientos_pendientes, [ejercicio], min(ganancias, cupo_sobre_ganancias))
    ganancias -= compensado
    cupo_sobre_ganancias -= compensado

    # Paso 2: saldos de ejercicios anteriores contra su mismo bloque, sin límite.
    ganancias -= _compensar(perdidas_pendientes, anteriores, ganancias)
    rendimientos -= _compensar(rendimientos_pendientes, anteriores, rendimientos)

    # Paso 3: lo que quede de ejercicios anteriores contra el otro bloque, con el cupo restante.
    rendimientos -= _compensar(perdidas_pendientes, anteriores, min(rendimientos, cupo_sobre_rendimientos))
    ganancias -= _compensar(rendimientos_pendientes, anteriores, min(ganancias, cupo_sobre_ganancias))

    rendimientos_vivos, rendimientos_caducados = _arrastrar(rendimientos_pendientes, ejercicio)
    perdidas_vivas, perdidas_caducadas = _arrastrar(perdidas_pendientes, ejercicio)
    return ResultadoCompensacion(
        base_ahorro=rendimientos + ganancias,
        rendimientos_negativos_pendientes=rendimientos_vivos,
        perdidas_patrimoniales_pendientes=perdidas_vivas,
        rendimientos_negativos_caducados=rendimientos_caducados,
        perdidas_patrimoniales_caducadas=perdidas_caducadas,
    )


def _compensar(pendientes: dict[int, Decimal], ejercicios: Iterable[int], disponible: Decimal) -> Decimal:
    """Compensa los saldos de `ejercicios`, en ese orden, hasta agotar `disponible`.

    Reduce los importes de `pendientes` y devuelve el total compensado.
    """
    total = CERO
    for ejercicio in ejercicios:
        if ejercicio not in pendientes:
            continue
        compensado = min(pendientes[ejercicio], disponible - total)
        pendientes[ejercicio] -= compensado
        total += compensado
    return total


def _arrastrar(pendientes: dict[int, Decimal], ejercicio: int) -> tuple[tuple[SaldoPendiente, ...], Decimal]:
    """Separa lo que se arrastra a ejercicios siguientes de lo que caduca este año."""
    ultimo_ejercicio_que_caduca = ejercicio - normativa.EJERCICIOS_ARRASTRE_SALDOS_NEGATIVOS
    vivos = tuple(
        SaldoPendiente(ejercicio_origen, importe)
        for ejercicio_origen, importe in sorted(pendientes.items())
        if importe > 0 and ejercicio_origen > ultimo_ejercicio_que_caduca
    )
    return vivos, pendientes.get(ultimo_ejercicio_que_caduca, CERO)


def _validar_anteriores(anteriores: Sequence[SaldoPendiente], ejercicio: int) -> None:
    primero = ejercicio - normativa.EJERCICIOS_ARRASTRE_SALDOS_NEGATIVOS
    ejercicios = [saldo.ejercicio for saldo in anteriores]
    if len(ejercicios) != len(set(ejercicios)):
        raise ValueError("Hay más de un saldo pendiente para el mismo ejercicio.")
    for saldo in anteriores:
        if not primero <= saldo.ejercicio < ejercicio:
            raise ValueError(
                f"En {ejercicio} solo se compensan saldos de {primero} a {ejercicio - 1}; "
                f"se ha indicado uno de {saldo.ejercicio}."
            )
        if saldo.importe <= 0:
            raise ValueError("El saldo pendiente debe indicarse en positivo.")
