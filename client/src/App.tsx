import { MantineProvider } from '@mantine/core';
import { Notifications } from '@mantine/notifications';
import { useEffect, useState } from 'react';
import { BrowserRouter } from 'react-router';

import { AppRoutes } from './routes/AppRoutes';
import { RootStore } from './stores/RootStore';
import { StoreProvider } from './stores/StoreContext';
import { theme } from './theme';

export interface AppProps {
  /** Tests pass a store with a fake API; the app builds its own. */
  store?: RootStore;
}

export function App({ store: given }: AppProps) {
  const [store] = useState(() => given ?? new RootStore());

  useEffect(() => {
    void store.auth.restore();
  }, [store]);

  return (
    <MantineProvider theme={theme} forceColorScheme="light">
      <Notifications position="top-right" />
      <StoreProvider store={store}>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </StoreProvider>
    </MantineProvider>
  );
}
