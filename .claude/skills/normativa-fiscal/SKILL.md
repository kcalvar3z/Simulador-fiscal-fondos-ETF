---
name: normativa-fiscal
description: Añadir, verificar o actualizar cualquier regla fiscal del simulador (tipos y tramos de la base del ahorro, retenciones, traspasos, regla de recompra, compensación de pérdidas). Úsala siempre que se toque simulador/normativa.py o se pregunte si una regla está vigente.
---

# Normativa fiscal del simulador

Las reglas vigentes que usa el proyecto, con su fuente, están en [reference.md](reference.md). Léelo antes de tocar cualquier constante.

## Procedimiento para añadir o cambiar una regla

1. **Identifica la norma exacta**: ley y artículo (p. ej. art. 94.1.a LIRPF), o reglamento (RIRPF).
2. **Busca la fuente en este orden de preferencia**:
   1. BOE (texto consolidado de la Ley 35/2006 del IRPF y del RD 439/2007, Reglamento).
   2. Agencia Tributaria: Manual práctico de Renta del ejercicio correspondiente.
   3. Consultas vinculantes de la DGT (buscador PETETE) para casos dudosos.
   4. Solo como apoyo: guías de despachos o portales especializados. Nunca como única fuente.
3. **Comprueba la vigencia** para el ejercicio que simula el proyecto (2026). Si la norma cambió recientemente, anota desde cuándo aplica.
4. **Escribe la constante** en `simulador/normativa.py` con un comentario en este formato:
   ```python
   # Art. 66 y 76 LIRPF. Escala del ahorro (estatal + autonómica), vigente 2025-2026.
   # Fuente: AEAT, Manual Renta 2025. Verificado: AAAA-MM-DD.
   ESCALA_AHORRO_2026 = [...]
   ```
5. **Actualiza [reference.md](reference.md)** y `docs/fuentes.md` con el enlace.
6. **Añade o ajusta un test** que dependa de la regla, para que un cambio futuro rompa algo visible.
7. Si no encuentras confirmación clara, **no supongas**: deja la regla marcada con `# VERIFICAR:` y explica la duda al usuario.

## Errores típicos que hay que evitar

- Aplicar el tipo del último tramo a toda la base: la escala es progresiva, cada tramo tributa a su tipo.
- Confundir retención (pago a cuenta) con cuota final: la retención se descuenta en la Renta, no es el impuesto definitivo.
- Tratar el traspaso como exención: es un **diferimiento**; la ganancia aflora al reembolsar.
- Suponer que los ETF extranjeros se pueden traspasar: desde el 1-1-2022 no (salvo régimen transitorio, ver reference.md).
