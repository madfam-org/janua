# Claims de organización y service principals

> Contrato de claims para las apps del ecosistema. Última revisión: 2026-09-03.

Dos cambios que van juntos y **no deben separarse**:

1. Los tokens de sesión (enlace mágico, contraseña, MFA, passkey) ahora sellan
   `org_id` — igual que los de OIDC.
2. Los roles de organización viajan bajo una clave **con espacio de nombres**,
   `madfam_org_roles`, nunca bajo `roles` a secas.

El punto 2 es lo que evita que el punto 1 sea una fuga. Está explicado abajo.

---

## 1. El problema que resuelve

`symbiosis-hcm` exige `org_id` en el token y responde **403** sin él
(`apps/api/core/permissions.py`). janua sí sellaba `org_id`… pero **solo en el
camino OIDC**. El camino de enlace mágico —`AuthService.create_session`— no lo
sellaba nunca, porque el resolvedor de claims vivía dentro del router de OIDC y
era estructuralmente inalcanzable desde el servicio de sesiones.

Consecuencia concreta: el equipo de CTM entra al MAP clínico por enlace mágico.
Al pulsar «Mi espacio (RH)» llegaban a una app que **carga y los rechaza**.
Peor que un 404, porque parece un problema suyo.

## 2. La trampa que había armada

`HR_ROLES` de symbiosis-hcm contenía la cadena literal `"admin"`. Los `roles`
que janua sella por OIDC son roles de **membresía de organización**
(`owner`/`admin`/`member`): permisos sobre la **cuenta** —invitar a alguien,
rotar un secreto, pagar la factura—, no sobre nómina.

Lo único que separaba a un `admin` de organización de la nómina, los salarios,
el SDI y los expedientes laborales del tenant era que su token **no traía
`org_id`** y la verificación de tenant lo rechazaba primero.

**Sellar `org_id` sin arreglar el espacio de nombres de los roles convierte un
403 honesto en una fuga de nómina**, en silencio, para todo `admin` de toda
organización. Por eso los dos cambios van juntos, y por eso hay pruebas que
fallan si alguien «simplifica» el namespace de vuelta.

## 3. Forma de los claims

Resueltos por `app/services/org_claims_service.py`, la **única** fuente. El
router de OIDC lo importa; no hay una segunda copia (dos copias de un
resolvedor de autorización derivan, y una copia derivada falla o cerrada —
alguien deja de trabajar— o abierta — alguien gana un tenant).

| Claim | Tipo | Cuándo se emite | Significado |
|---|---|---|---|
| `orgs` | lista de `{id, slug, role}` | con ≥1 membresía **activa** | todas las membresías activas |
| `org_id` | string (UUID) | solo si **no hay ambigüedad** | el tenant primario |
| `tenant_id` | string (UUID) | igual que `org_id` | alias de `org_id` |
| `org_slug` | string | igual que `org_id` | slug del tenant primario |
| `madfam_org_roles` | lista de strings | igual que `org_id` | rol de organización **en esa org** |
| `roles` | lista de strings | **solo** con concesiones vivas | roles de **aplicación** (`hcm:hr`), ver §5 |
| `is_service_account` | `true` | **solo** si la identidad es técnica | ver §4 |

**«Sin ambigüedad»** significa: exactamente una membresía activa, o
`user.tenant_id` nombra una de ellas. Con varias organizaciones y sin ancla, se
emite `orgs` **y nada más** — ningún consumidor debe adivinar un tenant.
Adivinar el tenant primario de un usuario multi-org es exactamente cómo el
operador de un tenant termina leyendo la nómina de otro.

Ejemplo (token de sesión de un integrante de CTM):

```jsonc
{
  "sub": "…", "tid": "…", "type": "access", "email": "…",
  "madfam_entitled_products": ["crea-map:pro", "kalya:team"],
  "orgs": [{ "id": "<uuid>", "slug": "crea", "role": "member" }],
  "org_id": "<uuid>",
  "tenant_id": "<uuid>",
  "org_slug": "crea",
  "madfam_org_roles": ["member"]
}
```

### Invariantes

- **Aditivo.** Un usuario sin membresía activa recibe un token con la forma
  exacta de antes: ninguna de estas claves aparece.
