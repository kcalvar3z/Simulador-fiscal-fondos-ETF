# Reglas vigentes (IRPF, territorio común, ejercicio 2026)

> Última revisión: 16-10-2026. Revisar al inicio de cada año y cuando se publique el Manual de Renta.

## 1. Escala de la base liquidable del ahorro

Tipo total (estatal + autonómico). La parte autonómica de esta escala no varía entre comunidades de régimen común.

| Base liquidable del ahorro | Tipo |
|---|---|
| 0 – 6.000 € | 19 % |
| 6.000 – 50.000 € | 21 % |
| 50.000 – 200.000 € | 23 % |
| 200.000 – 300.000 € | 27 % |
| Más de 300.000 € | 30 % |

Aplica igual en 2025 y 2026. Fuente: arts. 66 y 76 LIRPF; resumen en BBVA Mi Jubilación (escalas de gravamen). `# VERIFICAR` contra el Manual de Renta 2026 cuando se publique.

## 2. Cálculo de la ganancia patrimonial

- Ganancia = valor de transmisión − valor de adquisición (art. 34 LIRPF).
- El valor de adquisición incluye gastos y tributos inherentes a la compra; al de transmisión se le restan los de la venta (art. 35 LIRPF). Las comisiones de compraventa cuentan.
- **FIFO**: se consideran vendidas primero las participaciones o valores adquiridos antes (art. 94.1.a LIRPF para IIC; art. 37.2 para valores admitidos a negociación).
- Clases distintas (acumulación/distribución, divisa) tienen ISIN distinto y colas FIFO separadas.

## 3. Traspasos entre fondos

- **Fondos de inversión (no cotizados)**: el traspaso no tributa; la ganancia se difiere y las nuevas participaciones conservan el valor y la fecha de adquisición de las originales (art. 94.1.a LIRPF). Es diferimiento, no exención.
- **ETF españoles**: excluidos del régimen de traspaso (último párrafo del art. 94.1.a LIRPF).
- **ETF extranjeros**: excluidos desde el 1-1-2022, cualquiera que sea el mercado en que coticen (art. 94.2.a LIRPF, redacción de la Ley 11/2021).
- **Régimen transitorio**: ETF extranjeros adquiridos antes del 1-1-2022 que no coticen en bolsa española pueden traspasarse a un fondo no cotizado, pero no a otro ETF. `# VERIFICAR` alcance exacto en la disposición transitoria antes de modelizarlo; de inicio, el simulador lo menciona como aviso, no lo calcula.

## 4. Retenciones

- **Reembolso de fondos**: retención del 19 % sobre la ganancia (art. 101 LIRPF y RIRPF). Es pago a cuenta.
- **Venta de ETF** (españoles y, desde el 25-4-2023, extranjeros análogos): sin retención (art. 75.3.j RIRPF, añadido por el RD 249/2023), salvo jurisdicciones no cooperativas.
- **Dividendos de ETF de distribución**: rendimiento del capital mobiliario (art. 25.1.a LIRPF), base del ahorro; retención del 19 % si paga una entidad española. Fuera del alcance inicial.

## 5. Regla de recompra (antiaplicación de pérdidas, art. 33.5 LIRPF)

- No se computa una pérdida si se adquieren valores homogéneos:
  - **dos meses** antes o después, si cotizan en mercados regulados de la UE (letra f);
  - **un año** antes o después, en otro caso (letra g).
- La pérdida no se pierde: se integra cuando se transmiten los valores que quedan en cartera.
- Dos ETF de gestoras distintas sobre el mismo índice **no** son homogéneos entre sí.
- `# VERIFICAR` con consultas de la DGT el plazo aplicable a participaciones de fondos no cotizados antes de calcularlo; de inicio, el simulador solo avisa.

## 6. Compensación de pérdidas (art. 49 LIRPF)

- Ganancias y pérdidas patrimoniales se compensan primero entre sí.
- Si el saldo es negativo, se compensa con el saldo positivo de rendimientos del capital mobiliario del mismo año, con un **límite del 25 %** de ese saldo.
- Lo que sobre se arrastra a los **cuatro ejercicios siguientes**, en el mismo orden.
- La compensación debe hacerse por la cuantía máxima posible cada año.

## Fuentes

- BOE – Ley 35/2006 del IRPF (texto consolidado) y RD 439/2007.
- Agencia Tributaria – Manual práctico de Renta 2025, base imponible del ahorro.
- Guía Fiscal – Fiscalidad de los ETF en 2026.
- Cuatrecasas – ETF extranjeros: exclusión de retención (abril 2023).
- BBVA Mi Jubilación – Escalas de gravamen del IRPF.
