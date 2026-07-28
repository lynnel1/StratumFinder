# StratumFinder License

Copyright (C) 2026 Vladislavs Hripacs (CMDR Lynnel)

This program is free software: you can redistribute it and/or modify it
under the terms of the **GNU Affero General Public License** as published
by the Free Software Foundation, version 3 of the License.

This program is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero
General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program. If not, see <https://www.gnu.org/licenses/agpl-3.0.html>.

---

## Why AGPL?

AGPL is a strong copyleft license. It requires that:

- Anyone who **distributes** this software (modified or not) must also
  publish their source code under AGPL-3.0.
- Anyone who **runs a public network service** based on this software
  must make their source code available to users of that service.

In plain terms: you are free to use, modify, and share StratumFinder,
but you cannot take this code, build a closed-source product on top
of it, and keep your changes private.

## What you CAN do

- Use StratumFinder for any purpose (personal, commercial, educational)
- Read, study, and modify the source code
- Share copies of the original or modified versions
- Build the executable yourself

## What you MUST do if you redistribute or modify

- Make your modified source code available under AGPL-3.0
- Include this license file with any copy
- Preserve copyright notices

## What you CANNOT do

- Distribute modified versions under a different (closed-source) license
- Remove copyright notices or this license text

## Authorship verification

This software contains embedded authorship signatures throughout the
source code and in the data files it generates. These signatures allow
identification of derivative works and unauthorized distributions, even
when surface-level modifications are made (renaming, refactoring,
translation, recompilation).

Any modification attempting to remove or alter these signatures
constitutes an additional copyright violation under applicable law,
separate from the AGPL-3.0 license breach itself.

## Reporting violations

If you encounter a distribution that you believe violates this license,
please report it to:

- **Email:** painter28266@gmail.com
- **In-game CMDR:** Lynnel

The author actively monitors public distributions of exobiology-related
tools and CSV exports, and reserves all rights under AGPL-3.0 and
applicable copyright law (Berne Convention, DMCA, and national
copyright statutes). Violators automatically lose all rights granted
by this license under AGPL-3.0 Section 8, and may be required to:

- Cease distribution of the infringing software
- Publish their modified source code under AGPL-3.0
- Pay statutory damages and legal fees

## Full text

See <https://www.gnu.org/licenses/agpl-3.0.txt> for the complete license.

---

## Third-party data and services

StratumFinder uses data from the following services:

- [Spansh](https://spansh.co.uk) — body and system database (public API)
- [EDSM](https://www.edsm.net) — galaxy map (public API)
- [Canonn Research Group](https://canonn.science) — exobiology parameters
- [EDAstro / CMDR Orvidius](https://edastro.com) — biology distribution maps

## Third-Party Notices — MIT-licensed code

The species parameter database used by StratumFinder's biology
prediction (`+data/bio/species.json`) is **derived from data used in
the BioInsights plugin** for **Elite Observatory Core** by Vithigar
(GitHub: [Xjph](https://github.com/Xjph)). The prediction logic in
`core/bio_predictor.py` is **inspired by** the same plugin. Elite
Observatory Core is released under the MIT License.

The MIT License is compatible with AGPL-3.0. As required by the MIT
License, the original copyright notice is preserved below:

```
MIT License

Copyright (c) Vithigar (Xjph)

Permission is hereby granted, free of charge, to any person obtaining
a copy of this software and associated documentation files (the
"Software"), to deal in the Software without restriction, including
without limitation the rights to use, copy, modify, merge, publish,
distribute, sublicense, and/or sell copies of the Software, and to
permit persons to whom the Software is furnished to do so, subject to
the following conditions:

The above copyright notice and this permission notice shall be
included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NON-INFRINGEMENT.
IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
```

Full source code of Elite Observatory Core is available at:
<https://github.com/Xjph/ObservatoryCore>

If you find the biology-prediction feature useful, please consider
supporting the original author on Patreon:
<https://www.patreon.com/vithigar>

*Elite Dangerous* is a trademark of Frontier Developments plc.
StratumFinder is an unofficial, fan-made tool not endorsed by Frontier.
