/**
 * Browser storage, with the xlb-to-Dewdrop key rename handled once.
 *
 * The rename moved `xlb.skin-profile` to `dewdrop.skin-profile` and the two chat
 * keys alongside it. Nothing read the old names afterwards, so anyone who had
 * used the site before the rename came back to an empty profile — including an
 * empty **avoid-list**. Losing a stored currency preference is a shrug; silently
 * discarding the ingredients somebody told us they react to is not, because the
 * screening then reports "clear" on a product it would previously have flagged.
 *
 * So reads look under the current key, fall back to the legacy one, and migrate
 * the value forward when they find it. The fallback costs one extra
 * `getItem` on a cache miss and can be deleted once enough time has passed that
 * no live browser still holds the old keys.
 *
 * Every accessor is wrapped in try/catch rather than merely null-checked:
 * localStorage throws outright in private windows and embedded contexts.
 */

const PREFIX = 'dewdrop.'
const LEGACY_PREFIX = 'xlb.'

function currentKey(name: string): string {
  return `${PREFIX}${name}`
}

function legacyKey(name: string): string {
  return `${LEGACY_PREFIX}${name}`
}

/**
 * Read a value, migrating it from the pre-rename key if that is where it lives.
 *
 * `name` is the suffix only — `'currency'`, `'skin-profile'`, `'chat.avoid'`.
 */
export function read(name: string): string | null {
  try {
    const current = window.localStorage.getItem(currentKey(name))
    if (current !== null) return current

    const legacy = window.localStorage.getItem(legacyKey(name))
    if (legacy === null) return null

    // Found under the old name: move it forward so this only happens once.
    window.localStorage.setItem(currentKey(name), legacy)
    window.localStorage.removeItem(legacyKey(name))
    return legacy
  } catch {
    return null
  }
}

export function write(name: string, value: string): void {
  try {
    window.localStorage.setItem(currentKey(name), value)
  } catch {
    // Non-fatal: the value still holds for this session.
  }
}

export function remove(name: string): void {
  try {
    window.localStorage.removeItem(currentKey(name))
    // Clear the legacy copy too, or the next read would resurrect it.
    window.localStorage.removeItem(legacyKey(name))
  } catch {
    // Nothing to do.
  }
}

export function readJson<T>(name: string, fallback: T): T {
  const raw = read(name)
  if (raw === null) return fallback
  try {
    return JSON.parse(raw) as T
  } catch {
    // A corrupt value is no more useful than a missing one.
    return fallback
  }
}

export function writeJson(name: string, value: unknown): void {
  try {
    write(name, JSON.stringify(value))
  } catch {
    // Unserialisable value; nothing worth storing.
  }
}

/** The full key a `name` resolves to, for `storage` event comparisons. */
export function keyFor(name: string): string {
  return currentKey(name)
}

/** Does a `storage` event concern this name, under either key? */
export function eventMatches(eventKey: string | null, name: string): boolean {
  return eventKey === currentKey(name) || eventKey === legacyKey(name)
}
