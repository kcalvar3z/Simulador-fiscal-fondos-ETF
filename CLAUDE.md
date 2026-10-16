# Simulador fiscal: vender un fondo vs. vender un ETF (España)

## Qué es este proyecto

Herramienta divulgativa que calcula y compara el coste fiscal en el IRPF (España, territorio común) de deshacer una inversión en tres escenarios:

1. **Fondo de inversión – reembolso** (vender y pasar a liquidez).
2. **Fondo de inversión – traspaso** a otro fondo (por ejemplo, un monetario): la ganancia se difiere.
3. **ETF – venta**: no admite traspaso; la ganancia tributa siempre en el ejercicio.

Objetivo: que cualquier inversor entienda, con números, qué implica fiscalmente vender en un momento de incertidumbre, y generar contenido (gráficos y textos) para publicaciones en LinkedIn. Es también un proyecto de portfolio del autor (estudiante de Derecho + ADE orientado a fiscalidad patrimonial), así que el código debe ser limpio, testeado y legible por un reclutador.

**No es asesoramiento fiscal.** Toda salida visible para el usuario incluye el aviso: *"Cálculo orientativo con fines divulgativos. No constituye asesoramiento fiscal ni financiero."*

## Sobre el autor (cómo trabajar conmigo)

- Explícame en español y brevemente qué cambias y por qué. Estoy aprendiendo: si una decisión técnica no es obvia, justifícala en una o dos frases.
- Domino la parte fiscal mejor que la técnica: si una regla fiscal te parece dudosa, pregúntame o márcala como `# VERIFICAR` en lugar de suponer.
- Antes de cambios grandes (nueva dependencia, reestructurar carpetas, cambiar la lógica de cálculo), propón un plan corto y espera mi visto bueno.

## Stack

- Python 3.11+
- `decimal.Decimal` para todo importe monetario (nunca `float`). Redondeo a céntimos con `ROUND_HALF_UP` solo al presentar la cuota final.
- `pytest` para tests.
- `streamlit` para la interfaz web.
- `plotly` para gráficos interactivos y exportación PNG (vía `kaleido`) para LinkedIn.
- Sin bases de datos ni APIs externas: todos los datos fiscales viven en `simulador/normativa.py`.

## Estructura prevista

```
simulador/
  normativa.py       # Constantes fiscales con su fuente (escala del ahorro, retenciones, plazos…)
  lotes.py           # Compras por lotes y asignación FIFO
  calculo.py         # Ganancia patrimonial, cuota por tramos, retención
  escenarios.py      # Reembolso fondo / traspaso fondo / venta ETF
  compensacion.py    # Compensación de pérdidas (art. 49 LIRPF)
  graficos.py        # Gráficos para la app y para LinkedIn
app.py               # Interfaz Streamlit
tests/               # pytest; un fichero por módulo + casos de referencia
contenido/           # Borradores de posts y gráficos exportados
docs/fuentes.md      # Normativa y fuentes consultadas
```

## Comandos

```bash
pip install -r requirements.txt
pytest -q                      # tests
streamlit run app.py           # app en local
python -m simulador.graficos   # regenerar gráficos de contenido/
```

## Reglas del proyecto (obligatorias)

1. **Nunca inventes normativa.** Tipos, tramos, plazos y porcentajes se toman de `simulador/normativa.py`, y cada constante lleva comentario con artículo y fuente. Si hay que añadir o cambiar una regla, usa la skill `normativa-fiscal`.
2. **Todo cálculo nuevo lleva test** con un caso resuelto a mano (ver skill `calculo-plusvalias`).
3. **Nombres de dominio en español** (`ganancia_patrimonial`, `valor_adquisicion`, `cuota_ahorro`); código genérico puede ir en inglés.
4. **Funciones puras** en `simulador/`: sin `print`, sin estado global, sin lectura de ficheros. La app y los gráficos solo llaman a esas funciones.
5. **Alcance**: IRPF de residentes en territorio común, ejercicio 2026. Fuera de alcance (avisar si se pide): País Vasco y Navarra, no residentes, Impuesto sobre el Patrimonio, personas jurídicas.
6. **Contenido para LinkedIn**: usa la skill `post-linkedin`. Nunca recomendar comprar o vender; explicar implicaciones.
7. Antes de dar por terminada una tarea importante o publicar, ejecuta `/revisar`.

## Git

- Rama `main` siempre estable; trabajo en ramas `feat/…`, `fix/…`, `docs/…`.
- Mensajes de commit en español, en imperativo: `Añade cálculo FIFO por lotes`.
- No subir datos personales ni capturas de cuentas reales de broker.
