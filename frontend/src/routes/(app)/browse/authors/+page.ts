import * as api from '$lib/api/client';

export async function load() {
  const authors = await api.getAuthors(0, 500);
  return { authors };
}
