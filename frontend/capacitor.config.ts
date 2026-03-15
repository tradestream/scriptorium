import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.scriptorium.app',
  appName: 'Scriptorium',
  webDir: 'build',
  // Allow the webview to make requests to the configured server
  server: {
    androidScheme: 'https',
    // cleartext is needed if server uses http (local network)
    cleartext: true,
  },
  ios: {
    contentInset: 'always',
    scrollEnabled: true,
  },
};

export default config;
