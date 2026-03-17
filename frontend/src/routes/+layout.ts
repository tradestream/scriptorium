import { redirect } from '@sveltejs/kit';
import * as api from '$lib/api/client';
import type { LayoutLoad } from './$types';

export const ssr = false;

export const load: LayoutLoad = async ({ url }) => {
  // On Capacitor native with no server URL configured, show the setup screen.
  // Capacitor injects window.Capacitor at runtime — no import needed.
  if (typeof window !== 'undefined') {
    const cap = (window as any).Capacitor;
    if (cap?.isNativePlatform?.() && !api.getServerUrl()) {
      return { needsServerSetup: true, user: null, libraries: [], shelves: [] };
    }
  }

  const token = api.getAuthToken();
  const isAuthPage = url.pathname.startsWith('/auth');

  if (!token && !isAuthPage) {
    redirect(302, '/auth/login');
  }

  if (token && isAuthPage) {
    redirect(302, '/');
  }

  let user = null;
  let libraries = [];
  let shelves = [];
  let pinnedCollections = [];

  let absUrl: string | null = null;

  if (token) {
    try {
      [user, libraries, shelves, pinnedCollections] = await Promise.all([
        api.getCurrentUser(),
        api.getLibraries(),
        api.getShelves(),
        api.getCollections().then(cols => cols.filter(c => c.is_pinned)).catch(() => []),
      ]);
    } catch (error) {
      console.error('Failed to load initial data:', error);
      api.setAuthToken(null);
      if (!isAuthPage) {
        redirect(302, '/auth/login');
      }
    }
    // Fetch ABS URL separately — non-critical, don't fail auth if it errors
    try {
      const absStatus = await api.getAbsStatus();
      if (absStatus.connected && absStatus.server_url) absUrl = absStatus.server_url;
    } catch { /* ABS not configured */ }
  }

  return {
    needsServerSetup: false,
    user,
    libraries,
    shelves,
    pinnedCollections,
    absUrl,
  };
};
