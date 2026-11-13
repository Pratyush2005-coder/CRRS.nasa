// DEMO ONLY - replace with real backend later.
//
// Everything here runs in the browser: accounts are kept in localStorage and a password is
// stored as a salted SHA-256 hash (never as plain text). This is NOT real security - anyone
// can open the browser tools and see the saved data. When a backend exists, only this file
// needs to change: the rest of the app talks to these functions and nothing else.

import { FARM_LOCATION } from '../config/location'

const USERS_KEY = 'agroverseUsers'
const SESSION_KEY = 'agroverseSession'

// ---SHA-FALLBACK-START
// Used only if the browser's Web Crypto is unavailable (for example when testing over plain
// http on a phone). Normal case: crypto.subtle is used below.
const K = [
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
  0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
  0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
  0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
  0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
  0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
  0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
  0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
]

function sha256Fallback(str) {
  const bytes = new TextEncoder().encode(str)
  const len = bytes.length
  const padded = new Uint8Array(((len + 9 + 63) >> 6) << 6)
  padded.set(bytes)
  padded[len] = 0x80
  const view = new DataView(padded.buffer)
  view.setUint32(padded.length - 8, Math.floor((len * 8) / 0x100000000))
  view.setUint32(padded.length - 4, (len * 8) >>> 0)

  const h = [0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19]
  const w = new Uint32Array(64)
  const rotr = (x, n) => (x >>> n) | (x << (32 - n))

  for (let i = 0; i < padded.length; i += 64) {
    for (let t = 0; t < 16; t++) w[t] = view.getUint32(i + t * 4)
    for (let t = 16; t < 64; t++) {
      const s0 = rotr(w[t - 15], 7) ^ rotr(w[t - 15], 18) ^ (w[t - 15] >>> 3)
      const s1 = rotr(w[t - 2], 17) ^ rotr(w[t - 2], 19) ^ (w[t - 2] >>> 10)
      w[t] = (w[t - 16] + s0 + w[t - 7] + s1) >>> 0
    }
    let [a, b, c, d, e, f, g, hh] = h
    for (let t = 0; t < 64; t++) {
      const S1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25)
      const ch = (e & f) ^ (~e & g)
      const t1 = (hh + S1 + ch + K[t] + w[t]) >>> 0
      const S0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22)
      const maj = (a & b) ^ (a & c) ^ (b & c)
      const t2 = (S0 + maj) >>> 0
      hh = g; g = f; f = e
      e = (d + t1) >>> 0
      d = c; c = b; b = a
      a = (t1 + t2) >>> 0
    }
    h[0] = (h[0] + a) >>> 0; h[1] = (h[1] + b) >>> 0; h[2] = (h[2] + c) >>> 0; h[3] = (h[3] + d) >>> 0
    h[4] = (h[4] + e) >>> 0; h[5] = (h[5] + f) >>> 0; h[6] = (h[6] + g) >>> 0; h[7] = (h[7] + hh) >>> 0
  }
  return h.map((x) => x.toString(16).padStart(8, '0')).join('')
}
// ---SHA-FALLBACK-END

async function sha256Hex(text) {
  const c = globalThis.crypto
  if (c && c.subtle) {
    const digest = await c.subtle.digest('SHA-256', new TextEncoder().encode(text))
    return Array.from(new Uint8Array(digest))
      .map((b) => b.toString(16).padStart(2, '0'))
      .join('')
  }
  return sha256Fallback(text)
}

function randomSalt() {
  const bytes = new Uint8Array(16)
  const c = globalThis.crypto
  if (c && c.getRandomValues) c.getRandomValues(bytes)
  else for (let i = 0; i < bytes.length; i++) bytes[i] = Math.floor(Math.random() * 256)
  return Array.from(bytes).map((b) => b.toString(16).padStart(2, '0')).join('')
}

const hashPassword = (salt, password) => sha256Hex(`${salt}:${password}`)

function readUsers() {
  try {
    const raw = localStorage.getItem(USERS_KEY)
    const list = raw ? JSON.parse(raw) : []
    return Array.isArray(list) ? list : []
  } catch {
    return []
  }
}

// may throw if the browser blocks storage - callers catch it
function writeUsers(users) {
  localStorage.setItem(USERS_KEY, JSON.stringify(users))
}

// never hand the salt / hash to the UI
function toPublic(user) {
  // eslint-disable-next-line no-unused-vars
  const { salt, hash, ...rest } = user
  return rest
}

const normalizeEmail = (email) => String(email || '').trim().toLowerCase()

// ---------------------------------------------------------------- public API
// Every function returns { ok: true, ... } or { ok: false, error: '<code>' }.
// The codes match the keys in locales -> auth.errors.

export function getCurrentUser() {
  try {
    const id = localStorage.getItem(SESSION_KEY)
    if (!id) return null
    const user = readUsers().find((u) => u.id === id)
    return user ? toPublic(user) : null
  } catch {
    return null
  }
}

export async function signUp({ name, email, password, landArea, farmSoil, currentCrop }) {
  try {
    const users = readUsers()
    const cleanEmail = normalizeEmail(email)
    if (users.some((u) => u.email === cleanEmail)) return { ok: false, error: 'emailExists' }

    const salt = randomSalt()
    const user = {
      id: 'u_' + Date.now().toString(36) + Math.random().toString(36).slice(2, 8),
      name: String(name).trim(),
      email: cleanEmail,
      salt,
      hash: await hashPassword(salt, password),
      farmLocation: FARM_LOCATION.name, // fixed to Purulia for now
      landArea: String(landArea),
      farmSoil,
      currentCrop,
      createdAt: new Date().toISOString(),
    }
    writeUsers([...users, user])
    localStorage.setItem(SESSION_KEY, user.id)
    return { ok: true, user: toPublic(user) }
  } catch {
    return { ok: false, error: 'storage' }
  }
}

export async function signIn(email, password) {
  try {
    const user = readUsers().find((u) => u.email === normalizeEmail(email))
    if (!user) return { ok: false, error: 'invalidCredentials' }
    const hash = await hashPassword(user.salt, password)
    if (hash !== user.hash) return { ok: false, error: 'invalidCredentials' }
    localStorage.setItem(SESSION_KEY, user.id)
    return { ok: true, user: toPublic(user) }
  } catch {
    return { ok: false, error: 'storage' }
  }
}

export async function signOut() {
  try {
    localStorage.removeItem(SESSION_KEY)
  } catch {
    // nothing to do
  }
  return { ok: true }
}

// Only these fields can be edited. Email and location are fixed.
const EDITABLE = ['name', 'landArea', 'farmSoil', 'currentCrop']

export async function updateProfile(patch) {
  try {
    const id = localStorage.getItem(SESSION_KEY)
    const users = readUsers()
    const index = users.findIndex((u) => u.id === id)
    if (index === -1) return { ok: false, error: 'generic' }

    const updated = { ...users[index] }
    EDITABLE.forEach((field) => {
      if (patch[field] !== undefined) updated[field] = String(patch[field]).trim()
    })
    users[index] = updated
    writeUsers(users)
    return { ok: true, user: toPublic(updated) }
  } catch {
    return { ok: false, error: 'storage' }
  }
}

export async function resetPassword(email, newPassword) {
  try {
    const users = readUsers()
    const index = users.findIndex((u) => u.email === normalizeEmail(email))
    if (index === -1) return { ok: false, error: 'noAccount' }

    const salt = randomSalt()
    users[index] = { ...users[index], salt, hash: await hashPassword(salt, newPassword) }
    writeUsers(users)
    return { ok: true }
  } catch {
    return { ok: false, error: 'storage' }
  }
}