- **`roles` no cambia.** El camino OIDC sigue emitiéndolo igual para los
  clientes que ya lo leen. Los tokens de **sesión** no lo emiten: estrenan el
  claim con namespace, sin heredar la ambigüedad.
- **Fail-closed.** Si la resolución falla, no se emite ningún claim de
  organización. Los servicios con alcance de org rechazan; nunca mal-asignan.
- **Nunca bloquea el login.** Un fallo del resolvedor degrada a «sin claims»,
  no a un 500.
- **No se puede suplantar.** `additional_claims` se mezcla **antes** que las
  claves reservadas (`sub`/`tid`/`jti`/`type`/`exp`/`iss`/`aud`), así que un
  dict hostil o con bug no puede reescribir la identidad del token.
- **La revocación llega al refresh.** El resolvedor filtra
  `status == "active"`, y `refresh_tokens` vuelve a resolver: una membresía
  revocada deja de alimentar el claim en la siguiente rotación.

### Para quien consume

`madfam_org_roles` describe autoridad sobre la **cuenta de janua** y no debe
autorizar nada dentro de un producto. Los roles de **aplicación** —los que sí
autorizan dentro de un producto— viajan bajo `roles` y se conceden
explícitamente por organización: ver §5. La regla que no cambia es que el
**vocabulario** de roles lo sigue definiendo el servidor de recursos
(`symbiosis-hcm/apps/api/core/roles.py`); janua sólo registra **a quién** se le
concedió **qué**, por quién y cuándo.

---

## 4. Service principals

`User` distinguía `status`, `is_active`, `is_admin` y `tenant_id`. Ninguno
responde la pregunta que una app consumidora realmente hace: **¿esta fila es
una persona?**

Todo tenant multi-app acaba con logins técnicos —un acceso de desarrollo, un
importador, un principal de integración—, y sin esta marca aparecen en cada
roster, cada selector de asignación y cada campo de firma de documento como si
fueran colegas.

`User.is_service_account` (migración `015_user_is_service_acct`) es el primer
campo del modelo que describe **qué es** la fila, no qué puede hacer.

### No confundir con tokens de servicio

| | Service **token** | Service **principal** |
|---|---|---|
| Qué es | cliente OAuth `client_credentials` | fila `User` marcada |
| Tiene fila de usuario | no | sí |
| Para qué | Zavlo llama a Karafiel | una persona-máquina inicia sesión y ve una pantalla |
| Documentación | `docs/service-tokens.md`, ADR-006 | este documento |

Son problemas distintos. Los tokens de servicio ya estaban resueltos; esto es
la otra mitad, la de los logins **con forma humana** que aun así no son humanos.

### Roles de aplicación en tokens de servicio (2026-09-03)

**La concesión de un cliente de servicio son sus `allowed_scopes`, y el
servidor de recursos ve el rol namespaced VERBATIM.**

Los roles de aplicación de una **persona** salen de
`organization_member_app_roles` (migración 016), colgados de una fila de
membresía. Un principal **máquina no tiene membresía**, así que la columna que
un operador ya controla —y que ya decide qué puede pedir ese cliente— es su
registro de concesión.

En el camino `client_credentials`, para un cliente con `organization_id`, cada
scope **solicitado** que:

1. está en los `allowed_scopes` del cliente,
2. tiene la forma namespaced `^[a-z][a-z0-9-]*:[a-z][a-z0-9_-]*$`
   (`hcm:hr`, `hcm:employee`, `kalya:manage`), y
3. **no** es un rol de membresía de organización (`owner`/`admin`/`member`) ni
   un alias heredado `admin` / `*:admin`,

se emite **verbatim, con los dos puntos**, dentro del claim `roles`.

**El hueco que cierra.** `symbiosis-hcm` autoriza **solo** con roles de
aplicación leídos de `roles` (`apps/api/core/permissions.py`). janua sí sellaba
`org_id`/`tenant_id`/`org_slug` desde `client.organization_id` para estos
tokens, pero construía `roles` **a partir de los scopes**, como
`["service_account"]` + `admin` + `<scope>.replace(":", "_")` — así que
`hcm:admin` llegaba como `hcm_admin`, **con el separador equivocado**, y
`hcm:hr` no se emitía nunca. Un cliente de servicio ligado a una organización
(el de nauta, el gestor de kalya) **no podía satisfacer a HCM jamás**.

