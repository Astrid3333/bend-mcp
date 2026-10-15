# Errores comunes de bend / bend-mcp y cómo recuperarse

Tabla complementaria de `../SKILL.md` (reglas duras numeradas del skill).

| Mensaje / síntoma | Acción |
|---|---|
| `No se encontró el binario 'bend'` | Pedir instalar Bend (`cargo install bend-lang`) o ajustar `BEND_MCP_BEND_BIN`. |
| `syntax_warning` en `bend_check_install` | El binario no es 0.2.x: avisar al usuario y validar todo con `bend_check` antes de correr. |
| `El archivo ya existe. Pasa overwrite=true si quieres reemplazarlo.` (texto literal del servidor) | Reintentar con `overwrite=true` solo si el usuario quiere reemplazar. |
| `No existe X en el workspace` | Llamar `bend_list_programs` y reescribir con `bend_write_program`. |
| `[bend-mcp] Timeout tras Ns` | Programa posiblemente no paralelizable o demasiado grande: bajar el input o subir `timeout`. |
| `expected: ...` / errores de parse | La sintaxis no coincide con Bend 0.2.x. Muchos ejemplos de internet son de otra versión. |
| `Redefinition of builtin (type) 'X'` | Renombrar el tipo (regla dura 7 del skill). |
| `Unbound variable 'a.b'` | Acceso encadenado de campos: usar match anidado (regla dura 8). |
| `Unbound variable 'fork'` | `fork` fuera de `when`/`bend`: quitarlo, la recursión ya se paraleliza sola. |
| `Type Error: Expected function type ... main` | Params de `main` anotados con tipos: quitar anotaciones si se usan args de CLI. |
| `io_skipped` en el resultado | Normal: el flag `--io` no existe en esta versión; la IO corre igual en mode="c". |
| `mode_fallback` / `target_fallback` | No hay `nvcc`: el servidor cayó de `cu` a `c`. Informarlo al usuario. |
