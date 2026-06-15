# Changelog

## [0.3.4](https://github.com/huh-itmo-y27/PARDON/compare/v0.3.3...v0.3.4) (2026-06-15)


### Bug Fixes

* changed pods resources ([#49](https://github.com/huh-itmo-y27/PARDON/issues/49)) ([e2f46ce](https://github.com/huh-itmo-y27/PARDON/commit/e2f46cecf679fb58a3d3bc35439e29e8b8fdb97a))

## [0.3.3](https://github.com/huh-itmo-y27/PARDON/compare/v0.3.2...v0.3.3) (2026-06-12)


### Bug Fixes

* cd image rebuild triggers ([#42](https://github.com/huh-itmo-y27/PARDON/issues/42)) ([e6085be](https://github.com/huh-itmo-y27/PARDON/commit/e6085be9a661854a6e6796638ca4f415f307bfb8))

## [0.3.2](https://github.com/huh-itmo-y27/PARDON/compare/v0.3.1...v0.3.2) (2026-06-12)


### Bug Fixes

* k8s data artifact URLs and mlflow resources ([#40](https://github.com/huh-itmo-y27/PARDON/issues/40)) ([eb5d545](https://github.com/huh-itmo-y27/PARDON/commit/eb5d5456c4bf6a221347f7555d20f7869fde5234))

## [0.3.1](https://github.com/huh-itmo-y27/PARDON/compare/v0.3.0...v0.3.1) (2026-06-12)


### Bug Fixes

* fixed sync and mlflow pods ([#38](https://github.com/huh-itmo-y27/PARDON/issues/38)) ([4e4dd07](https://github.com/huh-itmo-y27/PARDON/commit/4e4dd07121f4da9d8effc21980c6c3457ac4ed1b))

## [0.3.0](https://github.com/huh-itmo-y27/PARDON/compare/v0.2.0...v0.3.0) (2026-06-11)


### Features

* add dvc SKAB data retrieval ([#34](https://github.com/huh-itmo-y27/PARDON/issues/34)) ([f9083f1](https://github.com/huh-itmo-y27/PARDON/commit/f9083f1b1bcbc2a7d0336d0244fb2d6805b8e8b0))

## [0.2.0](https://github.com/huh-itmo-y27/PARDON/compare/v0.1.4...v0.2.0) (2026-06-04)


### Features

* implement tcn_ae and vae models ([#31](https://github.com/huh-itmo-y27/PARDON/issues/31)) ([58b93d5](https://github.com/huh-itmo-y27/PARDON/commit/58b93d56a5046fd6cf8d09c8a2cfb7d2e4a585d3))

## [0.1.4](https://github.com/huh-itmo-y27/PARDON/compare/v0.1.3...v0.1.4) (2026-06-02)


### Documentation

* expand comprehensive overview, local setup instructions ([#29](https://github.com/huh-itmo-y27/PARDON/issues/29)) ([355aa31](https://github.com/huh-itmo-y27/PARDON/commit/355aa3137dfebbd16ca35e79ef008ddd8ca3e4fc))

## [0.1.3](https://github.com/huh-itmo-y27/PARDON/compare/v0.1.2...v0.1.3) (2026-05-30)


### Bug Fixes

* **cd:** dockerfile ([#25](https://github.com/huh-itmo-y27/PARDON/issues/25)) ([094c3e2](https://github.com/huh-itmo-y27/PARDON/commit/094c3e2d5f7009de9f5ae170e2005ff8e1c1335b))

## [0.1.2](https://github.com/huh-itmo-y27/PARDON/compare/v0.1.1...v0.1.2) (2026-05-30)


### Bug Fixes

* **cd:** fix bugs with .toml release ([#23](https://github.com/huh-itmo-y27/PARDON/issues/23)) ([0afa695](https://github.com/huh-itmo-y27/PARDON/commit/0afa695935d2d98379a408da049b2e5b45c6d9fd))

## [0.1.1](https://github.com/huh-itmo-y27/PARDON/compare/v0.1.0...v0.1.1) (2026-05-30)


### Bug Fixes

* clarify quick start documentation ([#21](https://github.com/huh-itmo-y27/PARDON/issues/21)) ([8a63146](https://github.com/huh-itmo-y27/PARDON/commit/8a63146549cf3809ce2ffece9bf5beca4cc364fe))

## [0.1.0](https://github.com/huh-itmo-y27/PARDON/compare/v0.0.1...v0.1.0) (2026-05-30)


### Features

* add dvc setup ([#2](https://github.com/huh-itmo-y27/PARDON/issues/2)) ([7741a46](https://github.com/huh-itmo-y27/PARDON/commit/7741a46d432834bd9239b3cf576d17556d54031a))
* add initial anomaly detection EDA ([#1](https://github.com/huh-itmo-y27/PARDON/issues/1)) ([db881cf](https://github.com/huh-itmo-y27/PARDON/commit/db881cf99ee18f33accf2f435ab8899c3192e599))
* add model selection in grafana metrics ([#15](https://github.com/huh-itmo-y27/PARDON/issues/15)) ([a69095c](https://github.com/huh-itmo-y27/PARDON/commit/a69095c0b4b2641743b2005f5fcb75dbe27f640e))
* add prometheus metrics store + grafana dashboards ([#8](https://github.com/huh-itmo-y27/PARDON/issues/8)) ([e6e6efc](https://github.com/huh-itmo-y27/PARDON/commit/e6e6efc646e8eccfeab154ac62021dfc02228d55))
* add web UI with retrain and recent runs ([#14](https://github.com/huh-itmo-y27/PARDON/issues/14)) ([b09abaf](https://github.com/huh-itmo-y27/PARDON/commit/b09abafcf1fc6fb11fa503b45cdc8971fca87dbe))
* introduce mlflow pipelines ([#3](https://github.com/huh-itmo-y27/PARDON/issues/3)) ([3137837](https://github.com/huh-itmo-y27/PARDON/commit/3137837e3383a262b736db0acb89cf596a226a9f))


### Bug Fixes

* **cd:** added ghcr image pull secrets ([#12](https://github.com/huh-itmo-y27/PARDON/issues/12)) ([bfe5223](https://github.com/huh-itmo-y27/PARDON/commit/bfe522350756a0199ef0efa1ffcf62d660137447))
* **cd:** builded multi-arch Docker image ([#13](https://github.com/huh-itmo-y27/PARDON/issues/13)) ([a8c07c5](https://github.com/huh-itmo-y27/PARDON/commit/a8c07c5503686127ac2148aa8c2c09d21410b37e))
* **cd:** fixed bugs rith publish to ghcr ([#17](https://github.com/huh-itmo-y27/PARDON/issues/17)) ([3cbaabe](https://github.com/huh-itmo-y27/PARDON/commit/3cbaabee77caeaff3b2e1b5e5d369b1784f15b78))


### Documentation

* add mkdocs pages ([#7](https://github.com/huh-itmo-y27/PARDON/issues/7)) ([530b202](https://github.com/huh-itmo-y27/PARDON/commit/530b2023f948010a9b894decb3f87dabf2ec9e0d))
* add PARDON logo SVG and update project description ([#10](https://github.com/huh-itmo-y27/PARDON/issues/10)) ([3c711b0](https://github.com/huh-itmo-y27/PARDON/commit/3c711b082fd3d19a839a41d97302805be3392f3d))