**Es aditivo, no un reemplazo.** `service_account`, el `admin` heredado y las
formas con guion bajo se siguen emitiendo exactamente igual; ningún consumidor
vivo ve cambiar la forma de un claim. Los scopes pedidos y **no** concedidos
siguen fallando igual que hoy (`invalid_scope`, 400).

**Sin organización, sin roles de aplicación.** Un cliente sin
`organization_id` no recibe ninguno: su token no lleva `org_id` que acote el
rol, así que un `hcm:hr` ahí sería autoridad sobre **cualquier** tenant que HCM
llegue a consultar. Falla cerrado.

**`madfam_org_roles` para un token de servicio trae `["service_account"]`.**
Los roles de aplicación viajan **solo** en `roles`. Un principal máquina no
tiene membresía de organización; poner ahí un rol de aplicación le diría al
consumidor que lo concedió la **cuenta** de janua, que es exactamente la
confusión que el espacio de nombres existe para evitar (ver §5, «La trampa del
`roles` heredado»).

**Ejemplo — `nauta` pidiendo `hcm:hr`** (cliente con `organization_id` = la org
de Crea, `allowed_scopes` con `hcm:hr`):

```jsonc
{
  "sub": "service-account:jnc_nauta",
  "token_use": "client_credentials",
  "actor_type": "service_account",
  "client_id": "jnc_nauta",
  "scope": "hcm:hr openid",
  "roles": ["hcm:hr", "service_account"],   // ← lo que HCM lee
  "madfam_org_roles": ["service_account"],  // ← NUNCA un rol de aplicación
  "org_id": "<uuid de la org de Crea>",
  "tenant_id": "<uuid de la org de Crea>",
  "org_slug": "crea",
  "is_admin": false
}
```

**Auditoría.** Cada token de servicio acuñado **con** roles de aplicación
escribe un evento `service_token.app_roles` (`client_id`, `org_id`, los roles;
**nunca** el secreto). Un token de servicio ordinario no escribe nada y su
costo no cambia. `allowed_scopes` dice qué **puede** pedir un cliente; este
evento dice qué **pidió**, y cuándo.

#### Cómo conceder el scope (operador)

Superficie dedicada, con la misma autenticación que el resto de los endpoints
internos (`X-Internal-API-Key`):

| Endpoint | Qué hace |
|---|---|
| `POST /api/v1/internal/oauth-clients/{client_id}/scopes` | añade **un** scope. **201** si lo añadió, **200** si ya estaba |
| `POST /api/v1/internal/oauth-clients/{client_id}/scopes/revoke` | lo retira. `changed: false` si no había nada que retirar |
| `GET /api/v1/internal/oauth-clients/{client_id}/scopes` | `allowed_scopes` + `app_role_scopes` (los que **sí** llegarán a `roles`) |

```bash
curl -sS -X POST \
  "$JANUA_URL/api/v1/internal/oauth-clients/jnc_nauta/scopes" \
  -H "X-Internal-API-Key: $INTERNAL_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"scope": "hcm:hr"}'
```

- **Aditivo e idempotente.** Toca **un** scope; los demás quedan intactos, así
  que un reintento nunca es destructivo.
- **`emits_app_role` en la respuesta.** Contesta la pregunta que el operador
  realmente tiene: *¿este scope llegará al claim `roles`?* Es `false` si el
  cliente no tiene `organization_id` o si el scope está mal escrito (`hcm_hr`),
  en lugar de descubrirlo como un 403 de HCM días después.
- **404 si el cliente no existe**, con un solo mensaje para «no existe» e
  «inactivo», para que la superficie no sirva de sonda.
- **No hay endpoint que lea, devuelva ni registre un secreto.**

**Por qué no las superficies que ya había.** `POST /oauth/clients/register`
**reemplaza `allowed_scopes` entero** en su camino de convergencia: el manifiesto
versionado de un consumidor, al re-ejecutarse, **borraría en silencio** un scope
concedido a mano. `PATCH /oauth/clients/{id}` exige sesión humana
(`get_current_user`) y también recibe la lista completa.

**Vía SQL** (romper-cristal, si el endpoint no está disponible):

