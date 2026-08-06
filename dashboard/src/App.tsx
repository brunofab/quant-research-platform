import {
  Navigate,
  Route,
  Routes,
} from 'react-router-dom'

import AppShell from './layout/AppShell'
import CapitalCyclePage from './pages/CapitalCyclePage'
import DataQualityPage from './pages/DataQualityPage'
import HomePage from './pages/HomePage'

function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route
          index
          element={<HomePage />}
        />

        <Route
          path="data-quality"
          element={<DataQualityPage />}
        />

        <Route
          path="theses/capital-cycle"
          element={<CapitalCyclePage />}
        />

        <Route
          path="*"
          element={
            <Navigate
              to="/"
              replace
            />
          }
        />
      </Route>
    </Routes>
  )
}

export default App