---
name: revisar
description: Revisión completa antes de cerrar una tarea importante, hacer merge a main o publicar contenido. Ejecutar solo cuando el usuario escriba /revisar.
disable-model-invocation: true
allowed-tools: Bash(pytest *) Bash(git status) Bash(git diff *)
---

# Revisión antes de publicar o hacer merge

Ejecuta esta lista en orden y entrega un informe breve con ✅ / ❌ por punto. Si algo falla, explica qué y propón la corrección; no la apliques sin confirmación.

1. **Tests**: `pytest -q` pasa entero. Ningún test marcado como `skip` sin motivo.
2. **Normativa**: toda constante nueva o modificada en `simulador/normativa.py` tiene artículo, fuente y fecha de verificación. Lista las marcadas con `# VERIFICAR`.
3. **Cálculo**: para cada función de cálculo cambiada, reproduce a mano un caso de `.claude/skills/calculo-plusvalias/examples.md` y compáralo con la salida del código.
4. **Dinero**: no hay `float` en importes (`grep -rn "float(" simulador/`).
5. **Avisos**: la app y cada pieza de `contenido/` incluyen el aviso de "no constituye asesoramiento fiscal".
6. **Contenido** (si hay post): las cifras del texto coinciden con las del gráfico y con el simulador; no hay recomendaciones de compra o venta.
7. **Repositorio**: `git status` limpio de ficheros temporales; sin datos personales; el README refleja el estado actual.
8. **Resumen final**: qué está listo, qué queda pendiente y qué decisiones necesitan al autor.
