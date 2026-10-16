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

Aplica igual en 2025 y 2026. Fuente: arts. 66 y 76 LIRPF; resumen en BBVA Mi Jubilación (escalas de gravamen). Comprobado en el texto consolidado del BOE el 16-10-2026: cada escala (estatal y autonómica) es 9,5 / 10,5 / 11,5 / 13,5 / 15 %, redacción de la Ley 7/2024 con efectos desde el 1-1-2025. `# VERIFICAR` contra el Manual de Renta 2026 cuando se publique.

## 2. Cálculo de la ganancia patrimonial

- Ganancia = valor de transmisión − valor de adquisición (art. 34 LIRPF).
- El valor de adquisición incluye gastos y tributos inherentes a la compra; al de transmisión se le restan los de la venta (art. 35 LIRPF). Las comisiones de compraventa cuentan.
- **FIFO**: se consideran vendidas primero las participaciones o valores adquiridos antes (art. 94.1.a LIRPF para IIC; art. 37.2 para valores admitidos a negociación).
- Las distintas clases de un mismo fondo (ISIN distinto) no son valores homogéneos a efectos del art. 8 RIRPF, al menos cuando difieren en la comisión de gestión, porque afecta al valor liquidativo y a la rentabilidad (DGT V0796-26, de 9-4-2026). El FIFO se aplica por separado a cada clase. Tampoco son homogéneos fondos de gestoras distintas que replican el mismo índice, por ser distinto el emisor. # VERIFICAR: clases que solo difieren en divisa o en política de distribución (la consulta no lo trata expresamente).

## 3. Traspasos entre fondos

- **Fondos de inversión (no cotizados)**: el traspaso no tributa; la ganancia se difiere y las nuevas participaciones conservan el valor y la fecha de adquisición de las originales (art. 94.1.a LIRPF). Es diferimiento, no exención.
- **ETF españoles**: excluidos del régimen de traspaso (último párrafo del art. 94.1.a LIRPF).
- **ETF extranjeros**: excluidos desde el 1-1-2022, cualquiera que sea el mercado en que coticen (art. 94.2.a LIRPF, redacción de la Ley 11/2021).
- **Régimen transitorio**: ETF extranjeros adquiridos antes del 1-1-2022 que no coticen en bolsa española pueden traspasarse a un fondo no cotizado, pero no a otro ETF. `# VERIFICAR` alcance exacto en la disposición transitoria antes de modelizarlo; de inicio, el simulador lo menciona como aviso, no lo calcula.

## 4. Retenciones

- **Reembolso de fondos**: retención del 19 % sobre la ganancia (art. 101.6 LIRPF; art. 96 RIRPF fija el porcentaje y art. 97.1 RIRPF, la base: la ganancia a integrar). Es pago a cuenta.
- **Traspaso de fondos**: sin retención, porque no se computa la ganancia (art. 101.6, párrafo segundo, LIRPF).
- Si el partícipe tiene participaciones homogéneas en varias entidades, la base de retención se calcula con el registro de la entidad que reembolsa (art. 97.2 RIRPF) y puede no coincidir con la ganancia fiscal; la cuota final no cambia. El simulador supone una sola entidad.
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

- Rendimientos del capital mobiliario (RCM) por un lado, y ganancias y pérdidas patrimoniales por otro, se integran y compensan primero **exclusivamente entre sí**.
- Si el saldo de ganancias y pérdidas es negativo, se compensa con el saldo positivo de RCM del mismo año, con un **límite del 25 %** de ese saldo (art. 49.1.b).
- La compensación funciona igual en sentido inverso: un saldo negativo de RCM se compensa con el saldo positivo de ganancias y pérdidas, con el mismo límite del 25 % (art. 49.1.a).
- Lo que sobre se arrastra a los **cuatro ejercicios siguientes**, en el mismo orden.
- La compensación debe hacerse por la cuantía máxima posible cada año (art. 49.2).
- **Orden con saldos de ejercicios anteriores** (AEAT, Manual práctico de Renta 2025, cap. 12, y su caso práctico):
  1. Saldos del propio ejercicio, compensación cruzada con el límite del 25 %.
  2. Saldos pendientes de los cuatro ejercicios anteriores, con el saldo positivo de su **mismo** bloque, **sin límite**.
  3. Lo que quede, con el saldo positivo restante del otro bloque. El **límite del 25 % es conjunto** con el del paso 1 (no hay un 25 % para el año y otro para el arrastre) y se calcula sobre el saldo positivo del ejercicio antes de compensaciones.
- Lo no compensado en el cuarto año caduca.
- **Criterio adoptado**: se compensan primero los saldos pendientes más antiguos. La norma no fija orden entre ejercicios; es el criterio que aplica el caso práctico del Manual de Renta 2025 (AEAT, cap. 12) y el más favorable al contribuyente, porque, al ser obligatorio compensar el máximo posible, minimiza los saldos que caducan a los cuatro años.

## 7. Supuestos del simulador

- **Mínimo personal y familiar**: se parte de un contribuyente con un salario estándar (medio o más frecuente), cuya base general absorbe íntegramente el mínimo personal y familiar. Por eso no minora la cuota del ahorro (art. 66.1.2.º LIRPF). Para rentas del trabajo muy bajas el cálculo sobrestimaría la cuota.
- **Una sola entidad comercializadora** por producto (ver sección 4, art. 97.2 RIRPF).

## Fuentes

- BOE – Ley 35/2006 del IRPF (texto consolidado) y RD 439/2007.
- Agencia Tributaria – Manual práctico de Renta 2025, base imponible del ahorro; cap. 12, integración y compensación de rentas, y su caso práctico.
- Guía Fiscal – Fiscalidad de los ETF en 2026.
- Cuatrecasas – ETF extranjeros: exclusión de retención (abril 2023).
- DGT – Consulta vinculante V0796-26, de 9-4-2026 (homogeneidad de clases de un mismo fondo).
- BBVA Mi Jubilación – Escalas de gravamen del IRPF.
