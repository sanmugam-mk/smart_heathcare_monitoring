import { config } from "./config.js";
import { getAccessToken, signOut } from "./auth.js";

export async function api(path, options = {}) {
  const token = getAccessToken();
  if (!token) {
    signOut();
    throw new Error("Your session expired. Sign in again.");
  }
  const headers = new Headers(options.headers || {});
  headers.set("authorization", `Bearer ${token}`);
  if (options.body && !(options.body instanceof FormData)) headers.set("content-type", "application/json");
  let response;
  try {
    response = await fetch(`${config.apiBaseUrl}${path}`, { ...options, headers });
  } catch (error) {
    throw new Error(`Could not reach the AWS API. Check your connection and API configuration. ${error.message}`);
  }
  const payload = await response.json().catch(() => null);
  if (response.status === 401) {
    signOut();
    throw new Error("Your sign-in has expired or is not authorized.");
  }
  if (!response.ok || payload?.success === false) {
    throw new Error(payload?.message || `AWS API request failed (${response.status}).`);
  }
  return payload?.data;
}

export function jsonBody(value) {
  return JSON.stringify(value);
}
