# Changelog

## [0.2.3](https://github.com/mlorentedev/garsync/compare/v0.2.2...v0.2.3) (2026-09-24)


### Bug Fixes

* **auth:** reject non-ASCII credentials, and archive the SEC-001 spec ([#111](https://github.com/mlorentedev/garsync/issues/111)) ([2c87539](https://github.com/mlorentedev/garsync/commit/2c8753975233d73bb69a636fbcb0ef608f4fb511))
* **guards:** land the two review findings whose PR merged before they did ([#113](https://github.com/mlorentedev/garsync/issues/113)) ([a9e883c](https://github.com/mlorentedev/garsync/commit/a9e883c419335ec940d5f6a9d23dec6c6bb524d0))


### Documentation

* **adr:** triage dependency alerts by reachability, and make an ignore state its trigger ([#110](https://github.com/mlorentedev/garsync/issues/110)) ([b6d65f4](https://github.com/mlorentedev/garsync/commit/b6d65f44a7a27ced5e3d799d81703f72adfd62f4))
* **architecture:** v2 target architecture, ADRs 007-013 and the scope register ([#99](https://github.com/mlorentedev/garsync/issues/99)) ([2c63905](https://github.com/mlorentedev/garsync/commit/2c6390543b506e037e1ab96b6c8848cb4e5a1273))
* make the repo's SSOTs singular (license, agent file, lessons) ([#102](https://github.com/mlorentedev/garsync/issues/102)) ([2ecc593](https://github.com/mlorentedev/garsync/commit/2ecc593337c082ae2d6bcf31a4263e50cebe0d25))

## [0.2.2](https://github.com/mlorentedev/garsync/compare/v0.2.1...v0.2.2) (2026-09-07)


### Bug Fixes

* **deps:** bump transitive sharp and esbuild to clear dependabot alerts (SEC-005) ([#63](https://github.com/mlorentedev/garsync/issues/63)) ([0e034cc](https://github.com/mlorentedev/garsync/commit/0e034cc0f750f941976f24a3e43f3a3531b311c7))


### Documentation

* **lessons:** capture dependabot group and npm scoped-override lessons from SEC-005 ([e4714e2](https://github.com/mlorentedev/garsync/commit/e4714e2496d189be045157fecb1ed76010125674))

## [0.2.1](https://github.com/mlorentedev/garsync/compare/v0.2.0...v0.2.1) (2026-09-07)


### Documentation

* apply /insights findings (2026-09-05) ([#53](https://github.com/mlorentedev/garsync/issues/53)) ([50e957a](https://github.com/mlorentedev/garsync/commit/50e957ab0c25d4b44a80bf194d0c72770d537034))
* split lessons into one file per lesson under docs/lessons/ ([#58](https://github.com/mlorentedev/garsync/issues/58)) ([946d481](https://github.com/mlorentedev/garsync/commit/946d481da6ec44696e00cd4e24e40b1c011bafb4))

## [0.2.0](https://github.com/mlorentedev/garsync/compare/v0.1.5...v0.2.0) (2026-09-06)


### Features

* **api:** add single-user auth gate and API hardening (SEC-001) ([#44](https://github.com/mlorentedev/garsync/issues/44)) ([1f6535f](https://github.com/mlorentedev/garsync/commit/1f6535fa2c705b882171aba6565070d912728114))

## [0.1.5](https://github.com/mlorentedev/garsync/compare/v0.1.4...v0.1.5) (2026-08-12)


### Bug Fixes

* skip add-to-project for dependabot PRs and configure dependabot to ignore major astro bumps ([a513d7e](https://github.com/mlorentedev/garsync/commit/a513d7ee9ed925fc04b9bfa8ba19216e964d9a16))


### Documentation

* add lesson about ruff 0.16.2 cascading lint rules ([ddc9d03](https://github.com/mlorentedev/garsync/commit/ddc9d03311d36d912d23d979d4d68fd68759555c))

## [0.1.4](https://github.com/mlorentedev/garsync/compare/v0.1.3...v0.1.4) (2026-05-29)


### Documentation

* migrate project-bound knowledge into docs/ (KPM-013) ([#4](https://github.com/mlorentedev/garsync/issues/4)) ([16845bb](https://github.com/mlorentedev/garsync/commit/16845bb31ff5692fa02bb02640d7ef9270189e4b))

## [0.1.3](https://github.com/mlorentedev/garsync/compare/v0.1.2...v0.1.3) (2026-05-29)


### Bug Fixes

* **test:** make integration stats-summary assertion date-independent ([#5](https://github.com/mlorentedev/garsync/issues/5)) ([2d730b2](https://github.com/mlorentedev/garsync/commit/2d730b27119f67baef5d77d12a54aebe91480074))

## [0.1.2](https://github.com/mlorentedev/garsync/compare/v0.1.1...v0.1.2) (2026-03-08)


### Bug Fixes

* resolve Starlight build error by fixing image path and copying favicon ([08175af](https://github.com/mlorentedev/garsync/commit/08175afe6f7669f895bfcd05e12381da0343504a))

## [0.1.1](https://github.com/mlorentedev/garsync/compare/v0.1.0...v0.1.1) (2026-03-08)


### Bug Fixes

* complete documentation files and content config for Starlight ([87a7acb](https://github.com/mlorentedev/garsync/commit/87a7acb62ea94c1c5da69eb06596cc4dfc54558f))
* resolve CI linting, type errors, and missing lockfiles ([d020ef3](https://github.com/mlorentedev/garsync/commit/d020ef3e47a2750ace28ccda265564b8e492eea4))

## 0.1.0 (2026-03-08)


### Features

* dashboard cleanup — remove dead data components, add e2e smoke test ([d338da6](https://github.com/mlorentedev/garsync/commit/d338da6e3f745b1eb2c02e4e2bb6a6de14f7f0be))
* initial project — Garmin sync + FastAPI backend + Astro dashboard ([173d0fc](https://github.com/mlorentedev/garsync/commit/173d0fc84dbd42fbb074bf475a7dd11af0473b7b))
* release v1.1.0 with security hardening, UX polish, and documentation site ([fb08042](https://github.com/mlorentedev/garsync/commit/fb0804270a77448da1b47bf279fdcd43018c5450))