```sql
UPDATE oauth_clients
   SET allowed_scopes = allowed_scopes || '["hcm:hr"]'::jsonb,
       updated_at = now()
 WHERE client_id = 'jnc_nauta'
   AND NOT (allowed_scopes @> '["hcm:hr"]'::jsonb);
```

> **Alcance:** igual que en §5, estos roles **no** gobiernan la puerta del ERP
> de Crea (eso vive en el `WorkspaceMember` de nauta). `hcm:*` autoriza dentro
> de symbiosis-hcm y nada más. **No se requiere migración**: se reutiliza
> `oauth_clients.allowed_scopes`, que ya existe.

### Superficies

- **Claim** `is_service_account: true` — en tokens de sesión y de OIDC. Se sella
  **solo** cuando es verdadero: el token de una persona no gana ninguna clave y
  su forma es idéntica a la de antes.
- **`GET /api/v1/users/me`, `/users/{id}`, `/users/`** — campo
  `is_service_account`.
- **`GET /api/v1/organizations/{id}/members`** — campo `is_service_account`,
  resuelto desde la identidad (no desde la fila de membresía: ser cuenta de
  servicio es un hecho de la **identidad**, verdadero en todas sus orgs, y una
  org no puede discrepar de otra al respecto). Se calcula **después** de la
  caché de Redis del servicio, para que una caché vieja nunca afirme que un
  login técnico es una persona.
- **`POST /api/v1/internal/users/provision`** — acepta `is_service_account`
  (por defecto `false`) y lo devuelve; acepta `org_role` (por defecto `member`)
  y devuelve el rol de la membresía activa resultante en `org_role`.

### La regla del provisioning

`provision` **honra la bandera solo al crear**. Una fila existente se devuelve
intacta —igual que ya pasaba con el nombre—: cambiar una identidad viva entre
«persona» y «servicio» tiene consecuencias visibles en rosters y en firmas de
documentos, y no debe ocurrir como efecto secundario del reintento de una app
de roster. La respuesta echa el valor **almacenado**, para que quien llame
detecte el caso sin una segunda lectura.

### Pool de identidad vs. organización (decisión del 2026-09-03)

`provision` recibe **dos** cosas distintas, y confundirlas causó una caída:

| Campo | Qué decide |
| --- | --- |
| `organization_id` (preferido) · `tenant_id` (alias **deprecado**) | **A qué organización** pertenece la persona. Se registra como `OrganizationMember`. Exactamente uno de los dos; si van ambos, deben coincidir. |
| `identity_pool` — `"platform"` (por defecto) · `"tenant"` | **En qué pool de unicidad de correo vive la IDENTIDAD**, es decir si `users.tenant_id` queda en NULL o no. |

- **Personal (STAFF) ⇒ `"platform"` + membresía.** `users.tenant_id` queda
  **NULL**. La liga con la organización es la fila de `organization_members`,
  no una columna en `users`. Es la forma correcta para todo el que llama hoy,
  incluida el «Alta de integrante» de crea-map.
- **Usuarios finales (BaaS Fase 1) ⇒ `"tenant"`.** `users.tenant_id` sí se
  escribe: son los usuarios de un cliente, aislados en el pool de ese cliente,
  y no se espera que resuelvan por las entradas por correo de la plataforma.

**Por qué.** Hasta el 2026-09-03 `tenant_id` hacía **los dos trabajos a la vez**,
así que cada integrante del CTM que crea-map aprovisionaba caía en un pool de
tenant. Ahí las entradas por correo desnudo —magic link, recuperación de
contraseña— **no podían verlo**: `send_magic_link` busca en el pool sin tenant,
no lo encontraba, tomaba su rama de creación y el INSERT chocaba con
`ix_users_email`, que en producción sigue siendo el índice único **global**
(migración 013 sin aplicar; `alembic_version` = 011) → `IntegrityError` → 503.
21 personas quedaron sin poder entrar. Ver ADR-001, «Email lookup pools and the
013 schema/code drift».

**Ciclo de vida.** `suspend` / `reactivate` **no** reciben `identity_pool`:
resuelven a la persona primero en el pool de plataforma y luego entre pools, así
que siguen funcionando tanto para las identidades nuevas como para las que se
crearon con el comportamiento anterior. El alcance por organización —que antes
daba `users.tenant_id`— ahora lo impone la **membresía**: sólo se puede actuar
sobre alguien que tenga membresía en la organización indicada.

