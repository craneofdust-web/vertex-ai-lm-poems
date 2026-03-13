export async function api(path, options = {}) {
  const response = await fetch(path, options);
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      if (body && body.detail) detail = String(body.detail);
    } catch (error) {
      // ignore parse errors for non-json responses
    }
    throw new Error(detail);
  }
  return response.json();
}
