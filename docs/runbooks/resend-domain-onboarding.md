# Onboarding a client sending domain in Resend

**Scope:** adding a second sending domain so janua can send transactional mail
*from the client's own address* rather than `hola@madfam.io`. Written while
onboarding the first client tenant; the steps generalise. Below, `Client` is the
tenant's display name, `<client-domain>` its sending domain and `<tenant>` its
binding key in `apps/api/app/services/sender_binding.py`.

**Read first:** [`../EMAIL_SENDER_POLICY.md`](../EMAIL_SENDER_POLICY.md). This
runbook executes Phase 2 of that policy. The single precondition the policy
calls non-negotiable is the one this runbook is about: **the domain must be
verified in Resend before janua is told to send from it.**

## The one thing that must not go wrong

Resend does not degrade when you send from a domain it has not verified — it
**rejects the API call**. An unverified sender is not a message in the spam
folder, it is *no message at all*, and the message in question is a sign-in
link. So the code and the cutover are deliberately separated:

| State | `RESEND_VERIFIED_DOMAINS` | A tenant's magic link comes from |
|---|---|---|
| Today (code merged, domain not verified) | `madfam.io` | `MADFAM <hola@madfam.io>` |
| After verification + manifest edit | `madfam.io,<client-domain>` | `Client <hola@<client-domain>>` |

**The display name waits with the address.** They are one decision, keyed on
whether the binding's own address domain is verified. There is no intermediate
state.

> **Corrected 2026-09-07.** This table previously read
> `Client <hola@madfam.io>` in the first row, under the rule "the display
> name moves as soon as the code ships; only the address waits". That behaviour
> shipped in #603 and was **observed in production on 2026-09-07 at 02:32:21
> CDMX** — the first magic link requested from the tenant's portal arrived in
> the client's inbox with exactly that From — and was **rejected the same night**.
> Only MADFAM sends from `hola@madfam.io`; a client's display name in front of
> MADFAM's address is a claim the recipient cannot verify and is the shape of a
> display-name spoof. See `docs/EMAIL_SENDER_POLICY.md`.

Both states run the same code path, so the cutover is not also a first
execution — `tests/unit/services/test_email_branding.py::
TestSenderUnderTheVerifiedDomainGate` exercises the post-verification state in
CI, and
`tests/unit/services/test_email_sender.py::TestDisplayNameFollowsAddress` is the
regression fence for the header above.

**Body branding is not affected by any of this.** The tenant header, palette,
voice (tú/usted) and CDMX clock render on both sides of the verification line —
`email_branding.py` is a separate decision from the From line.

## Precondition: DNS must be ours

`<client-domain>` must be delegated to Cloudflare first. If its nameservers
still point at a previous web host, records cannot be applied through Enclii
until the domain plan's nameserver switch (nameservers → Cloudflare) is done. Do
not start step 2 before then — the DKIM record simply cannot be published.

## Order of operations

### 1. Create the domain in Resend and read back its DNS

The DKIM public key is generated per-domain, so the records cannot be written
into this runbook ahead of time; they must be read from the API at creation.

```bash
export RESEND_API_KEY=...            # operator env only — never commit, never echo
python3 scripts/resend_domain_onboard.py <client-domain>
```

Idempotent: a re-run finds the existing domain instead of creating a duplicate.
It prints the records **and** the matching `enclii providers cloudflare
dns-apply` lines. Exit code `2` means "exists, not verified yet" — expected here.

> **If the very first call answers `HTTP 403` with a body of `error code: 1010`,
> the API key is not the problem.** That is Cloudflare, in front of
> `api.resend.com`, refusing urllib's default `User-Agent` before the request
> reaches Resend. Both scripts now send a descriptive UA (#606 for this one; the
> sibling `sender_binding_switch.py` in the 2026-09-07 wrap-up), and
> `tests/unit/test_resend_scripts_user_agent.py` fails if either loses it. Worth
> recognising by sight: a 403 on an authenticated endpoint reads as a bad
> credential, and an operator can burn a long time rotating a key that was fine.

### 2. Publish the records through Enclii