**Compatibilidad.** `tenant_id` se sigue aceptando con el mismo significado, de
modo que el llamador actual (crea-map, que sólo envía `tenant_id`) no requiere
cambio alguno en este despliegue; migrará a `organization_id` en un seguimiento.

### La membresía es la excepción a esa regla

Escribir `tenant_id` en la fila del `User` **no otorga acceso**. El resolutor de
claims cuenta únicamente membresías con `status == "active"`, así que una
identidad con `tenant_id` y **sin** `OrganizationMember` recibe un token **sin
`org_id`** — y HCM la rechaza con 403. Por eso `provision` crea (o reconcilia)
la membresía activa en **la misma transacción** que el usuario, y lo hace en
**ambas** ramas, la de creación y la de «ya existía»: reconciliarla en la rama
de 200 es lo que **repara a quienes se provisionaron antes de este cambio**, que
de otro modo quedarían fuera de «Mi espacio (RH)» para siempre.

- **`org_role`** (opcional, por defecto `member`) elige el rol de la membresía.
  Está acotado a `admin` · `member` · `viewer`: el valor viaja al claim
  `madfam_org_roles`, y una cadena libre dejaría que una app de roster acuñe una
  autorización arbitraria. **`owner` no se ofrece**: la propiedad de una
  organización es una decisión de operador, no algo que conceda un «Alta de
  integrante».
- **No degrada un rol existente.** Si ya hay membresía activa se devuelve tal
  cual: un ascenso hecho por un operador sobrevive al reintento del roster,
  igual que sobrevive el nombre.
- **Re-alta.** Una membresía `removed`/`inactive` se **revive** (no se duplica),
  porque el reintento del roster es precisamente la re-alta.
- La respuesta trae **`org_role`** (o `null` si no hay membresía), para que la
  app de roster verifique que la persona llevará `org_id` sin decodificar un
  token.

### Cómo leerlo (para consumidores)

Trátalo como una **afirmación positiva**: ausente ⇒ persona. Es la dirección
segura, y es deliberadamente la contraria a los defaults de autorización de
este repo: confundir una cuenta de servicio con una persona muestra una fila de
más en un roster; confundir una persona con una cuenta de servicio **borraría a
un colega** de la interfaz donde trabaja.

La bandera **no autoriza ni desautoriza nada**. Es un hecho de presentación. Si
llegara a conceder o quitar acceso, un operador tendría dos palancas donde cree
tener una.

---

## 5. Roles de aplicación (`hcm:hr` y compañía)

### El hueco que quedaba

