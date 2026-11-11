import { Container } from '@mantine/core';
import { observer } from 'mobx-react-lite';
import { Navigate, Outlet, Route, Routes } from 'react-router';

import { ComingSoon } from '../components/ComingSoon';
import { LoadingState } from '../components/StateViews';
import { LoginScreen } from '../features/auth/LoginScreen';
import { StylePreview } from '../features/design/StylePreview';
import { MyShifts } from '../features/me/MyShifts';
import { AppShell } from '../features/shell/AppShell';
import { useAuthStore } from '../stores/StoreContext';

/** Anyone logged in gets the shell; everybody else goes to the login screen. */
const RequireAuth = observer(function RequireAuth() {
  const auth = useAuthStore();
  if (!auth.isAuthenticated) return <Navigate to="/login" replace />;
  return <AppShell />;
});

/** The role only hides what it cannot use; the server is still the real guard. */
const RequireManager = observer(function RequireManager() {
  const auth = useAuthStore();
  if (!auth.isManager) return <Navigate to={auth.homePath} replace />;
  return <Outlet />;
});

const Fallback = observer(function Fallback() {
  const auth = useAuthStore();
  return <Navigate to={auth.isAuthenticated ? auth.homePath : '/login'} replace />;
});

/** Routes of the app, split by role (architecture §9). The style preview exists only in development. */
export const AppRoutes = observer(function AppRoutes() {
  const auth = useAuthStore();
  if (auth.isRestoring) {
    return (
      <Container size={640} py="xl">
        <LoadingState rows={2} />
      </Container>
    );
  }
  return (
    <Routes>
      {import.meta.env.DEV ? <Route path="/design" element={<StylePreview />} /> : null}
      <Route
        path="/login"
        element={auth.isAuthenticated ? <Navigate to={auth.homePath} replace /> : <LoginScreen />}
      />
      <Route element={<RequireAuth />}>
        <Route path="/me/shifts" element={<MyShifts />} />
        <Route path="/me/availability" element={<ComingSoon title="Availability" />} />
        <Route path="/me/pay" element={<ComingSoon title="My pay" />} />
        <Route path="/manager" element={<RequireManager />}>
          <Route path="schedule" element={<ComingSoon title="Schedule" />} />
          <Route path="pay" element={<ComingSoon title="Team pay" />} />
        </Route>
      </Route>
      <Route path="*" element={<Fallback />} />
    </Routes>
  );
});
