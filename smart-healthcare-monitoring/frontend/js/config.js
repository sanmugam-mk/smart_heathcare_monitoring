// Replace these public Cognito/API identifiers after deploying the SAM stack.
// This browser-only app has no client secret; keep credentials out of this file.
export const config = {
  region: "ap-south-1",
  userPoolId: "REPLACE_WITH_USER_POOL_ID",
  clientId: "REPLACE_WITH_APP_CLIENT_ID",
  hostedUiDomain: "https://REPLACE_WITH_COGNITO_DOMAIN.auth.ap-south-1.amazoncognito.com",
  apiBaseUrl: "https://REPLACE_WITH_API_ID.execute-api.ap-south-1.amazonaws.com/v1",
  redirectUri: "http://localhost:8000/",
  logoutUri: "http://localhost:8000/",
};
