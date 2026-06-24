export const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function authFetch(
  url: string,
  init: RequestInit = {},
): Promise<Response> {
  const token =
    typeof window !== "undefined"
      ? localStorage.getItem("access_token")
      : null;

  const headers = new Headers(init.headers);

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  return fetch(url, {
    ...init,
    headers,
  });
}
