import { Route, Routes } from 'react-router';

import { StylePreview } from '../features/design/StylePreview';

/** Routes of the app. The style preview exists only in development builds (plan 003, step 4). */
export function AppRoutes() {
  return (
    <Routes>
      {import.meta.env.DEV ? <Route path="/design" element={<StylePreview />} /> : null}
      <Route path="*" element={<h1>Shibutzim</h1>} />
    </Routes>
  );
}
