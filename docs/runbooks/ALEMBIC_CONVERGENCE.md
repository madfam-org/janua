# Convergencia de `alembic_version` (Janua API)

> **Audiencia:** operadores, SRE, release engineers
> **Estado medido:** 2026-09-03, producción
> **Regla corta:** *promote* NO ejecuta migraciones. Toda migración aplicada a mano se sella (`stamp`) inmediatamente después.

---

## 1. El estado actual y por qué importa

Producción registra:

```
alembic_version.version_num = 011_invitation_columns
```

Y sin embargo el esquema ya contiene todo lo que crean las revisiones 012, 013,
015 y 016 — cada una aplicada **a mano** — y 014 (`capability_links`), aplicada
por el bootstrap del operador mediante SQL generado, **deliberadamente sin tocar
`alembic_version`**.

Esto no es un descuido de nadie. `promote-to-prod.yml` es un cambio de puntero
de imagen y no ejecuta migraciones: es el diseño (RFC 0001, patrón B). La
consecuencia es que lo único que escribe la tabla de versión nunca se ejecuta,
así que la fila quedó congelada en 011 mientras el esquema siguió avanzando.

**Por qué es peligroso y no solo desprolijo.** Esa fila es la *única* entrada
que usa alembic para decidir qué hacer a continuación. Leída tal cual, dice que
012 en adelante no ocurrieron, así que `alembic upgrade head` intentaría
reproducir las cinco. Hoy eso no rompe nada porque las migraciones 012–016 son
reentrantes a propósito (cada una consulta `inspect()` antes de crear) — pero
esa garantía es una propiedad de cinco archivos concretos, no del repositorio.
El propio docstring de 014 registra el modo de falla que está evitando:
`DuplicateTable` aborta la transacción **completa** y deja la base clavada en la
revisión padre. En cuanto alguien escriba una migración sin ese guardia, la fila
obsoleta convierte un `upgrade` rutinario en una caída — y Janua es el piso de
autenticación del ecosistema: se lleva puestos todos los logins río abajo.

Converger es quitar esa arma cargada de la mesa.

| | Revisión | Objetos que crea |
|---|---|---|
| 012 | `012_user_spanish_formality` | columna `users.spanish_formality` |
| 013 | `013_per_tenant_email_uniqueness` | índices `uq_users_tenant_email`, `uq_users_email_global` |
| 014 | `014_capability_links` | tabla `capability_links` + `uq_capability_links_token_hash`, `ix_capability_links_tenant_id`, `ix_capability_links_tenant_subject` |
| 015 | `015_user_is_service_acct` | columna `users.is_service_account` |
| 016 | `016_org_member_app_roles` | tabla `organization_member_app_roles` + `ix_org_member_app_roles_member`, `uq_org_member_app_roles_live` |

013 además **elimina** `ix_users_email` al final. Esa eliminación NO se exige
para sellar: los entornos construidos con `Base.metadata.create_all` conservan
el índice viejo junto a los nuevos, y exigirlo bloquearía justo los entornos que
este procedimiento existe para converger. El script lo reporta como nota.

---

## 2. Verificar (solo lectura, seguro en producción)

`scripts/alembic_converge.py` inspecciona el esquema, contrasta cada revisión
contra los objetos que debería haber creado, e imprime la tabla
`revision | objeto esperado | ¿presente?`.

Desde el pod de la API — el único lugar que alcanza la base:

```bash
kubectl -n janua exec deploy/janua-api -- python scripts/alembic_converge.py --check
```

Sin flags hace lo mismo: **el modo lectura es el predeterminado.** No escribe
nada, no ejecuta DDL, y la URL de la base se lee del entorno
(`DIRECT_DATABASE_URL`, si no `DATABASE_URL` — la misma precedencia que
`alembic/env.py`) y **nunca se imprime**: los diagnósticos nombran host y base,
nada más. La salida se puede pegar en un ticket.

Salida esperada hoy (resumida):

```
Base de datos: <host>:5432/janua
alembic_version registrado: 011_invitation_columns

revision                         objeto esperado                                    ¿presente?
-------------------------------  -------------------------------------------------  ----------
012_user_spanish_formality       column users.spanish_formality                     sí
                                   -> PRESENTE
...
Revisiones presentes pero NO registradas (5): 012_..., 013_..., 014_..., 015_..., 016_...
```

