# Changelog

## [2.4.0](https://github.com/binh-vu/hugedict/tree/2.4.0) (2022-08-02)

[Full Changelog](https://github.com/binh-vu/hugedict/compare/2.3.3...2.4.0)

**Implemented enhancements:**

- improve rocksdb loader [\#14](https://github.com/binh-vu/hugedict/issues/14) ([\#16](https://github.com/binh-vu/hugedict/pull/16) ([binh-vu](https://github.com/binh-vu)))
- Ability to manually update the cache [\#11](https://github.com/binh-vu/hugedict/issues/11)

**Fixed**

- \[mrsw\] Invalid address when the URL is too long [\#8](https://github.com/binh-vu/hugedict/issues/8)

## [2.3.3](https://github.com/binh-vu/hugedict/tree/2.3.3) (2022-07-31)

[Full Changelog](https://github.com/binh-vu/hugedict/compare/2.3.2...2.3.3)

**Implemented enhancements:**

- Improve documentation [\#12](https://github.com/binh-vu/hugedict/pull/12) ([binh-vu](https://github.com/binh-vu))

**Fixed**

- `hugedict.parallel` cache function in big script requires more time to start a primary instance [\#10](https://github.com/binh-vu/hugedict/issues/10) ([\#13](https://github.com/binh-vu/hugedict/pull/13) ([binh-vu](https://github.com/binh-vu)))
- \[mrsw\] entry not found [\#9](https://github.com/binh-vu/hugedict/issues/9)
- PyLance reports private import usage for `hugedict.prelude` [\#7](https://github.com/binh-vu/hugedict/issues/7)

## [2.3.2](https://github.com/binh-vu/hugedict/releases/tag/2.3.2) - 2022-07-05

[Full Changelog](https://github.com/binh-vu/hugedict/compare/2.3.1...2.3.2)

**Fixed**

- PyLance reports private import usage for `hugedict.prelude` [\#7](https://github.com/binh-vu/hugedict/issues/7)

## [2.3.1](https://github.com/binh-vu/hugedict/releases/tag/2.3.1) - 2022-07-03

[Full Changelog](https://github.com/binh-vu/hugedict/compare/2.3.0...2.3.1)

**Added**

- Add prefix_extractor to hugedict.prelude ([9283234](https://github.com/binh-vu/hugedict/commit/9283234c33d92a2159aecba8809636c3c9a1517a))
- Add function to get RocksDB properties ([72f46391](https://github.com/binh-vu/hugedict/commit/72f46391018b813d778a31aee382afe2e1f2de56))

## [2.3.0](https://github.com/binh-vu/hugedict/releases/tag/2.3.0) - 2022-07-03

[Full Changelog](https://github.com/binh-vu/hugedict/compare/2.2.0...2.3.0)

**Added**

- Add seek iterators [#3](https://github.com/binh-vu/hugedict/issues/3) ([6971710](https://github.com/binh-vu/hugedict/commit/6971710577ac68d654f3c4ae91a7af5faf899bb6))

## [2.2.0](https://github.com/binh-vu/hugedict/releases/tag/2.2.0) - 2022-07-01

**Added**

- Add option to open rocksdb dict in secondary mode [(ef6b975](https://github.com/binh-vu/hugedict/commit/ef6b97529af9a662833fce025a85f7eb74e43090))
