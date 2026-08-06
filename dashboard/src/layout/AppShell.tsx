import {
  NavLink,
  Outlet,
} from 'react-router-dom'

function AppShell() {
  return (
    <div className="app-shell">
      <aside className="app-sidebar">
        <div className="app-brand">
          <span className="app-brand-mark">
            QR
          </span>

          <div>
            <strong>
              Quant Research
            </strong>

            <span>
              Thesis Platform
            </span>
          </div>
        </div>

        <nav
          className="app-navigation"
          aria-label="Main navigation"
        >
          <p className="app-navigation-label">
            Platform
          </p>

          <NavLink
            to="/"
            end
            className={({ isActive }) =>
              isActive
                ? (
                    'app-navigation-link ' +
                    'app-navigation-link-active'
                  )
                : 'app-navigation-link'
            }
          >
            Overview
          </NavLink>

          <NavLink
            to="/data-quality"
            className={({ isActive }) =>
              isActive
                ? (
                    'app-navigation-link ' +
                    'app-navigation-link-active'
                  )
                : 'app-navigation-link'
            }
          >
            Data quality
          </NavLink>

          <p className="app-navigation-label">
            Investment theses
          </p>

          <NavLink
            to="/theses/capital-cycle"
            className={({ isActive }) =>
              isActive
                ? (
                    'app-navigation-link ' +
                    'app-navigation-link-active'
                  )
                : 'app-navigation-link'
            }
          >
            Capital cycle
          </NavLink>
        </nav>

        <div className="app-sidebar-footer">
          Read-only research environment
        </div>
      </aside>

      <div className="app-content">
        <Outlet />
      </div>
    </div>
  )
}

export default AppShell
