import { config } from "./config.js";

const TOKEN_KEY = "medichart_access_token";
const ID_TOKEN_KEY = "medichart_id_token";
const STATE_KEY = "medichart_oauth_state";
const VERIFIER_KEY = "medichart_pkce_verifier";

function decodeJwt(token) {
  const encoded = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
  return JSON.parse(atob(encoded.padEnd(Math.ceil(encoded.length / 4) * 4, "=")));
}

function base64Url(bytes) {
  let binary = "";
  bytes.forEach((value) => { binary += String.fromCharCode(value); });
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

async function createChallenge(verifier) {
  const data = new TextEncoder().encode(verifier);
  return base64Url(new Uint8Array(await crypto.subtle.digest("SHA-256", data)));
}

export function getAccessToken() {
  const token = sessionStorage.getItem(TOKEN_KEY);
  if (!token) return null;
  try {
    if (decodeJwt(token).exp * 1000 <= Date.now()) {
      clearSession();
      return null;
    }
    return token;
  } catch {
    clearSession();
    return null;
  }
}

export function getRole() {
  const token = sessionStorage.getItem(ID_TOKEN_KEY);
  if (!token) return "Doctor";
  try {
    const groups = decodeJwt(token)["cognito:groups"] || [];
    return groups.includes("admin") ? "Administrator" : groups.includes("doctor") ? "Doctor" : "Authorized user";
  } catch {
    return "Doctor";
  }
}

function clearSession() {
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(ID_TOKEN_KEY);
}

export async function beginLogin() {
  const verifier = base64Url(crypto.getRandomValues(new Uint8Array(48)));
  const state = base64Url(crypto.getRandomValues(new Uint8Array(24)));
  sessionStorage.setItem(VERIFIER_KEY, verifier);
  sessionStorage.setItem(STATE_KEY, state);
  const challenge = await createChallenge(verifier);
  const url = new URL(`${config.hostedUiDomain}/oauth2/authorize`);
  url.search = new URLSearchParams({
    client_id: config.clientId,
    response_type: "code",
    scope: "openid email profile",
    redirect_uri: config.redirectUri,
    state,
    code_challenge_method: "S256",
    code_challenge: challenge,
  }).toString();
  window.location.assign(url.toString());
}

export async function completeLogin() {
  const params = new URLSearchParams(window.location.search);
  const code = params.get("code");
  if (!code) return false;
  const state = params.get("state");
  if (!state || state !== sessionStorage.getItem(STATE_KEY)) {
    throw new Error("Sign-in state did not match. Please try signing in again.");
  }
  const verifier = sessionStorage.getItem(VERIFIER_KEY);
  if (!verifier) throw new Error("Sign-in session expired. Please try again.");
  const response = await fetch(`${config.hostedUiDomain}/oauth2/token`, {
    method: "POST",
    headers: { "content-type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "authorization_code",
      client_id: config.clientId,
      code,
      redirect_uri: config.redirectUri,
      code_verifier: verifier,
    }),
  });
  if (!response.ok) throw new Error(`Sign-in failed (${response.status}); check Cognito callback configuration.`);
  const tokens = await response.json();
  if (!tokens.access_token || !tokens.id_token) throw new Error("Cognito returned an incomplete token response.");
  sessionStorage.setItem(TOKEN_KEY, tokens.access_token);
  sessionStorage.setItem(ID_TOKEN_KEY, tokens.id_token);
  sessionStorage.removeItem(STATE_KEY);
  sessionStorage.removeItem(VERIFIER_KEY);
  history.replaceState({}, document.title, window.location.pathname);
  return true;
}

export function signOut() {
  clearSession();
  sessionStorage.removeItem(STATE_KEY);
  sessionStorage.removeItem(VERIFIER_KEY);
  const url = new URL(`${config.hostedUiDomain}/logout`);
  url.search = new URLSearchParams({
    client_id: config.clientId,
    logout_uri: config.logoutUri,
  }).toString();
  window.location.assign(url.toString());
}

export function requireSession() {
  if (!getAccessToken()) {
    window.location.replace(config.redirectUri);
    return false;
  }
  return true;
}