### Códigos de salida

| Código | Significado |
|---|---|
| 0 | Convergente, o nada que sellar |
| 1 | **PARCIAL** — alguna revisión está a medias. No se cambió nada |
| 2 | Hay revisiones aplicadas sin registrar (desvío) — solo en `--check` |
| 3 | Error de conexión, de inspección, o un `stamp` que falló |

### Si sale PARCIAL

Una revisión a medias (creó tres objetos, hay dos) es un estado que **ninguna
migración produce**. El script se niega a hacer absolutamente nada y sale con 1,
a propósito:

- Sellarla registraría una mentira y ocultaría el objeto faltante para siempre
  — alembic no vuelve a visitar una revisión ya registrada.
- Aplicarla con `upgrade` es justamente lo que este script no hace.

Ambas direcciones están mal. **Escalá a un humano**: hay que averiguar qué pasó
con ese objeto antes de tocar nada.

---

## 3. Sellar (`--stamp`)

Solo después de que `--check` muestre PRESENTE en todo lo que se va a sellar.

```bash
kubectl -n janua exec -it deploy/janua-api -- python scripts/alembic_converge.py --stamp
```

Pide confirmación interactiva (`si`) cuando hay TTY; con `-it` la hay. En un job
o pipeline sin TTY agregá `--yes`.

**Qué hace exactamente.** Ejecuta `alembic stamp <rev>` una revisión a la vez,
desde la que sigue a la registrada hasta la más alta que esté *completa* —
`012` → `013` → `014` → `015` → `016`. Nunca `upgrade`: `stamp` escribe una fila
y no toca ningún otro objeto. Le dice a alembic «esta revisión ya es cierta»,
que es exactamente el hecho que acabamos de verificar mirando el esquema.

**Por qué paso a paso y no un salto al objetivo.** Si algo falla a mitad de
camino, `alembic_version` queda en la última revisión sellada con éxito — que
sigue siendo cierta. Un salto único fallido no deja ese margen.

**Prefijo, no máximo.** Un hueco detiene la caminata aunque una revisión
posterior esté completa: sellar 016 afirma que 012–015 también son ciertas,
porque alembic guarda una sola versión e infiere el resto de la cadena. Si falta
014 y están 015 y 016, el script sella hasta 013 y se detiene. Correcto.

Verificación posterior:

```bash
kubectl -n janua exec deploy/janua-api -- python -m alembic current
kubectl -n janua exec deploy/janua-api -- python scripts/alembic_converge.py --check   # → 0, "Convergente"
```

### Después de sellar: actualizar el ledger

`apps/api/alembic/PROD_ALEMBIC_STATE.json` es lo que lee el guardia de promote
(sección 4). Actualizá `recorded_revision`, `verified_at` y `verified_by` **con
lo que el script acaba de reportar**, y abrí un PR. El orden importa: primero se
lee la base, después se edita el archivo. Editarlo «hacia adelante» sin haber
corrido `--check` no acelera nada: anula el guardia.

---

## 4. El guardia de promote

`promote-to-prod.yml` tiene un job `migrations-guard` que corre antes de
`validate`.

**No consulta la base de datos, y no puede.** Corre en un runner alojado por
GitHub, sin ruta a producción ni credenciales del clúster; y darle al job que
escribe el manifiesto de producción una credencial de la base de datos de
producción para mejorar un mensaje de error es un intercambio que rechazamos
explícitamente — ese job ya tiene `contents: write`.

Entonces compara dos cosas que **sí** puede ver, ambas en el repositorio:

- `alembic heads` del repo (derivado recorriendo `alembic/versions/` con `ast`:
  sin base, sin settings, sin importar la app).
- `alembic/PROD_ALEMBIC_STATE.json:recorded_revision` — la última revisión que
  un humano leyó de producción con `alembic_converge.py --check`.

Si la cabeza está más de N revisiones adelante del ledger (N = 0 por defecto),
el promote se detiene salvo que el operador marque
**`migrations_acknowledged=true`** en el `workflow_dispatch`.

