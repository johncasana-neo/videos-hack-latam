---
name: radiografia
description: Genera el video diario de Radiografia del Gasto Publico leyendo el insight JSON mas reciente, seleccionando la plantilla HTML segun el patron detectado, llenando los placeholders Jinja2 con datos reales, y validando el resultado antes de renderizar con HyperFrames
---

# Radiografia del Gasto Publico

Usa este skill cuando el usuario pida procesar el insight diario de la serie "Radiografia del Gasto Publico" de Agente P.

## Flujo obligatorio

1. Leer el insight mas reciente dentro de `insights/` con nombre `insight_YYYY_MM_DD.json`.
2. Validar que existan los campos criticos:
   - `case.caso_titulo`
   - `case.patron_detectado`
   - `case.confidence`
   - `source.entidad_nombre`
   - `source.codigo_seace`
   - `source.fuente_oficial`
   - `script.voiceover_text_full`
   - `output.width`, `output.height`, `output.fps`
3. Abortarlo si `case.confidence < 0.8` o si falta cualquier campo critico.
4. Mapear `case.patron_detectado` a plantilla:
   - `postor_unico_con_proceso_acelerado` -> `templates/postor_unico.html`
   - `proveedor_recurrente` -> `templates/proveedor_recurrente.html`
   - `fraccionamiento_contractual` -> `templates/fraccionamiento.html`
   - `funcionario_sancionado_activo` -> `templates/funcionario_sancionado.html`
   - default -> `templates/postor_unico.html`
5. Copiar la plantilla elegida a `index.html` y reemplazar todos los placeholders `{{ variable }}` con datos del insight.
6. Formatear montos como `S/ X,XXX,XXX`.
7. Censurar RUCs con el formato `20••••••XXX`, conservando solo los ultimos 3 digitos.
8. Ajustar los timings de segmentos usando la duracion real del audio recibida en el prompt. Si no viene, usar `20`.
9. Ejecutar `npx hyperframes lint index.html`.
10. Si el lint falla por errores corregibles, autocorregir y reintentar hasta 2 veces.
11. Imprimir un JSON final:

```json
{
  "status": "ok",
  "video_path": "output/radiografia-YYYY_MM_DD.mp4",
  "case_title": "Titulo del caso",
  "entity_name": "Entidad",
  "episode": "01/30"
}
```

## Variables esperadas por las plantillas

- `episode_label`
- `caso_titulo`
- `entidad_nombre`
- `entidad_sigla`
- `entidad_ruc_censurado`
- `monto_adjudicado_formato`
- `objeto_contrato`
- `numero_postores`
- `dias_proceso`
- `promedio_sector`
- `fuente_oficial`
- `audio_duration`
- `codigo_seace`
- `funcionario_dni_ultimos`
- `sancion_fecha`
- `firma_fecha`

## Reglas estrictas

- Nunca publicar nombres propios sin censura si no hay sentencia firme.
- Siempre incluir el disclaimer `Datos publicos · Fuente: [fuente]` en el frame final.
- Si `confidence < 0.8` o falta algun campo critico, abortar y reportar `status: "aborted"`.
- No inventar datos. Si falta un dato no critico, usar una etiqueta neutra como `No reportado`.
- No exponer RUCs completos, DNI completos, telefonos, correos personales ni direcciones personales.
- El resultado debe ser 1080x1920, 30 fps y duracion final entre 18 y 22 segundos.
