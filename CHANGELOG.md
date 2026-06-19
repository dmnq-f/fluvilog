# Changelog

## [0.6.0](https://github.com/dmnq-f/fluvilog/compare/v0.5.1...v0.6.0) (2026-06-19)


### Features

* **api:** report package version in /api/health ([f482ef2](https://github.com/dmnq-f/fluvilog/commit/f482ef2953f56f8ea04b7349e36d11cad99f3616))


### Bug Fixes

* **serve-api:** apply timestamped log format to uvicorn ([23b86f4](https://github.com/dmnq-f/fluvilog/commit/23b86f4caf1338158f02cd40a7de2f24cb7b7f2d))

## [0.5.1](https://github.com/dmnq-f/fluvilog/compare/v0.5.0...v0.5.1) (2026-06-17)


### Performance Improvements

* **collect:** poll today-only when caught up ([9ad35c3](https://github.com/dmnq-f/fluvilog/commit/9ad35c3f3259849353119bd95ce090d37bab29d1))

## [0.5.0](https://github.com/dmnq-f/fluvilog/compare/v0.4.0...v0.5.0) (2026-06-17)


### Features

* **wgmn:** cap outbound request rate with a token bucket ([31ad190](https://github.com/dmnq-f/fluvilog/commit/31ad190ff72c1565964e5e468a2d867a5529bd42))

## [0.4.0](https://github.com/dmnq-f/fluvilog/compare/v0.3.0...v0.4.0) (2026-06-17)


### Features

* add configurable log level and broaden log coverage ([4662b67](https://github.com/dmnq-f/fluvilog/commit/4662b6782ed64c60edc22b6f6926d054b5526320))
* **api:** add liveness and db readiness health endpoints ([7a56750](https://github.com/dmnq-f/fluvilog/commit/7a56750f0f31c9a63c4d024554fac00a2384d63e))
* **api:** expose recording_since on station responses ([5fb1c71](https://github.com/dmnq-f/fluvilog/commit/5fb1c71072aba9e64e77b104ca0b227668ed1515))
* select parameters via --parameter, default to all ([75669fa](https://github.com/dmnq-f/fluvilog/commit/75669faf3bf2585554fea6375abb30cefe87017e))

## [0.3.0](https://github.com/dmnq-f/fluvilog/compare/v0.2.0...v0.3.0) (2026-06-15)


### Features

* add backfill subcommand for historical date ranges ([552c303](https://github.com/dmnq-f/fluvilog/commit/552c303371d0a667f5c5f3f130baeec407e18884))
* back-fill collect gaps by resuming from the stored watermark ([19089c4](https://github.com/dmnq-f/fluvilog/commit/19089c4039103b8c5f337587e2ac9b0fdc0e6432))
* warn when a backfill range predates a station's start ([054baaf](https://github.com/dmnq-f/fluvilog/commit/054baaf94b47ff786db7821e437545bb09cfb93f))

## [0.2.0](https://github.com/dmnq-f/fluvilog/compare/v0.1.1...v0.2.0) (2026-06-15)


### Features

* add FLUVILOG_* environment configuration layer ([8ed4bff](https://github.com/dmnq-f/fluvilog/commit/8ed4bfff46d16371434a6c1936aa574f1adfd1cf))


### Documentation

* add docker compose stack example ([8fd58c8](https://github.com/dmnq-f/fluvilog/commit/8fd58c8a209052dcd8bd96c05b6faed05fbf4fe6))

## [0.1.1](https://github.com/dmnq-f/fluvilog/compare/v0.1.0...v0.1.1) (2026-06-15)


### Bug Fixes

* add missing metadata for pypi package ([5837e98](https://github.com/dmnq-f/fluvilog/commit/5837e98589c8365ff1799dbcdef77e0420fc10a4))

## 0.1.0 (2026-06-15)


### ⚠ BREAKING CHANGES

* add read surface and optional HTTP API for stored readings

### Features

* add read surface and optional HTTP API for stored readings ([1bf817d](https://github.com/dmnq-f/fluvilog/commit/1bf817d1a0d90931560c1a78bd9ac3343ad068ae))


### Documentation

* add README.md ([a48b9e0](https://github.com/dmnq-f/fluvilog/commit/a48b9e024d66673e9710fa7b2bd99e1deaca0334))
* update relevant WGMN + service links ([19fad99](https://github.com/dmnq-f/fluvilog/commit/19fad995c2be60e5edd4bf94412344332b23d94a))
