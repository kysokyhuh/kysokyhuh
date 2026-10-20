name: Update monochrome contributions

on:
  workflow_dispatch:
  schedule:
    - cron: "17 3 * * *" # Daily, UTC

permissions:
  contents: write

jobs:
  heatmap:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Generate light and dark SVGs
        run: python scripts/generate_heatmap.py
      - name: Commit updated SVGs
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add assets/contributions-light.svg assets/contributions-dark.svg
          if ! git diff --cached --quiet; then
            git commit -m "chore: refresh contribution heatmap"
            git push
          fi

