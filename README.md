# Stratum Finder

**A desktop tool for *Elite Dangerous* that helps you find systems with valuable exobiology (Stratum Tectonicas and many other species) that may still have a free First Footfall bonus.**

It queries the [Spansh](https://spansh.co.uk) and [EDSM](https://www.edsm.net) databases, scores each candidate system by how likely the First Footfall is still unclaimed, builds an efficient travel route, and exports everything to CSV. It also tracks your collected samples, estimates your payout at Vista Genomics, and predicts which species you'll find on each planet in real time as you scan the system.

> First Footfall pays a **×5 bonus** on organic data. A single Stratum Tectonicas set is worth ~19M credits — or ~95M with First Footfall. This tool helps you find the systems where that bonus is most likely still available.

---

## Features

- **Multi-profile search** — pick multiple biology profiles via a dropdown + chips UI, search them all in one go with results merged by system and a "Profile" column showing which search(es) matched each row.
- **Candidate search** — combines three Spansh strategies (pre-Odyssey data, biological signals, pure Canonn filters) and verifies each system against EDSM.
- **First Footfall likelihood score** — each system gets a 0–100 score and a colour (🟢 70+, 🟡 40–69, 🔵 20–39, 🔴 <20) based on last-scan dates, mapping activity, and player presence.
- **17 biology profiles** — combined Stratum profile, eight individual high-value species (including Fonticulua Fluctus at 100M with First Footfall and Electricae at 31M, both on icy worlds), and broad group profiles (all Bacterium, all Tussock, etc.). Each profile shows its credit value next to the name.
- **Quiet-zone finder** — ranks the 20 nearest and 20 quietest regions of the galaxy with scrollable lists and sort-by-column-click, so you can pick a low-traffic area where footfalls are more likely free.
- **Configurable max distance from main star** — in Settings choose 50k / 100k / 250k / 500k ls or no limit, overriding profile defaults. Useful for huge multi-star systems with widely separated bodies.
- **Automatic route planning** — nearest-neighbour ordering with per-jump distances.
- **Inventory tracker** — logs your collected organisms, auto-imports completed scans from your Elite journal, prices them by species, lets you flag First Footfall, and totals your potential Vista Genomics payout.
- **Real-time biology tracker** — a companion window that reads your journal live and shows what's on each planet in your current system. After FSS you get instant species predictions from a 72-species database, DSS narrows candidates down to confirmed genera, and `ScanOrganic` marks samples as collected — with historic entries from your journal (last 5 days) pulled in automatically.
- **Elite journal integration** — auto-detects your current system and picks up biology scans in real time.
- **EDMC integration prompt** — at launch the app strongly recommends EDMC (one-click download) so your scans flow back into EDDN → Spansh / EDSM / Inara / Canonn for everyone.
- **Adaptive UI** — main window auto-sizes to fit any screen resolution from 1366×768 laptops up to 4K.
- **Bilingual UI (English / Русский)** — switch language from the top-right corner; everything including logs and data values is translated.
- **Four Elite-styled themes** — Elite Orange, Odyssey Blue, Midnight Purple, Ice Green.
- **Developer mode** *(optional build)* — search by system name with the Sol-distance limit disabled, override filter parameters, and stop a running search.

---

## Screenshots

<img width="1120" height="1085" alt="image" src="https://github.com/user-attachments/assets/616a07ff-bae9-4708-aa56-fa1502c6c956" />
<img width="1080" height="1148" alt="image" src="https://github.com/user-attachments/assets/9bf0b4b8-4d5e-499a-a7b6-922fd0602a50" />
<img width="1080" height="1148" alt="image" src="https://github.com/user-attachments/assets/c4fef4a7-6a31-435f-b832-a27d895dfe95" />

---

## Requirements

- **Windows 10 / 11 (64-bit)** for the pre-built executable.
- To build from source or run the scripts: **Python 3.10 or newer** (3.12 recommended).
- An internet connection (the app queries Spansh and EDSM).
- *Elite Dangerous* with **Odyssey** for on-foot exobiology.

---

## Installation

### Option A — Run the pre-built executable

1. Download the latest release archive from the [Releases](https://github.com/lynnel1/StratumFinder/releases) page.
2. Extract it anywhere (a path **without non-Latin characters** is safest).
3. Keep `StratumFinder.exe` and the `+data` folder **together** in the same directory.
4. Double-click `StratumFinder.exe`.

On first launch the app creates a `+data/user/` folder (your settings, inventory) and an `n/` folder (CSV results) next to the executable.

### Option B — Run from source

```bash
git clone https://github.com/lynnel1/StratumFinder.git
cd StratumFinder
pip install -r requirements.txt
python app.py
```

### Option C — Build your own executable

The repository includes two build scripts (Windows):

| Script              | Output                       | Developer mode             |
| ------------------- | ---------------------------- | -------------------------- |
| `build_exe.bat`     | `dist/StratumFinder-dev.exe` | **enabled** (Ctrl+Shift+D) |
| `build_release.bat` | `dist/StratumFinder.exe`     | disabled (hidden)          |

Just double-click the script you want. It installs dependencies, runs PyInstaller, and copies the `+data` folder next to the resulting `.exe`.

> **Note on antivirus warnings:** executables produced by PyInstaller are frequently flagged as `Win64:Malware-gen` by AVG, Avast, Windows Defender, and others. This is a **false positive** common to all PyInstaller apps, not actual malware. See [Antivirus false positives](#antivirus-false-positives) below.

---

## Quick start

1. **Settings → Elite Journal** — click **Auto** to detect your journal folder, then **Save path**.
   The default location is:
   ```
   %USERPROFILE%\Saved Games\Frontier Developments\Elite Dangerous\
   ```

2. **Search tab:**
   - Click **AUTO** to read your current system from the journal.
   - Pick **one or more biology profiles** from the dropdown (chips appear below; click ✕ to remove). Start with *All Stratum*.
   - Choose a **search radius** (1000 ly is a good default).
   - Click **ANALYZE POSITION** to see your distance from Sol, the local busyness score, and nearby quiet zones.
   - Click **START SEARCH**.

3. **Results tab:**
   - Filter by colour (🟢🟡🔵🔴) and by extra criteria (if they are available).
   - **Single-click** a row to copy the system name to your clipboard (paste it into the in-game Galaxy Map).
   - **Double-click** a row to open the system on EDSM.
   - Export the filtered list with **Export CSV**.

4. Fly out, collect your exobiology, and use the **Inventory tab** to track and value your finds. Open the **Real-time bio window** from the Search tab if you want live predictions and collection tracking while you scan.

---

## How the search works

For a selected biology profile and origin point, the app runs three Spansh queries and merges the results:

| Strategy | Filter                                                                                     |
| -------- | ------------------------------------------------------------------------------------------ |
| **A**    | Bodies last updated **before Odyssey** (2021-05-19) — never visited on foot or not mapped. |
| **B**    | Bodies with **biological signals ≥ 1**.                                                    |
| **D**    | Pure Canonn filter (subtype, atmosphere, temperature, gravity, pressure).                  |

Each unique candidate system is then verified against EDSM (mapping history, recent activity), scored, and ordered into a route. The result is written to a CSV in the `n/` folder, named `profile_YYYY-MM-DD_N.csv` (the counter `N` resets each day).

> **About First Footfall detection:** Elite Dangerous does **not** record First Footfall status in the journal at scan time — it only appears when you *sell* the data. Therefore every score is an **estimate** based on indirect signals (last-scan date, DSS activity, whether EDSM has data). The tool narrows down likely candidates; it cannot guarantee a free footfall.

> **Why the search takes a while:** Spansh and EDSM are community-run services maintained by volunteers on donation-funded infrastructure. To stay a good neighbour, the app queries them **sequentially** with small delays between requests (~0.8s between Spansh pages, ~0.1s per EDSM lookup) and honours `429` rate-limit responses with exponential back-off. Firing everything in parallel would shave off a few minutes at the cost of degrading the service for everyone — not worth it. For large searches (500+ candidates) the app shows you the ETA upfront so you can decide whether to narrow the radius.

---

## Biology profiles

Profiles are JSON files in `+data/profiles/`, grouped into three categories:

- **stratum** — *All Stratum* (Tectonicas, Paleas, Cucumisis, Frigus, and others) in one profile.
- **expensive** — individual high-value species: Fonticulua Fluctus, Electricae, Clypeus Margaritus, Osseus Pellebantus, Osseus Discus, Tussock Triticum, Tussock Pennata, Bacterium Omentum, Concha Renibus.
- **common** — broad group profiles: all Bacterium, all Tussock, all Cactoida, all Osseus, all Frutexa, all Concha, and a catch-all *Other exobiology*.

### Adding your own profile

Drop a new JSON file into `+data/profiles/expensive/` or `+data/profiles/common/`. The example below shows the structure; adjust the values to match your target species (see [Canonn Research](https://canonn.science/) for accurate exobiology parameters):

```json
{
  "name": "Species Name",
  "display_name": "Display Name",
  "category": "expensive",
  "description": "...",
  "value_credits_avg": 25000000,
  "value_credits_max_with_footfall": 125000000,
  "filters": {
    "subtype": ["High metal content world"],
    "atmosphere": ["Thin Carbon dioxide"],
    "temperature_min": 165,
    "temperature_max": 240,
    "gravity_max": 0.5,
    "pressure_max": 0.05,
    "is_landable": true,
    "distance_to_arrival_max": 50000
  },
  "local_check": {
    "atmospheres": ["Thin Carbon dioxide"],
    "temperature_min": 165,
    "gravity_max": 0.5
  }
}
```

Restart the app and the profile appears in the dropdown.

---

## Inventory

The Inventory tab tracks collected organisms as sample sets (1/3, 2/3, 3/3).

- **Add collection** — manually add a set, choosing 1–3 samples.
- **Import from journal** — scans your journal files and imports every completed organism (`ScanType=Analyse`) retroactively.
- **Recalculate prices** — fills in prices from the built-in species price reference (`+data/exobiology_prices.json`). Works with both English and Russian species names, since it matches on the Latin species word.
- **Double-click a row** — edit price and other fields for that organism.
- **Sell all (Vista Genomics)** — clears inventory and adds the total to your lifetime earnings.

---

## Real-time biology tracker

A companion window that opens from the Search tab and follows what you're doing in-game.

The tracker groups planets under the current system header and shows one line per species with a visual state:

| State | Icon | Trigger |
|-------|------|---------|
| Predicted | 🔍 | After FSS Scan + FSSBodySignals — species that fit the planet's parameters. |
| Genus confirmed | ✨ | After DSS `SAASignalsFound` — narrows the list to the exact genera the game confirmed. |
| Collected | ✅ | After `ScanOrganic Analyse` — a real collection on the surface. |
| Historic | 📚 | Pulled from your journal for the last 5 days — species you already collected earlier. |

Predictions are drawn from a 72-species database matched against subtype, atmosphere, temperature, gravity, pressure, volcanism, and required nearby star type (e.g. *Electricae Pluma* needs an A / White Dwarf / Neutron star in the system). Estimated prices are prefixed with `~` so you never confuse a forecast with a confirmed value.

The window persists between launches, but only if you're still in the same system — after a jump the tree resets and the tracker starts fresh.

---

## Configuration & data files

Everything user-editable lives in the `+data/` folder next to the executable:

| File / folder                  | Purpose                                                       |
| ------------------------------ | ------------------------------------------------------------- |
| `+data/profiles/`              | Biology search profiles (JSON).                               |
| `+data/bio/species.json`       | 72-species parameter database for real-time predictions.      |
| `+data/themes.json`            | Colour themes.                                                |
| `+data/quiet_zones.json`       | Quiet galactic regions with coordinates.                      |
| `+data/exobiology_prices.json` | Base credit values per species.                               |
| `+data/user/`                  | Your settings, inventory, and history (created on first run). |
| `n/`                           | Exported CSV result lists.                                    |

---

## Developer mode

Available only in the `build_exe.bat` (dev) build. Open it with **Ctrl+Shift+D** or from Settings.

- Enter a **system name** and the app fetches its coordinates automatically.
- The **Sol-distance minimum is ignored**, so you can test from anywhere.
- **Override** temperature / gravity / pressure / radius without editing profile files.
- Toggle search **strategies A/B/D** and EDSM verification.
- **Stop** a running search at any point.

---

## Antivirus false positives

PyInstaller-built executables are routinely flagged as generic malware (`Win64:Malware-gen`) by AVG, Avast, Windows Defender, and similar products. **This is a known false positive, not a real infection.** Free ways to deal with it (launching from VS Code triggers nothing at all):

- **Add an exclusion** for the app folder in your antivirus (simplest for personal use).
- **Build with `--onedir`** instead of `--onefile` — a folder of files triggers fewer detections than a single packed executable.
- **Submit the file** to your antivirus vendor's false-positive form (e.g. AVG's) to have it whitelisted.

Eliminating the warning for *everyone* requires a paid code-signing certificate; there is no fully free way to do that.

---

## Project structure

```
StratumFinder/
├── app.py                  # Entry point
├── build_exe.bat           # Build with developer mode
├── build_release.bat       # Build without developer mode
├── requirements.txt
├── core/
│   ├── finder.py           # Search engine (Spansh + EDSM + scoring)
│   ├── profiles.py         # Profile loading
│   ├── storage.py          # Settings, inventory, pricing
│   ├── zones.py            # Quiet-zone analysis
│   ├── journal.py          # Elite journal parser
│   ├── bio_predictor.py    # 72-species real-time prediction engine
│   └── csv_io.py           # CSV read/write
├── gui/
│   ├── main_window.py      # Main UI
│   ├── bio_window.py       # Real-time biology tracker
│   ├── dev_window.py       # Developer window (optional)
│   ├── theme.py            # Theme loading
│   └── i18n.py             # English / Russian translations
└── +data/                  # Editable data (profiles, themes, prices, zones, species)
```

---

## Tech stack

- **Python 3.10+** with **Tkinter** for the GUI (no external UI framework).
- **requests** + **urllib3** for API access.
- **PyInstaller** for building the executable.

---

## Acknowledgements

This tool would not be possible without the community projects whose data it relies on. If it's useful to you, please consider supporting them:

- **[Spansh](https://www.patreon.com/Spansh)** — the body/system database and search API behind every query.
- **[EDSM](https://www.patreon.com/edsm)** — galaxy map and scan history used for verification.
- **[Canonn Research Group](https://www.patreon.com/Canonn)** — the exobiology parameters all the search filters are based on.
- **[EDAstro](https://edastro.com)** — biology distribution maps used to build the quiet-zone list.
- **[Elite Observatory Core](https://github.com/Xjph/ObservatoryCore) by [Vithigar](https://www.patreon.com/vithigar)** — the species parameter database used by the real-time biology tracker is derived from the BioInsights plugin (MIT-licensed); the prediction logic is inspired by it. Full attribution in [LICENSE.md](LICENSE.md).

Please also run a data-relay tool (EDMC, EDDiscovery, EDDI, or Elite Observatory) while you play, so these databases keep growing for everyone.

---

## Disclaimer

This is an unofficial, fan-made tool. *Elite Dangerous* is a trademark of Frontier Developments plc. First Footfall availability is **estimated**, never guaranteed — Frontier may also change exobiology parameters or payouts at any time, in which case the profile JSONs may need updating.

---

## License

This software is released strictly for personal, non-commercial use only.

- **Commercial Use Prohibited:** Any form of monetization, sale, or generation of income using this code, its binaries, or any modified parts of this project is strictly forbidden.
- **API Terms:** Access to Spansh and EDSM APIs through this tool remains entirely subject to their respective terms of service.
- **Fair Use:** You are welcome to modify and use this tool for your own personal, free-of-charge exobiology expeditions in *Elite Dangerous*.
