import { createContext, useContext, type ReactNode } from 'react';

import type { AuthStore } from './AuthStore';
import type { ScheduleStore } from './ScheduleStore';
import type { RootStore } from './RootStore';

const StoreContext = createContext<RootStore | null>(null);

export interface StoreProviderProps {
  store: RootStore;
  children: ReactNode;
}

export function StoreProvider({ store, children }: StoreProviderProps) {
  return <StoreContext.Provider value={store}>{children}</StoreContext.Provider>;
}

export function useRootStore(): RootStore {
  const store = useContext(StoreContext);
  if (!store) throw new Error('useRootStore must be used inside a StoreProvider.');
  return store;
}

export function useAuthStore(): AuthStore {
  return useRootStore().auth;
}

export function useScheduleStore(): ScheduleStore {
  return useRootStore().schedule;
}
