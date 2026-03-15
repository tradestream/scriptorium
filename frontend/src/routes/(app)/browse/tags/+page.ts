import * as api from '$lib/api/client';

export async function load() {
  const tags = await api.getTags(0, 1000);
  return { tags };
}
