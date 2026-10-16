"""Reglas fiscales del simulador: IRPF, territorio común, ejercicio 2026.

Es la única fuente de datos normativos del proyecto. Cada constante indica su
artículo y su fuente. Resumen razonado en
.claude/skills/normativa-fiscal/reference.md y enlaces en docs/fuentes.md.
"""

from datetime import date
from decimal import Decimal
from typing import NamedTuple

EJERCICIO = 2026


class Tramo(NamedTuple):
    """Tramo de una escala progresiva. `hasta=None` indica el último tramo, sin límite."""

    hasta: Decimal | None
    tipo: Decimal


# Arts. 66 y 76 LIRPF. Escala del ahorro (estatal + autonómica), vigente 2025-2026
# (redacción de la Ley 7/2024, efectos 1-1-2025). Cada mitad: 9,5 / 10,5 / 11,5 / 13,5 / 15 %.
# Fuente: BOE, texto consolidado LIRPF. Verificado: 2026-10-16.
# VERIFICAR: contrastar con el Manual práctico de Renta 2026 cuando se publique.
ESCALA_AHORRO_2026 = (
    Tramo(Decimal("6000"), Decimal("0.19")),
    Tramo(Decimal("50000"), Decimal("0.21")),
    Tramo(Decimal("200000"), Decimal("0.23")),
    Tramo(Decimal("300000"), Decimal("0.27")),
    Tramo(None, Decimal("0.30")),
)

# Art. 101.6 LIRPF; art. 96 RIRPF (porcentaje) y art. 97.1 RIRPF (base: la ganancia).
# Retención en el reembolso de participaciones de IIC. Es pago a cuenta, no cuota final.
# Fuente: BOE, textos consolidados LIRPF y RIRPF. Verificado: 2026-10-16.
TIPO_RETENCION_REEMBOLSO_FONDO = Decimal("0.19")

# Art. 75.3.j RIRPF (RD 249/2023). La venta de ETF españoles y extranjeros análogos no
# lleva retención, salvo que se haga en un mercado de una jurisdicción no cooperativa.
# Fuente: BOE, texto consolidado RIRPF. Verificado: 2026-10-16.
TIPO_RETENCION_VENTA_ETF = Decimal("0")

# Art. 49.1.a y b LIRPF. Compensación cruzada entre el saldo de rendimientos del capital
# mobiliario y el de ganancias y pérdidas patrimoniales: límite del 25 % del saldo positivo.
# Fuente: BOE, texto consolidado LIRPF. Verificado: 2026-10-16.
LIMITE_COMPENSACION_CRUZADA = Decimal("0.25")

# Art. 49.1 LIRPF. Los saldos negativos no compensados se arrastran a los cuatro años siguientes.
# Fuente: BOE, texto consolidado LIRPF. Verificado: 2026-10-16.
EJERCICIOS_ARRASTRE_SALDOS_NEGATIVOS = 4

# Art. 94.2.a LIRPF (redacción de la Ley 11/2021). Los ETF extranjeros quedan excluidos del
# régimen de traspaso desde esta fecha. Solo se usa para avisos.
# VERIFICAR: alcance exacto del régimen transitorio (adquisiciones anteriores) antes de modelizarlo.
# Fuente: reference.md, sección 3.
FECHA_EXCLUSION_TRASPASO_ETF_EXTRANJEROS = date(2022, 1, 1)

# Art. 33.5.f y g LIRPF. Regla de recompra: plazo (antes o después de la venta con pérdida)
# en el que la recompra de valores homogéneos impide computar la pérdida. Solo se usa para avisos.
# VERIFICAR: plazo aplicable a participaciones de fondos no cotizados (consultas de la DGT).
# Fuente: reference.md, sección 5.
PLAZO_RECOMPRA_MESES_MERCADO_REGULADO = 2
PLAZO_RECOMPRA_MESES_OTROS = 12