**Qué compra esto, dicho con honestidad:** no verifica producción. Convierte una
suposición silenciosa en una pregunta ruidosa. Hoy se puede promover código cuyo
ORM hace SELECT de una columna que la base no tiene y enterarse por los 500. Con
esto, ese promote exige que alguien marque una casilla que dice «sé que hay
migraciones sin aplicar». La verificación real es `--check` desde el pod, y este
runbook la hace precondición de marcar la casilla.

**La casilla existe solo en `workflow_dispatch`.** El camino programado
(hoy apagado por `AUTO_PROMOTE_ENABLED`) no tiene operador que reconozca nada, y
un promote desatendido sobre una migración sin aplicar es precisamente el caso
para el que existe el guardia: ahí un ledger desviado detiene el promote, no lo
deja pasar.

**Falla del lado seguro.** Un ledger que nadie actualiza se desvía hacia
«atrasado», y exige el reconocimiento más seguido de lo estrictamente necesario.
Es el lado correcto para equivocarse.

> **Nota de estado (2026-09-03):** con el ledger en 011 y la cabeza en 016, el
> guardia **bloquea todo promote** hasta que se ejecute la convergencia
> (sección 3) y se actualice el ledger, o hasta que se marque
> `migrations_acknowledged=true`. Es el resultado buscado: el primer promote
> después de este cambio obliga a mirar el estado real de la base.

Localmente:

```bash
cd apps/api
python scripts/alembic_promote_guard.py                # bloquea si hay desvío
python scripts/alembic_promote_guard.py --acknowledged # lo que hace la casilla
```

---

## 5. La regla, de acá en adelante

1. **`promote` NO ejecuta migraciones.** Es el diseño. No lo cambies sin un ADR.
2. **Toda migración aplicada a mano se sella inmediatamente después.** Aplicar y
   sellar son un solo procedimiento, no dos tareas; separarlos es lo que produjo
   este runbook.
3. **Después de sellar, actualizá `PROD_ALEMBIC_STATE.json`** en un PR. El
   ledger es lo único que el guardia de promote puede ver.
4. **Nunca `alembic upgrade` contra un esquema que ya tiene los objetos.** Usá
   `--check` para confirmar y `--stamp` para registrar.
5. **PARCIAL nunca se resuelve sellando.** Se escala.
6. **Toda migración nueva sigue siendo reentrante** (consultar `inspect()` antes
   de crear), como 003/006/007/009/010/011/012/014/015/016. Lo verifica
   `tests/unit/test_migration_reentrancy.py`.

---

## 6. Referencias

| Qué | Dónde |
|---|---|
| Script de convergencia | `apps/api/scripts/alembic_converge.py` |
| Guardia de promote | `apps/api/scripts/alembic_promote_guard.py` |
| Ledger del estado de producción | `apps/api/alembic/PROD_ALEMBIC_STATE.json` |
| Tests | `apps/api/tests/unit/test_alembic_converge.py`, `test_alembic_promote_guard.py` |
| Invariantes del grafo de revisiones | `apps/api/tests/unit/test_alembic_revision_graph.py` |
| Reentrancia de migraciones | `apps/api/tests/unit/test_migration_reentrancy.py` |
| Pipeline de promote | `.github/workflows/promote-to-prod.yml`, `docs/PP_3B_STAGING_PIPELINE.md` |
| Reconciliación GitOps | `docs/runbooks/production-gitops-reconcile.md` |

## Revisión 017: aplicar, no inferir del catálogo histórico

`017_payment_mail_dispatch` agrega recibos durables para avisos de pago y
compuertas PostgreSQL que **no** crea `Base.metadata.create_all`. El convergidor
histórico de 012–016 no demuestra que esas compuertas existan y no debe usarse
para sellar 017. Aplique la migración real por la vía autorizada de Enclii antes
de habilitar el nuevo endpoint; consulte [la receta de recuperación](payment-notice-recovery.md).
El libro `PROD_ALEMBIC_STATE.json` conserva la última verificación real: no se
actualiza al escribir código ni por pasar pruebas locales. Con filas en el nuevo
ledger, el downgrade se rechaza para preservar evidencia; revierta la aplicación.
