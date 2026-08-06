import { Link } from 'react-router-dom'

function HomePage() {
  return (
    <main>
      <header className="page-header">
        <div>
          <p className="eyebrow">
            Quant Research Platform
          </p>

          <h1>
            Research Overview
          </h1>

          <p className="subtitle">
            Platform health, data-quality
            controls and active investment
            research projects.
          </p>
        </div>
      </header>

      <section className="dashboard-card">
        <div className="card-header">
          <div>
            <h2>
              Platform monitoring
            </h2>

            <p>
              Pipeline and data-quality
              information will be displayed
              here.
            </p>
          </div>

          <span className="company-count">
            Setup in progress
          </span>
        </div>

        <div className="home-placeholder">
          The next step connects this page to
          the pipeline-status and aggregated
          quality-check APIs.
        </div>
      </section>

      <section className="home-projects">
        <div className="home-section-heading">
          <div>
            <p className="eyebrow">
              Investment theses
            </p>

            <h2>
              Research projects
            </h2>
          </div>
        </div>

        <div className="home-project-grid">
          <article className="home-project-card">
            <div>
              <span className="home-project-status">
                Active
              </span>

              <h3>
                AI Capital Cycle
              </h3>

              <p>
                CAPEX acceleration, cash-flow
                pressure, transition signals
                and eventual normalization.
              </p>
            </div>

            <Link
              className="home-project-link"
              to="/theses/capital-cycle"
            >
              Open thesis
            </Link>
          </article>

          <article className="home-project-card home-project-card-planned">
            <div>
              <span className="home-project-status">
                Planned
              </span>

              <h3>
                Nike Turnaround
              </h3>

              <p>
                Revenue stabilization,
                inventory, margins and brand
                recovery.
              </p>
            </div>

            <span className="home-project-link-disabled">
              Not configured
            </span>
          </article>

          <article className="home-project-card home-project-card-planned">
            <div>
              <span className="home-project-status">
                Planned
              </span>

              <h3>
                Memory Cycle
              </h3>

              <p>
                Pricing, inventories, supply,
                CAPEX and semiconductor-cycle
                conditions.
              </p>
            </div>

            <span className="home-project-link-disabled">
              Not configured
            </span>
          </article>
        </div>
      </section>
    </main>
  )
}

export default HomePage