Poner espacio de nombres a `madfam_org_roles` (§2) era lo correcto y **dejó la
otra mitad sin construir**. symbiosis-hcm autoriza con roles de **aplicación**
que lee del claim `roles` —`hcm:hr`, `hcm:admin`, `employee`
(`apps/api/core/permissions.py`)— y **janua no emitía ni una sola cadena
`hcm:*`**. Es decir: la Dirección de CTM podía tener una membresía válida,
recibir un token con `org_id` correcto (§4 y janua#591)… y aun así ser rechazada
en todas las funciones de RH. La membresía respondía *cuál inquilino*; nada
respondía *cuál autoridad dentro del producto*.

### La forma

Una concesión = una fila en `organization_member_app_roles` (migración `016`),
colgada de la **membresía**, no del usuario:

| Columna | Para qué |
|---|---|
| `organization_member_id` | la membresía que la porta (FK, `ON DELETE CASCADE`) |
| `app` · `role` | **opacos** para janua: `hcm` · `hr` |
| `granted_by` · `granted_at` | quién la concedió y cuándo |
| `revoked_at` · `revoked_by` | quién la retiró y cuándo |

El resolutor las convierte en `"<app>:<role>"` y las sella bajo `roles`.

**Por qué una tabla y no un JSONB en la membresía.** Esto concede autoridad
sobre **nómina y expedientes laborales**, así que los dos datos que un auditor
pide —quién la dio y cuándo se quitó— tienen que sobrevivir a la concesión. Una
lista JSONB guarda sólo el estado actual: revocar es una reescritura en sitio
que **borra la evidencia** de que la concesión existió. Las filas se retiran con
`revoked_at`, nunca se borran, igual que `capability_links` (§ADR-004) y por la
misma razón por la que `internal_users` no tiene endpoint de purga.

**Por qué cuelga de la membresía y no del usuario.** Una concesión no significa
nada fuera de la membresía que la porta: si alguien sale de la organización, su
autoridad de RH se va con el inquilino en vez de quedar como fila huérfana que
un futuro re-alta reanimaría en silencio. Además hace que la fuga entre
organizaciones sea **estructuralmente difícil de escribir**: el resolutor parte
de UNA fila de membresía y no puede alcanzar las concesiones de otra org.

### Las tres reglas de alcance

- **Sólo la org primaria resuelta aporta.** Sin `org_id` inequívoco no hay
  `roles` tampoco: elegir una de varias membresías entregaría la autoridad de RH
  de un inquilino a una sesión que la persona abrió para otro.
- **Nada es implícito.** No hay derivación desde `member.role`, ni conjunto por
  defecto, ni tabla que convierta un `admin` de organización en `hcm:admin`.
  Cualquiera de esas reconstruiría **por la puerta de atrás** el puente
  rol-de-cuenta → nómina que el espacio de nombres existe para impedir. Una
  cuenta de servicio se trata igual que una persona: lo que se le concedió
  explícitamente, y nada más.
- **La revocación llega al refresh.** El resolutor filtra `revoked_at IS NULL` y
  todos los caminos de emisión re-resuelven.

### La trampa del `roles` heredado

El camino OIDC **ya emitía** su propio `roles` (roles de organización, para
clientes que lo leen desde hace años, y que contiene la cadena `"admin"`). En
ese handler `**org_claims` se expande **después** de `"roles": entitlements[...]`,
así que una clave `roles` saliendo del resolutor **habría pisado el claim
heredado** por puro orden de diccionario. Por eso el resolutor devuelve la clave
privada `_app_roles` y `merge_app_roles_into_claims` la integra una sola vez
para ambos caminos:

- **Tokens de sesión**: sólo roles de aplicación. Siguen sin llevar ningún rol de
  organización bajo `roles` — lo que aterriza ahí es `hcm:hr`, jamás `admin`.
- **OIDC**: la **unión** con la lista heredada. Nadie pierde una cadena que ya leía.

Sin concesiones **no se emite la clave `roles` en absoluto**, así que el token de
quien no tiene nada concedido conserva exactamente su forma anterior.

### Superficie de administración

Misma autenticación que el resto de los endpoints internos
(`X-Internal-API-Key`), y misma costura reemplazable hacia service tokens.

| Endpoint | Qué hace |
|---|---|
| `POST /api/v1/internal/app-roles/grant` | concede `(org, user, app, role)`. **201** si la creó, **200** si ya existía |
| `POST /api/v1/internal/app-roles/revoke` | la retira. `changed: false` si no había nada que retirar |
| `GET /api/v1/internal/app-roles/{organization_id}/{user_id}` | `claim_values` vivos + historial completo, incluidas las revocadas |

- **Idempotente en ambos sentidos.** Un `grant` repetido devuelve el
  `granted_at` **original**: la respuesta a «¿cuándo se le dio acceso a nómina?»
  es la primera vez, no el último reintento. Volver a conceder tras revocar crea
  una fila **nueva** (el historial es el punto).
- **404 si no hay membresía activa** en esa organización — el mismo filtro que
  aplica el resolutor, así que una concesión que nunca alimentaría un token se
  señala en vez de aceptarse en silencio. Un solo mensaje para «no existe la
  org» y «no es miembro», para que la superficie no sirva de sonda.
- **Se valida la forma, no el significado.** `app` y `role` son opacos, pero se
  rechaza un separador dentro de un componente: el claim es `f"{app}:{role}"`, y
  un `app` igual a `"hcm:hr"` emitiría `"hcm:hr:x"` y podría **fabricar** un rol
  que el servidor de recursos sí reconoce.
- **No hay endpoint de borrado**, y no debe haberlo.

> **Alcance:** estos roles **no** gobiernan la puerta del ERP de Crea. Una
> auditoría de SSO resolvió que ese control vive en el `WorkspaceMember` de
> nauta. `hcm:*` autoriza dentro de symbiosis-hcm y nada más.

---

## 6. Entitlements por organización (lectura interna, janua#611)

`GET /api/v1/me/entitlements` contesta **qué puede alcanzar el usuario que
llama**: está acotado a `get_current_user` y mezcla las concesiones per-usuario
del portador, la herencia de su organización primaria y el catch-all de admin
(ver `app/services/entitlements_service.py`). Es la pregunta correcta para un
cliente que lee **su propio** espacio, y la equivocada para un asesor de MADFAM
que **ve el espacio de un cliente**: el token del asesor nombra los entitlements
del asesor (vacíos / de MADFAM), no los del cliente, así que un hub que se apoye
en él pinta cada producto del cliente como «no contratado».

Este endpoint contesta una pregunta **distinta**: «¿qué otorga **esta
organización**?», independiente de cualquier viewer, leído directo del
`product_tiers` de la org.

| Endpoint | Qué hace |
|---|---|
| `GET /api/v1/internal/orgs/{org_id}/entitlements` | Entitlements que **la organización** otorga, por id de org. **422** si `org_id` no es un UUID; conjunto **vacío** si la org no existe o no tiene `product_tiers` («esta org no otorga nada», nunca «desconocido») |

- **Autenticación.** `verify_internal_api_key` — el mismo `X-Internal-API-Key`
  que `internal_users`, `internal_app_roles` e `internal_oauth_client_scopes`.
  **No** debe ser alcanzable con el token de acceso de un usuario: los
  entitlements de una org son un hecho **sobre la org**, y contestarlo para
  cualquier portador que nombre un id de org dejaría que un cliente enumerara el
  mix de productos de otro. Una credencial de servicio es la autoridad correcta,
  igual que la escritura org-scoped (`set_org_product_tier`) tampoco vive en la
  superficie de usuario.
- **Forma de la respuesta.** Idéntica a la de `/me/entitlements`
  (`EntitlementsResponse`): `products` es la lista de filas
  `{slug, tier, expires_at, source}` y `claim_string_form` son las mismas cadenas
  `"<slug>:<tier>"` del claim JWT. Quien ya parsea una parsea la otra sin contrato
  nuevo. Cada fila trae `source: "inherited"`, porque eso es lo que es un tier de
  org.
- **Sin capa per-usuario ni catch-all de admin.** Ninguno es una propiedad de la
  organización; incluirlos contestaría una pregunta diferente de la que el caso
  del asesor necesita. Es una **lectura pura** — sin escritura, sin concesión, sin
  mutación de auditoría —, así que no acarrea efecto que un operador tenga que
  revertir.

**El modelo de entitlements, resumido.** `entitlements_service` deriva lo que un
usuario alcanza mezclando, en orden de prioridad: (1) filas per-usuario
(`user_entitlements`, escritas por el webhook de suscripción de Dhanam y por
herramientas de admin); (2) herencia de la organización **primaria** del usuario
(su `product_tiers`); (3) catch-all de admin (`is_admin=True`). La fila de mayor
prioridad gana ante slugs duplicados. `get_org_entitlements(org_id)` reutiliza
sólo la capa (2) —el `product_tiers` de la org proyectado a la misma forma— pero
para **una org nombrada**, no para la org primaria del portador.

**Quién lo consume, y por qué cierra el hueco de la §5.** El ERP de nauta lee
este endpoint con el id de la org janua del **espacio que se está viendo** cuando
el viewer es un asesor (miembro `ADVISOR` o «ver como»), en lugar del
`/me/entitlements` del propio asesor. Esa es la contraparte de la nota de alcance
de la §5: la **puerta** del ERP de Crea vive en el `WorkspaceMember` de nauta, y
las **fichas** que el ERP pinta se resuelven contra el `product_tiers` de la org
del cliente — leído por aquí. janua sigue siendo la única autoridad de
entitlements; nauta sólo pregunta.

---

## 7. Pasos de operador

1. **Aplicar la migración `015_user_is_service_acct`** deliberadamente contra la
   base de datos objetivo. `promote` **no corre migraciones** en este
   ecosistema. Es aditiva (una columna `NOT NULL DEFAULT false`, nada se altera
   ni se borra) y re-entrante. Hasta aplicarla, el SELECT del ORM falla
   ruidosamente contra una base que no la tiene — el fallo previsto, no una
   respuesta silenciosamente equivocada.
2. **Promover janua.** Sin promote, ningún token nuevo lleva `org_id` y «Mi
   espacio (RH)» sigue en 403.
3. **Desplegar symbiosis-hcm con su cambio hermano ANTES o A LA VEZ.** Este es
   el orden que importa: si `org_id` llega a HCM sin la separación de roles, todo
   `admin` de organización obtiene acceso RH completo. Ver §2.
4. **Verificar** con un token de sesión real que `org_id`, `org_slug` y
   `madfam_org_roles` están presentes, y que `roles` **no** lleva roles de
   organización.
5. **Marcar el login técnico** de crea-map como service principal, cuando ese
   camino se ejecute (ver el handoff del PR).
6. **Aplicar la migración `016_org_member_app_roles` A MANO** antes de promover
   el cambio de roles de aplicación (§5). `promote` **no corre migraciones**: el
   SQL exacto va en el cuerpo del PR. Es aditiva (una tabla nueva y dos índices;
   nada se altera ni se borra) y re-entrante. Hasta aplicarla, el resolutor
   degrada **fail-closed** —no sella ningún rol de aplicación, que es el
   comportamiento de hoy— y los endpoints de concesión fallan ruidosamente
   contra la relación ausente.
7. **Conceder los roles de aplicación** que hagan falta, ya con la tabla puesta:
   para la Dirección de CTM, `hcm:hr` en la organización de Crea. Sin este paso
   la tabla está vacía y **nada cambia para nadie** — que es justamente lo que
   hace seguro promover el código antes de decidir las concesiones.
8. **Verificar** en un token real que `roles` trae `hcm:hr` y que
   `madfam_org_roles` sigue trayendo el rol de organización por separado.
9. **Para un cliente de SERVICIO** (nauta, el gestor de kalya), conceder el
   scope con `POST /api/v1/internal/oauth-clients/{client_id}/scopes` (§4).
   **No hay migración que aplicar**: se reutiliza `oauth_clients.allowed_scopes`.
   Verificar en la respuesta que `emits_app_role` es `true` — si es `false`, o
   el cliente no tiene `organization_id`, o el scope está mal escrito.

## 8. Referencias

- `apps/api/app/services/org_claims_service.py` — el resolvedor, fuente única
- `apps/api/app/models/app_role.py` — la tabla de concesiones (§5)
- `apps/api/app/routers/v1/internal_app_roles.py` — conceder / revocar / listar
- `apps/api/app/routers/v1/oauth_provider.py` — `_service_client_app_roles`, la
  regla de §4 para clientes de servicio
- `apps/api/app/routers/v1/internal_oauth_client_scopes.py` — conceder /
  revocar / listar scopes de un cliente
- `apps/api/tests/unit/routers/test_service_client_app_roles.py`
- `apps/api/tests/unit/routers/test_internal_oauth_client_scopes.py`
- `apps/api/alembic/versions/016_org_member_app_roles.py` — la migración de §5
- `apps/api/tests/unit/services/test_app_role_claims.py`
- `apps/api/tests/unit/routers/test_internal_app_roles.py`
- `apps/api/app/services/service_principal.py` — el predicado y el claim
- `apps/api/alembic/versions/015_user_is_service_account.py` — la migración
- `apps/api/tests/unit/services/test_org_claims_service.py`
- `apps/api/tests/unit/services/test_service_principal.py`
- `apps/api/app/routers/v1/internal_org_entitlements.py` — la lectura por org de la §6
- `apps/api/app/services/entitlements_service.py` — `get_org_entitlements` y `get_user_entitlements`
- `apps/api/tests/unit/routers/test_internal_org_entitlements.py`
- `apps/api/tests/unit/services/test_entitlements_service.py`
- `nauta/apps/web/src/server/erp-entitlements.ts` — el consumidor (asesor ⇒ org del espacio visto)
- `symbiosis-hcm/apps/api/core/roles.py` — el otro lado de §2
- ADR-003 (multi-tenancy), ADR-004 (capability links), `docs/service-tokens.md`
