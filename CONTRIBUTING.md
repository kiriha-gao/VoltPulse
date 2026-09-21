# Contributing to VoltPulse

Thank you for your interest in contributing to **VoltPulse**! We welcome contributions from power systems researchers, market analysts, and software engineers.

---

## 🧭 Code of Conduct & Contribution Standards

VoltPulse adheres to high scientific rigor, mathematical consistency, and reproducible engineering:
1. **Mathematical Soundness**: Energy storage dispatch must adhere to physical constraints (capacity, power, efficiency losses, and terminal SOC preservation). Naive LP without binary mutual exclusion variables $u_t$ is strictly prohibited.
2. **Data Integrity & Truthfulness**: Never fabricate real market data. When working with offline fixtures or generated benchmark data, always set `is_simulated = True` and use `synthetic://` source URLs.
3. **Transactional Safety**: Downstream analytics and reporting pipelines must write to staging directories (`.staging`) first and commit only upon 100% completion.

---

## 🛠️ Development Setup

1. **Fork and clone the repository**:
   ```bash
   git clone https://github.com/<your-username>/voltpulse.git
   cd voltpulse
   ```

2. **Create and activate a virtual environment**:
   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # Linux/macOS:
   source .venv/bin/activate
   ```

3. **Install dependencies and package in editable mode**:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   pip install -e ".[dev]"
   ```

---

## 🧪 Testing and Verification

Before submitting a Pull Request, all automated test suites and probe assertions must pass:

```bash
# 1. Run unit and integration tests (all 27 tests must pass)
pytest -v

# 2. Run original probe suite (Appendix C verification)
python scripts/run_probes.py

# 3. Run secondary edge-case probe suite (fault injection & rollback)
python scripts/run_extra_probes.py

# 4. Run automated acceptance audit
python scripts/acceptance.py
```

---

## 📝 Commit Convention

We follow [Conventional Commits](https://www.conventionalcommits.org/):
- `feat:` A new feature or model capability (e.g., `feat(model): add two-stage stochastic dispatch`)
- `fix:` A bug fix (e.g., `fix(qc): reject mismatched date columns`)
- `docs:` Documentation updates or paper references (e.g., `docs: update methodology with dual EFC`)
- `test:` Adding or updating tests and probes (e.g., `test(bess): add zero price boundary test`)
- `refactor:` Code restructuring without changing behavior (e.g., `refactor(pipeline): extract staging logic`)
- `chore:` Maintenance tasks or dependency updates (e.g., `chore(deps): bump scipy to 1.15.2`)

---

## 🚀 Pull Request Workflow

1. Create a feature branch: `git checkout -b feat/your-feature-name`
2. Commit your changes with clear messages.
3. Push to your fork: `git push origin feat/your-feature-name`
4. Open a Pull Request on GitHub against the `main` branch.
5. Ensure CI passes on all matrix runners (Ubuntu & Windows, Python 3.10–3.12).
