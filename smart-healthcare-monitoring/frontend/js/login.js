import { beginLogin, completeLogin, getAccessToken } from "./auth.js";

const button = document.querySelector("#login-button");
const message = document.querySelector("#login-message");

try {
  if (new URLSearchParams(location.search).has("error")) {
    throw new Error(new URLSearchParams(location.search).get("error_description") || "Cognito rejected sign-in.");
  }
  if (await completeLogin() || getAccessToken()) {
    location.replace("dashboard.html");
  }
} catch (error) {
  message.textContent = error.message;
  message.hidden = false;
}

button.addEventListener("click", async () => {
  button.disabled = true;
  try {
    await beginLogin();
  } catch (error) {
    message.textContent = error.message;
    message.hidden = false;
    button.disabled = false;
  }
});
