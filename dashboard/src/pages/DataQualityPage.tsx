function DataQualityPage() {
  return (
    <main>
      <header className="page-header">
        <div>
          <p className="eyebrow">
            Platform controls
          </p>

          <h1>
            Data Quality
          </h1>

          <p className="subtitle">
            Detailed validation runs,
            individual checks and diagnostic
            findings.
          </p>
        </div>
      </header>

      <section className="dashboard-card">
        <div className="card-header">
          <div>
            <h2>
              Quality history
            </h2>

            <p>
              Historical runs and check
              diagnostics will be added here.
            </p>
          </div>
        </div>

        <div className="home-placeholder">
          The platform already stores the
          required run and check-result data.
        </div>
      </section>
    </main>
  )
}

export default DataQualityPage
