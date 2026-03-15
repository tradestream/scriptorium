import * as api from '$lib/api/client';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ params }) => {
  try {
    const collection = await api.getCollection(Number(params.id));
    return { collection };
  } catch {
    return { collection: null };
  }
};
