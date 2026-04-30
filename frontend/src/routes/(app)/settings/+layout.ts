import * as api from '$lib/api/client';
import type { LayoutLoad } from './$types';

export const load: LayoutLoad = async ({ parent }) => {
  const { user } = await parent();
  if (!user?.is_admin) {
    return { user, adminConfig: null };
  }
  try {
    const adminConfig = await api.getAdminConfig();
    return { user, adminConfig };
  } catch {
    return { user, adminConfig: null };
  }
};