Enclii-first: do not edit DNS in the Cloudflare dashboard. Copy the generated
lines from step 1 verbatim. Their shape (values are per-domain — use the
script's output, not these):

```bash
enclii providers cloudflare dns-apply resend._domainkey \
  --type TXT --content '<the DKIM value from step 1>' \
  --proxied false --apply \
  --reason 'Resend sending-domain verification for <client-domain>'

enclii providers cloudflare dns-apply send \
  --type MX --content '10 feedback-smtp.us-east-1.amazonses.com' \
  --proxied false --apply \
  --reason 'Resend sending-domain verification for <client-domain>'

enclii providers cloudflare dns-apply send \
  --type TXT --content 'v=spf1 include:amazonses.com ~all' \
  --proxied false --apply \
  --reason 'Resend sending-domain verification for <client-domain>'
```

Three records, in Resend's own vocabulary:

- **DKIM** — `resend._domainkey` TXT, the per-domain public key. This is the one
  that breaks if a character is lost in transcription, which is why step 1
  generates the command rather than asking you to retype it.
- **SPF (return path)** — `send.<client-domain>` gets **both** an `MX` and a
  `TXT`. The `send` subdomain is Resend's default custom return path; it is
  what makes SPF align with the envelope sender.
- Note `--proxied false` on every record — these are mail records, and there is
  no TTL flag on `dns-apply`.

**DMARC is optional** for verification and recommended after it: a
`_dmarc.<client-domain>` TXT of `v=DMARC1; p=none; rua=mailto:...` starts in
report-only so nothing is rejected while alignment is observed.

### 3. Ask Resend to verify

Propagation is not instant; give the records a few minutes first.

```bash
python3 scripts/resend_domain_onboard.py <client-domain> --verify
```

Repeat until it reports `Status : verified` (exit code `0`). `--status` polls
without attempting a re-check. **Do not proceed while this says anything else.**

### 4. Create the `hola@<client-domain>` mailbox (Proton)

Resend *sends* as `hola@<client-domain>`; nothing *receives* there until the
mailbox exists, and janua sets `Reply-To: hola@<client-domain>` on the tenant's
mail. A person replying to a sign-in mail must land somewhere real.

This is a **manual operator step in the Proton admin console** (part of the
client's domain plan) — it is not automated here and this repo has no Proton
credentials. Add `hola@` as an address/alias on the Proton-hosted domain.

Proton's own MX records are separate from Resend's `send.` return-path MX and
do not conflict — they sit at different names.

### 5. Flip the janua manifest

Only now. In the production janua manifest (the API deployment's env):

```
RESEND_VERIFIED_DOMAINS=madfam.io,<client-domain>
```

Keep `madfam.io` in the list — dropping it would downgrade every other
sender. The value is comma-separated and matched on the **exact** domain, so
`<client-domain>` does not authorise `sub.<client-domain>`.

This is a plain env change; **no Alembic migration is involved.**

### 6. Smoke: read the actual From header

The API's 200 says nothing about SPF/DKIM alignment or spam placement. Read a
real message.

1. Request a magic link for a tenant user from the tenant's canonical host.
   (Every host in the binding's `hosts` is a valid tenant signal for sender
   purposes; use the one people are actually given.)
2. In the received mail, confirm:
   - `From: Client <hola@<client-domain>>`
   - `Reply-To: hola@<client-domain>`
   - `Authentication-Results:` shows `dkim=pass` and `spf=pass`
   - it landed in the **inbox**, not spam
3. Confirm a reply to that address arrives in the Proton mailbox.
4. Confirm a sign-in with **no tenant** (e.g. `janua.dev`) still comes from
   `MADFAM <hola@madfam.io>`.

Step 4 is not optional: the gate is shared, and a mistake in step 5 is most
likely to show up as MADFAM's own mail breaking.

## Rollback

Remove the domain from the verified set and redeploy:

```
RESEND_VERIFIED_DOMAINS=madfam.io
```

The tenant's mail immediately reverts to `MADFAM <hola@madfam.io>` — the platform sender
whole, name and address together (2026-09-07 rule) — and delivery resumes on a
domain with four-plus months of reputation. No code change, no migration, no
Resend change. The domain can stay registered in Resend while rolled back. The
tenant's BODY branding is untouched by a rollback.

If instead the *default* sender is what broke, the fault is almost certainly a
malformed `RESEND_VERIFIED_DOMAINS` (blank falls back to `madfam.io` by design;
a typo'd value does not). Check the deployed env before touching Resend.

## What this runbook deliberately does not do

- It does not add DNS by hand or via `kubectl` — Enclii-first, per `AGENTS.md`.
- It does not automate Proton. Mailbox creation is an operator action.
- It does not put the API key anywhere but the operator's shell. The script
  reads `RESEND_API_KEY` from env and never prints it or the `Authorization`
  header.

---

# Quién puede tener remitente de marca

**Sólo los clientes vCTO.** Directiva del propietario, 2026-09-06: «este tipo
de trato debe reservarse exclusivamente para nuestros clientes vCTO, donde
tenemos control operativo completo.»

La razón no es comercial, es operativa. Cuando un correo sale como
`Cliente <hola@<dominio-del-cliente>>`, MADFAM se ha hecho cargo del DNS de ese
dominio, de la rotación de su DKIM, de su reputación de envío y de sus rebotes.
Eso se puede prometer para un cliente retenido cuya infraestructura operamos.
No se puede prometer para un alta self-serve — y prometerlo ahí significa que
el problema de entregabilidad de un desconocido llega como incidente nuestro.

## Dónde vive la verdad

En **janua**, en `product_tiers` de la organización — el mismo almacén de
titularidades que ya alimenta el claim `madfam_entitled_products` del JWT:

```json
{ "vcto": "fractional_cto" }
```

Se otorga y se revoca por el endpoint de admin que ya existe y que ya audita:

```
POST   /api/v1/admin/entitlements/org   {"org_id": "...", "product": "vcto", "tier": "fractional_cto"}
DELETE /api/v1/admin/entitlements/org   {"org_id": "...", "product": "vcto"}
```

**Por qué no se lee de nauta.** Nauta sí tiene el dato (`Workspace.tier =
FRACTIONAL_CTO`), pero (1) no lo expone a ningún llamador de servicio — sus dos
rutas máquina devuelven sólo `{workspaceId, provisioning, locale}` y un
`TimeEntryDraft`; (2) la integración hoy va nauta → janua y nunca al revés,
así que preguntarle obligaría al proveedor de identidad a depender de un
producto aguas abajo en un BackgroundTask, para un enlace de acceso; y (3) el
propio ADR-0001 de nauta declara que «janua es la única autoridad de
titularidades». Preguntarle a nauta invertiría la regla que nauta respeta.

## La compuerta falla cerrada

El mailer corre sin sesión de base de datos, así que la lectura autoritativa no
puede ocurrir en la ruta de envío. La compuerta consulta, en orden: una
decisión explícita del llamador, luego el caché de proceso, y si ninguna
responde **no hay derecho**.

«Falla cerrada» aquí significa que el correo **sí sale**, desde
`MADFAM <hola@madfam.io>` — el remitente de la plataforma completo. Nunca
significa que el enlace de acceso no llegue: un correo que nadie recibe es peor
falla que un correo desde la dirección de la plataforma.

## Matriz de respaldo (fallback)

| vCTO | Dominio verificado en la cuenta que envía | Sale como |
|---|---|---|
| sí | sí | `Cliente <hola@<dominio-del-cliente>>` |
| sí | no | `MADFAM <hola@madfam.io>` |
| no | sí | `MADFAM <hola@madfam.io>` |
| no | no | `MADFAM <hola@madfam.io>` |
| sin señal de inquilino | — | `MADFAM <hola@madfam.io>` |

El degradado es **total**, no parcial: el nombre visible acompaña siempre a la
dirección. `Cliente <hola@madfam.io>` **nunca** debe producirse — sólo
MADFAM envía desde `hola@madfam.io`, y poner el nombre de un cliente delante de
esa dirección es una afirmación que quien recibe no puede verificar.

> **Corregido el 2026-09-07.** Esta matriz decía `Cliente <hola@madfam.io>`
> en las tres filas de respaldo, bajo la regla «el degradado siempre es parcial:
> la marca es cosmética, la dirección es operativa». Ese comportamiento se
> observó en producción el 2026-09-07 a las 02:32:21 CDMX (primer enlace mágico
> pedido desde el portal del inquilino) y fue rechazado esa misma noche. El nombre
> visible es tan operativo como la dirección.

La marca del cliente **sí** aparece en el **cuerpo** del mensaje en todos los
casos: encabezado, colores, voz (tú/usted) y reloj CDMX no dependen de esta
compuerta.

---

# Migrar a tu propia cuenta de Resend (u otro proveedor)

Directiva del propietario, 2026-09-06: «debemos permitir mecanismos para que
[el primer cliente] y cualquier otro cliente vCTO pueda moverse fácilmente a su
propia cuenta de Resend (o su proveedor preferido).»

Un `SenderBinding` (`apps/api/app/services/sender_binding.py`) separa **quién
firma el correo** de **qué cuenta lo envía**. Mudarse de cuenta cambia tres
campos del binding — `account`, `credential_ref`, `verified_domains` — y
**ningún camino de código**. Es reversible en un comando.

> La verificación de dominio en Resend es **por cuenta**. Que
> `<dominio-del-cliente>` esté verificado en la cuenta de MADFAM no dice nada sobre la
> cuenta del cliente. Por eso un binding en cuenta propia lleva su propia lista
> `verified_domains` y deja de consultar `RESEND_VERIFIED_DOMAINS`.

## Orden de operaciones

### 0. La llave, una sola vez, sin eco

El operador pega la API key del cliente una vez y la escribe a Vault. Ni el
script ni el binding ven nunca el valor: el binding guarda una **referencia**.

```bash
read -rs TENANT_RESEND_API_KEY && export TENANT_RESEND_API_KEY
vault kv put secret/janua/senders/<inquilino> resend_api_key="$TENANT_RESEND_API_KEY"
```

### 1. ¿La cuenta del cliente ya tiene el dominio, verificado?

```bash
python3 scripts/sender_binding_switch.py <inquilino> --verify
```

Código de salida `2` = existe pero no verificado. `0` = listo para el paso 3.

> **`HTTP 403` con cuerpo `error code: 1010` no es la llave.** Es Cloudflare
> delante de `api.resend.com` rechazando el `User-Agent` por omisión de urllib.
> Ambos scripts ya mandan un UA descriptivo y hay una prueba que falla si se
> pierde. Un 403 en un extremo autenticado se lee como credencial mala: no
> rotes la llave del cliente por esto.

### 2. Si no: crearlo ahí e imprimir el DNS que falta

```bash
python3 scripts/sender_binding_switch.py <inquilino> --onboard
```

La clave DKIM es **por cuenta además de por dominio**, así que son registros
**nuevos**, distintos a los que ya están publicados para la cuenta de MADFAM.
El script imprime las líneas `enclii providers cloudflare dns-apply` listas.
Publicarlas por Enclii, esperar propagación, y repetir el paso 1.

### 3. Voltear el binding

```bash
python3 scripts/sender_binding_switch.py <inquilino> --switch \
    --credential-ref 'secret/data/janua/senders/<inquilino>#resend_api_key'
```

Se **rehúsa** a correr si el paso 1 no reporta `verified` (usar `--force` sólo
a sabiendas): voltear antes haría que Resend rechace cada envío del inquilino, y
los enlaces de acceso no llegarían en absoluto.

Edita `sender_binding.py` e imprime el diff. Es un cambio de código a
propósito — el binding es configuración versionada, así que la mudanza se
revisa en un PR y se revierte con `git`. Usar `--dry-run` para verlo sin
escribir.

Antes de desplegar, confirmar que la credencial sí está en Vault (responde
sí/no, nunca imprime el valor):

```bash
python3 scripts/sender_binding_switch.py <inquilino> --check-credential
```

### 4. Reversa

```bash
python3 scripts/sender_binding_switch.py <inquilino> --rollback
```

Vuelve a la cuenta de MADFAM. La línea `From` no cambia; sólo cambia la cuenta
que la transporta. Confirmar que el dominio siga en `RESEND_VERIFIED_DOMAINS`
de la cuenta de MADFAM, o la dirección degradará a `hola@madfam.io`.

## Otro proveedor que no sea Resend

`provider` es un campo del binding (`resend` | `smtp`). El stub `smtp` existe
con la misma interfaz para que «proveedor preferido» sea un cambio de binding y
no de código. **Todavía no tiene transporte detrás**: un binding que declare
`smtp` falla de forma visible en el envío en vez de salir calladamente por
Resend, que sería mentir sobre cómo salió el correo. Implementar el transporte
SMTP es el trabajo pendiente para el primer cliente que lo pida.

## Qué NO hace este procedimiento

- No toca DNS a mano — Enclii-first, por `AGENTS.md`.
- No pone una llave en el repositorio, en un log, ni en un argumento de línea
  de comandos. El binding guarda referencias; Vault guarda valores.
- No cambia la compuerta vCTO. Mudarse de cuenta y tener derecho a remitente de
  marca son decisiones independientes.

---

# Estado real: el primer inquilino en su propia cuenta (desde 2026-09-07)

El primer inquilino vCTO completó la mudanza. Su dominio está **Verificado** en
la cuenta de Resend del propio cliente (DKIM `resend._domainkey`, MX/TXT de
envío publicados por Enclii y por el panel de Cloudflare). Su binding en
`sender_binding.py`:

```
tenant           <inquilino>
account          tenant                    (antes: madfam)
credential_ref   <VARIABLE>                (un NOMBRE — una variable de entorno)
verified_domains ("<dominio-del-cliente>",) (antes: () — delegaba en la lista global)
```

## La credencial es una VARIABLE DE ENTORNO, no una ruta de Vault

Esta es la corrección importante al paso 3 de arriba, y hay que leerla antes de
mudar al segundo inquilino.

```
Vault  secret/janua#<inquilino>_resend_api_key
  ↓  (ExternalSecret administrado por enclii)
Secret de K8s  janua-secrets, llave `<inquilino>-resend-api-key`
  ↓  (env, marcada optional en k8s/base/deployments/janua-api.yaml)
Env del pod  <VARIABLE>  (el nombre que guarda `credential_ref`)
  ↓
apps/api/app/services/sender_credentials.py
```

`sender_credentials` acepta las dos formas de referencia, pero **janua-api corre
sin `VAULT_ADDR` / `VAULT_TOKEN`** (verificado en el pod en vivo, 2026-09-07).
Una referencia `ruta#campo` por lo tanto **nunca puede resolverse en
producción**: fallaría cada vez, en silencio, y dejaría al inquilino en el
remitente de plataforma para siempre. El ExternalSecret es lo que tiende el puente entre
Vault y el pod; la variable de entorno es lo que el proceso sí puede leer.

Por eso el `--credential-ref` del paso 3 para un despliegue como el actual es el
**nombre de la variable**, y hay que declararla en el deployment:

```bash
python3 scripts/sender_binding_switch.py <inquilino> --switch \
    --credential-ref '<VARIABLE>'
```

La entrada de env está marcada **optional** en el deployment a propósito: si la
llave falta, el remitente degrada (abajo) en vez de impedir que arranque el pod.

## Si falta la credencial, el correo SIGUE saliendo

Regla del propietario (#607), aplicada una capa más abajo: **el enlace de acceso
de un cliente nunca se bloquea por una credencial de inquilino faltante.**

Hay una ventana legítima en la que falta: el operador voltea el binding antes de
escribir el secreto, o el ExternalSecret aún no sincroniza. En esa ventana:

- **El enlace mágico sale igual**, desde el remitente de plataforma,
  `MADFAM <hola@madfam.io>`, **entero**. Nunca
  `Cliente <hola@madfam.io>` — una degradación sigue sujeta a LA REGLA.
- **Se registra una advertencia**, `sender_credentials.tenant_credential_missing`,
  con el inquilino y la **referencia** de la credencial. Nunca el valor.
- **El cuerpo no se toca**: el mensaje sigue leyéndose como el cliente. Lo
  que se retiene es la afirmación del sobre, no la presencia del inquilino.

Por qué esto no es un lujo: un binding en cuenta propia lleva su propia
`verified_domains`, que describe una cuenta a la que el proceso sólo llega con
la llave de ese inquilino. Sin la llave, las dos compuertas anteriores **pasan**
— el dominio SÍ está verificado, en una cuenta a la que no nos podemos
autenticar — y la dirección de marca saldría por la cuenta de MADFAM, donde
`<dominio-del-cliente>` **no** está verificado. Resend rechaza eso de tajo. La falla no
es un `From` feo: es un cliente que no puede entrar.

`email_sender.sender_for` aplica entonces una **tercera compuerta**,
`sender_credentials.tenant_credential_available`, después de la vCTO y la de
dominio verificado.

> `--check-credential` sigue respondiendo **NO** en ese estado, y debe hacerlo:
> es la pregunta del operador («¿ya está la llave?»), no la del envío. El camino
> de envío hace la pregunta booleana y degrada; `resolve_credential` sigue
> lanzando excepción para quien pide el secreto en sí.

## Verificación después de desplegar

```bash
# 1. ¿La llave llegó al pod? (responde sí/no, nunca imprime el valor)
python3 scripts/sender_binding_switch.py <inquilino> --check-credential

# 2. Pedir un enlace mágico desde un host del inquilino y leer el encabezado real.
#    Esperado: From: Cliente <hola@<dominio-del-cliente>>
#    Si se lee «MADFAM <hola@madfam.io>», buscar en los logs
#    `sender_credentials.tenant_credential_missing` antes de tocar el binding:
#    casi siempre es el ExternalSecret, no el código.
```

## Reversa desde este estado

Borrar el secreto **no** es una reversa: degrada al inquilino al remitente de
plataforma, no restaura el envío de marca por la cuenta de MADFAM. La reversa
real vuelve a poner los tres campos:

```bash
python3 scripts/sender_binding_switch.py <inquilino> --rollback
```

y exige que `<dominio-del-cliente>` siga en `RESEND_VERIFIED_DOMAINS` de la cuenta de
MADFAM, o la dirección degradará a `hola@madfam.io` de todos modos.
