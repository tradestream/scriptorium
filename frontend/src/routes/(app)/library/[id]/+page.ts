import * as api from '$lib/api/client';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ params }) => {
  try {
    const library = await api.getLibrary(params.id);
    return { library };
  } catch {
    return { library: null };
  }
};
