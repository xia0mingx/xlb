import { useCallback, useSyncExternalStore } from 'react'
import type { SkinProfile } from '../api/types'
import * as storage from '../storage'

const STORAGE_NAME = 'skin-profile'

export const emptyProfile: SkinProfile = {
  skin_type: 'normal',
  concerns: [],
  sensitive: false,
  acne_prone: false,
  fragrance_free: false,
  budget_max: null,
  categories: [],
  avoid_ingredients: [],
}

function read(): SkinProfile | null {
  // Storage can throw outright in private windows and embedded contexts, so
  // every access is guarded rather than merely null-checked.
  const stored = storage.readJson<Partial<SkinProfile> | null>(STORAGE_NAME, null)
  return stored ? ({ ...emptyProfile, ...stored } as SkinProfile) : null
}

// One shared snapshot for the whole app. Several components read the profile at
// once - the header badge, the page, the picker - and they must all re-render
// when it changes. Per-component useState cannot do that: the `storage` event
// fires only in OTHER tabs, so the tab that saved would be the one tab left
// showing stale data.
let snapshot: SkinProfile | null = read()
const listeners = new Set<() => void>()

function emit() {
  listeners.forEach((listener) => listener())
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  // Cross-tab sync still matters: the quiz may be retaken in another tab.
  const onStorage = (event: StorageEvent) => {
    if (storage.eventMatches(event.key, STORAGE_NAME)) {
      snapshot = read()
      emit()
    }
  }
  window.addEventListener('storage', onStorage)
  return () => {
    listeners.delete(listener)
    window.removeEventListener('storage', onStorage)
  }
}

// Must return a stable reference between renders or React re-renders forever.
function getSnapshot(): SkinProfile | null {
  return snapshot
}

function write(next: SkinProfile | null) {
  snapshot = next
  if (next) storage.writeJson(STORAGE_NAME, next)
  else storage.remove(STORAGE_NAME)
  emit()
}

/** The skin profile lives in localStorage - there are no user accounts in v1. */
export function useSkinProfile() {
  const profile = useSyncExternalStore(subscribe, getSnapshot, getSnapshot)

  const setProfile = useCallback((next: SkinProfile) => write(next), [])
  const clearProfile = useCallback(() => write(null), [])

  return { profile, setProfile, clearProfile, hasProfile: profile !== null }
}
