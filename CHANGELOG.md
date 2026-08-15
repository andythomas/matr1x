# CHANGELOG

## v8.5.0 (2026-08-14)

### Bug fixes

* fix(Keithley): fix delay commands (2400) and input resistance (6500) *by Dominik Kriegner* ([`1b8c394`](https://github.com/andythomas/matr1x/commit/1b8c3940052f7dd13d00c4b31ddd0dbae8a517d4))

* fix(ty): remove unused rule (#84) *by Andy Thomas* ([`d0cdf1d`](https://github.com/andythomas/matr1x/commit/d0cdf1dc69fcaabd387dbebd7f38a27d5a821168))

* fix: address html escaped syntax in LSP responses (#72) *by Andy Thomas* ([`180c5f6`](https://github.com/andythomas/matr1x/commit/180c5f60205964b839898666dcc947d9bbd52479))

* fix(matrix-script): ensure correct line highlighted (#60) *by Dominik Kriegner* ([`2d71598`](https://github.com/andythomas/matr1x/commit/2d7159844db937c509b3035d718d3da0f0588e7d))

* fix(matrix-script): ensure correct line highlighted *by Dominik Kriegner* ([`2d71598`](https://github.com/andythomas/matr1x/commit/2d7159844db937c509b3035d718d3da0f0588e7d))

* fix(ConfigEditor): boolean representation in checkboxes (#57) *by Dominik Kriegner* ([`4e1421b`](https://github.com/andythomas/matr1x/commit/4e1421ba8b85f20836feb55b9a0aecc9fb245cfb))

* fix(ConfigEditor): prevent editing config section headers (#50) *by Dominik Kriegner* ([`26ce1b2`](https://github.com/andythomas/matr1x/commit/26ce1b22f5dda2535d0e6ad79ef6b5f1e2faa97e))

* fix(CI): PR check action (#32) *by Andy Thomas* ([`5a5e7b0`](https://github.com/andythomas/matr1x/commit/5a5e7b0d85150605e747b48e18ba88e5aa219df0))

* fix(CI): PR check action *by Andy Thomas* ([`5a5e7b0`](https://github.com/andythomas/matr1x/commit/5a5e7b0d85150605e747b48e18ba88e5aa219df0))

* fix(elabftw): support and suggest ElabFTW server >=5.3.0 (#23) *by Dominik Kriegner* ([`62a6f9d`](https://github.com/andythomas/matr1x/commit/62a6f9d6b88d7d6fca5bafebfcdcccd5d03653ee))

* fix(elabftw): support and suggest ElabFTW server >=5.3.0 *by Dominik Kriegner* ([`62a6f9d`](https://github.com/andythomas/matr1x/commit/62a6f9d6b88d7d6fca5bafebfcdcccd5d03653ee))

* fix(MeasurementThread): keep an error as an error (#12) *by Dominik Kriegner* ([`9edad13`](https://github.com/andythomas/matr1x/commit/9edad13cf65bb0ac1d0b93687002c452a87b9093))

* fix(MeasurementThread): keep an error as an error *by Dominik Kriegner* ([`9edad13`](https://github.com/andythomas/matr1x/commit/9edad13cf65bb0ac1d0b93687002c452a87b9093))

* fix: address typo and recover workflows (#17) *by Andy Thomas* ([`f7c329c`](https://github.com/andythomas/matr1x/commit/f7c329c0a124c7c3302ee2a6ef9126c889831b70))

### Build system

* build(commit-hooks): add ty and ruff pre-commit hooks (#27) *by Dominik Kriegner* ([`52d8919`](https://github.com/andythomas/matr1x/commit/52d89195167b98ea9d18aaca378957d5ee547326))

### Documentation

* docs: add uv update detail (#91) *by Andy Thomas* ([`0733c4f`](https://github.com/andythomas/matr1x/commit/0733c4f792e78f095dd1caefa7696ed59c4ffd2e))

* docs: update great-docs and add more content (#70) *by Andy Thomas* ([`8fbda6a`](https://github.com/andythomas/matr1x/commit/8fbda6a50ccabee20d05a4d5f1956c823c92248e))

* docs: properly format deprecation warning and explain lifecycle (#35) *by Andy Thomas* ([`b1f5b5f`](https://github.com/andythomas/matr1x/commit/b1f5b5fa4cfa8671e309ef2083a260271b228dd6))

* docs: add initial user-manual (#31) *by Andy Thomas* ([`bb1ae60`](https://github.com/andythomas/matr1x/commit/bb1ae60e96b20bd866c86285aee1391058702746))

### Features

* feat: show execthread logs in log-window (#71) *by Andy Thomas* ([`29e8d50`](https://github.com/andythomas/matr1x/commit/29e8d50cf2a22525dcc0e394dedb063306a443ac))

* feat(config): deprecate matr1x.install.root_path (#46) *by Andy Thomas* ([`c7e7759`](https://github.com/andythomas/matr1x/commit/c7e77593049b93b0c6485c21eb9d3afdd109503f))

* feat(config): deprecate matr1x.install.root_path *by Andy Thomas* ([`c7e7759`](https://github.com/andythomas/matr1x/commit/c7e77593049b93b0c6485c21eb9d3afdd109503f))

* feat(System): support class-based system definitions (#29) *by Dominik Kriegner* ([`7a62504`](https://github.com/andythomas/matr1x/commit/7a6250412450804f9a9000a037e5586f9df6e66b))

* feat(System): support class-based system definitions *by Dominik Kriegner* ([`7a62504`](https://github.com/andythomas/matr1x/commit/7a6250412450804f9a9000a037e5586f9df6e66b))

* feat(ConfigEdit): Add new visa_resource field type (#28) *by Dominik Kriegner* ([`165312a`](https://github.com/andythomas/matr1x/commit/165312afbc758bb21d3e0000b6c73423aac085cf))

* feat(ConfigEdit): Add new visa_resource field type *by Dominik Kriegner* ([`165312a`](https://github.com/andythomas/matr1x/commit/165312afbc758bb21d3e0000b6c73423aac085cf))

* feat(system): subsystem access and auto-complete (#19) *by Andy Thomas* ([`7916717`](https://github.com/andythomas/matr1x/commit/791671760afcd84968ef4900241148edc4c54ed2))

### Unknown

* move mime and desktop files (#90) *by Andy Thomas* ([`c372417`](https://github.com/andythomas/matr1x/commit/c3724175f238bdeb0654ca1e702ebac141b16150))

* ruff action fixes *by pheowl* ([`0eb10b9`](https://github.com/andythomas/matr1x/commit/0eb10b9b3d641ce978e4ab994c62a46be5373e96))

* sync to PR 1859 in ifwlib repo *by Andy Thomas* ([`3be9875`](https://github.com/andythomas/matr1x/commit/3be9875d7cb921450497d3249a7ccc24edbb8541))

## v8.4.1 (2026-07-15)

### Bug fixes

* fix(matrix): fix for "print_to_comment=true" *by Andy Thomas* ([`ec20d0d`](https://github.com/andythomas/matr1x/commit/ec20d0dc51e98050f8fec1d2f00f122c3a167943))

## v8.4.0 (2026-07-15)

### Bug fixes

* fix(controlwindow): remove double calling of System.set in legacy code (#1855) *by Dominik Kriegner* ([`41c0d73`](https://github.com/andythomas/matr1x/commit/41c0d732db3b26519b208685b568fb8cd80d6d80))

* fix(controlwindow): remove double calling of System.set in legacy code *by Dominik Kriegner* ([`41c0d73`](https://github.com/andythomas/matr1x/commit/41c0d732db3b26519b208685b568fb8cd80d6d80))

* fix(config): correctly replace <pkgroot> on all platforms (#1858) *by Dominik Kriegner* ([`79e97d8`](https://github.com/andythomas/matr1x/commit/79e97d8ef4f974ee7ba977b87906c816d148a9aa))

* fix(matrix-script): make finish button again work as intended (#1856) *by Dominik Kriegner* ([`f38c986`](https://github.com/andythomas/matr1x/commit/f38c98681d0ddf606d4b43da9b593ab59ebe511f))

* fix(store_script_in_datafile): ensure last user script line is stored by added a newline (#1854) *by Dominik Kriegner* ([`f52ef15`](https://github.com/andythomas/matr1x/commit/f52ef1529329f8f447f2d410a9349bda8d4ce788))

* fix: matrix-preview filename needs to be in raw-string *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix: allow connection.clear() to fail *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix: avoid segmentation fault in control-GUI (#1594) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(sweep-generator): correctly emit signals (#1597) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix: address type checking issues (#1602) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(matrix-script): add columns without unit (#1599) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(logwindow): correct logwindow handling and link it between matrix-gui and sweep-generator (#1605) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(matrix-script): add columns without unit (#1599) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(sweep-generator): fix deeper recursion (#1607) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(matrix-script): harden execution for very fast measurements (#1610) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(controlGUI): avoid cross thread access of Qt objects (#1591) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(controlGUI): avoid cross thread access of Qt objects *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix: address type checking issues (#1617) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(matrix-script): avoid timeout for interthread communication (#1613) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(matrix-script): avoid manually defined timeout for interthread communication *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(matrix-script): correct handling of carriage return (#1618) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(matrix-script): correct handling of carriage return *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(git): add additional type check (#1625) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(git): add additional type check *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(vektorak): rename sys to system (#1626) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(elabftw): make code us newest version of elabapi_python (#1627) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(install): address several security vulnerabilities (#1631) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(pytest): increase rubustness of pytests (#1636) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(pytest): find ruff more robustly *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix: update required pygit2 version for Py3.14 (#1638) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(uv): update lockfile to newest version (#1643) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(test): correct GUI teardown and test output capture (#1641) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(test): make pytest not swallow the printout *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(install): address security vulnerability (#1654) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(ppms): add default rate and fix typing (#1655) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(fsw8): delete unused channel parameter (#1656) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(modbusdevice): add method and arguments to output in case of an exception (#1659) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(system): use "Easier to ask for forgiveness than permission" style (#1650) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(system): make config_query use "Easier to ask for forgiveness than permission" style *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(modbusdevice): use correct attribute name and better default (#1663) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(matrix-script): make duplicate_output_to_logfile functionality carriage return aware (#1673) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(log window): improve usability (#1674) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(AJA): fix panic mode behavior (#1680) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(AJA): fix panic mode behavior *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(typehint): make typehint fit to code behavior and docstring *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(control-dummy): make panic mode behavior more like in normal controlGUI (#1681) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(datafilename): better automatic renaming of datafilenames with dots (#1689) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(post-install): more robust desktop integration (#1699) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(controlGUI): disable measurement access during panic mode (#1696) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(controlGUI): disable measurement access during panic mode *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(matrix-gui): unknown stdout triggers warning (#1709) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(installation): clarify installation options and remove pip (#1707) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix: improve readability of logger table messages (#1708) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(GuiDict): allow lazy instantiation (#1701) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(matrix-script): carriage return issue in wait (#1705) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(matrix-script): carriage return issue in wait *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(control): refactor, fix and improve control and related (#1716) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(post-install): minor integration issues (#1720) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix: remove unused control guis from the codebase (#1721) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix: update the jaguar control (#1732) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(Ptarmigan): change commands to new notation *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix: address security vulnerabilities (#1738) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(control): make public var methods thread-safe (#1728) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(matrix-preview): fix transpose button visibility (#1693) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(AutoSlot): do not use Generics and allow Unions (#1745) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(AutoSlot): do not use Generics *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(loadmatrix): use " :" for splitting in header (#1747) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix: remove deprecated var-outType from codebase *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(control-dummy): allow to recover from V4 panic (#1744) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(control-dummy): allow to recover from V4 panic *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(install): address security vulnerability (#1752) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(sweep-generator): correctly assign the system filenames (#1753) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(sweep-generator): fix empty system filenames *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(controlGUI): cleanup GUI interaction possibilities after error (#1750) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(controlGUI): cleanup GUI interaction possibilities after error *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix: pin elabapi version due to api change (#1765) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(matrix-script): auto-scroll in terminal (#1770) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix: grab system information (#1787) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(matrix-gui): do not allow to delete the current measurement (#1798) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(matrix-gui): correctly store config settings (#1800) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(matrix-script): reactivate pulldows in toolbar (#1807) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(controlwindow): ensure proper cleanup of GuiDict upon crash (#1802) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(controlwindow): ensure proper cleanup of GuiDict upon crash *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(config): add missing email config to validation models (#1808) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(config): add missing email config to validation models *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(matrix-script,system-aja): use Message communication for all output (#1810) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix: remove deprecated var-outType from codebase *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(controlwindow): ensure proper cleanup of GuiDict upon crash *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(config): add missing email config to validation models *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(config editor): ensure editor opens correctly (#1826) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(config editor): ensure editor opens correctly *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(system): add_comment requires initialization (#1836) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* fix(system): add_comment requires initialization (#1836) *by Andy Thomas* ([`1f35b90`](https://github.com/andythomas/matr1x/commit/1f35b90a3ff374742c22eac1f3d7acb3d0fd880f))

* fix(config editor): ensure editor opens correctly (#1826) *by Dominik Kriegner* ([`4252072`](https://github.com/andythomas/matr1x/commit/42520723252ba618b2cc8816b800b0780a824d6f))

* fix(config editor): ensure editor opens correctly *by Dominik Kriegner* ([`4252072`](https://github.com/andythomas/matr1x/commit/42520723252ba618b2cc8816b800b0780a824d6f))

* fix: remove deprecated var-outType from codebase *by Dominik Kriegner* ([`656c089`](https://github.com/andythomas/matr1x/commit/656c0899dd69acc6a82193a588104b04a0c772e7))

* fix(controlwindow): ensure proper cleanup of GuiDict upon crash *by Dominik Kriegner* ([`656c089`](https://github.com/andythomas/matr1x/commit/656c0899dd69acc6a82193a588104b04a0c772e7))

* fix(config): add missing email config to validation models *by Dominik Kriegner* ([`656c089`](https://github.com/andythomas/matr1x/commit/656c0899dd69acc6a82193a588104b04a0c772e7))

* fix(matrix-script,system-aja): use Message communication for all output (#1810) *by Dominik Kriegner* ([`91b9ecc`](https://github.com/andythomas/matr1x/commit/91b9ecc569d270c9949258ea0ae4f45ab0158749))

* fix(config): add missing email config to validation models (#1808) *by Dominik Kriegner* ([`49e5702`](https://github.com/andythomas/matr1x/commit/49e57023fb366603df0a71ac63a44f64dea7ca01))

* fix(config): add missing email config to validation models *by Dominik Kriegner* ([`49e5702`](https://github.com/andythomas/matr1x/commit/49e57023fb366603df0a71ac63a44f64dea7ca01))

* fix(controlwindow): ensure proper cleanup of GuiDict upon crash (#1802) *by Dominik Kriegner* ([`d9f84b9`](https://github.com/andythomas/matr1x/commit/d9f84b95272f91de8318b0b69de7509e72f51a18))

* fix(controlwindow): ensure proper cleanup of GuiDict upon crash *by Dominik Kriegner* ([`d9f84b9`](https://github.com/andythomas/matr1x/commit/d9f84b95272f91de8318b0b69de7509e72f51a18))

* fix(matrix-script): reactivate pulldows in toolbar (#1807) *by Andy Thomas* ([`f15d83b`](https://github.com/andythomas/matr1x/commit/f15d83b8e1d828f11e9d8efba4450aa3b7cd6b4b))

* fix(matrix-gui): correctly store config settings (#1800) *by Andy Thomas* ([`7b9a22f`](https://github.com/andythomas/matr1x/commit/7b9a22ffef00a5f75384e59a95658159ac173bd6))

* fix(matrix-gui): do not allow to delete the current measurement (#1798) *by Andy Thomas* ([`b9920f8`](https://github.com/andythomas/matr1x/commit/b9920f8a19f18b28342f0618f3517ca71edf9670))

* fix: grab system information (#1787) *by Andy Thomas* ([`c3dc228`](https://github.com/andythomas/matr1x/commit/c3dc228c00536d97b2d89842d693842001b322d8))

* fix(matrix-script): auto-scroll in terminal (#1770) *by Andy Thomas* ([`0fdc740`](https://github.com/andythomas/matr1x/commit/0fdc740b2c997d9e6a646bebb636abf4a1e4b7d9))

* fix: pin elabapi version due to api change (#1765) *by Andy Thomas* ([`12a132a`](https://github.com/andythomas/matr1x/commit/12a132a9f65404ad87eadb36b5d6e825d5667790))

### Documentation

* docs(_matrix_script_template): edit signatures and docstrings (#1614) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* docs(matrix-script): add startup help (back) (#1632) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* docs: streamline readme, remove unmaintained sections (#1711) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* docs(install): add migration section for v8.3 *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

### Features

* feat(attocry2100): new FZU attocube cryo files (v1) (#1850) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* feat(attocubeAMC300): new system for attocube amc300 based translation stage *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* feat(matrix-script): add hover info to user script (#1619) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* feat(matrix-script): add context sensitive auto-complete via LSP (#1633) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* feat(AJA): add O2 gas option in system/control-AJA (#1649) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* feat: remove custom installer and auto-perform desktop integration on first start-up (#1652) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* feat(AJA): add automatic google spreadsheet entry upon sample growth (#1662) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* feat(AJA): sync elabftw resource names/link to google sheet file *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* feat(controlwindow): utilize one logger for stdout and stderr (#1667) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* feat(matrix-script): reset date and metadata to script start upon init_datafile (#1692) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* feat(matrix-gui): provide a GUI for the measurement thread (#1665) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* feat(AJA): add standby button to control-aja (#1697) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* feat(pymeasure): better support for pymeasure Instruments (#1746) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* feat(control): introduce better validation and type safety for var (#1735) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* feat: allow matrix-script and sweep-generator use with no system (#1794) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* feat: allow thread-safe modification of guiObjects (#1748) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* feat(config): consolidate defaults into Pydantic models (#1801) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* feat(matrix-gui): allow to modify queued measurements (#1803) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* feat(editor): provide ty diagnostics for matrix-script (#1829) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* feat(AJA): add MFC3 in control and system (#1847) *by Dominik Kriegner* ([`061f215`](https://github.com/andythomas/matr1x/commit/061f21553adafc623c9777cce3166744e56362c9))

* feat(matrix.py): allow to log messages and add them to the datafile (#1848) *by Andy Thomas* ([`95c5137`](https://github.com/andythomas/matr1x/commit/95c5137655a7c911362fcccc58522902f5eacd3c))

* feat(editor): provide ty diagnostics for matrix-script (#1829) *by Andy Thomas* ([`9752e42`](https://github.com/andythomas/matr1x/commit/9752e423429b7929316ec1d0f74192c4606dbdc1))

* feat(matrix-gui): allow to modify queued measurements (#1803) *by Andy Thomas* ([`fd1bd3e`](https://github.com/andythomas/matr1x/commit/fd1bd3ed7d28b69f00a8bfd7860a98d2ef68dac2))

* feat(config): consolidate defaults into Pydantic models (#1801) *by Dominik Kriegner* ([`3207f5d`](https://github.com/andythomas/matr1x/commit/3207f5d2f88f2149597f2a736d5d74942bf7c562))

* feat: allow thread-safe modification of guiObjects (#1748) *by Andy Thomas* ([`80f781d`](https://github.com/andythomas/matr1x/commit/80f781d7351641332e61eb0b7d5d9369b7a7de40))

* feat: allow matrix-script and sweep-generator use with no system (#1794) *by Andy Thomas* ([`4cc333d`](https://github.com/andythomas/matr1x/commit/4cc333d224ce2fa314d7c133303a424720a6218b))

### Unknown

* remove system parameter and self.system (#1782) *by Andy Thomas* ([`d8a64a5`](https://github.com/andythomas/matr1x/commit/d8a64a52cc75a998a587a709c301c0d1fa622ffe))

## v8.3.0 (2026-04-18)

### Bug fixes

* fix(controlGUI): cleanup GUI interaction possibilities after error (#1750) *by Dominik Kriegner* ([`50c4ad5`](https://github.com/andythomas/matr1x/commit/50c4ad554da1c2e1261e4befe70146b641e56120))

* fix(controlGUI): cleanup GUI interaction possibilities after error *by Dominik Kriegner* ([`50c4ad5`](https://github.com/andythomas/matr1x/commit/50c4ad554da1c2e1261e4befe70146b641e56120))

* fix(sweep-generator): correctly assign the system filenames (#1753) *by Andy Thomas* ([`e305569`](https://github.com/andythomas/matr1x/commit/e3055696435bfc6186005718b732e0a9f4b5c304))

* fix(sweep-generator): fix empty system filenames *by Andy Thomas* ([`e305569`](https://github.com/andythomas/matr1x/commit/e3055696435bfc6186005718b732e0a9f4b5c304))

* fix(control-dummy): allow to recover from V4 panic (#1744) *by Dominik Kriegner* ([`484637c`](https://github.com/andythomas/matr1x/commit/484637c8b1ed0aad84e8de119274578f11d48139))

* fix(control-dummy): allow to recover from V4 panic *by Dominik Kriegner* ([`484637c`](https://github.com/andythomas/matr1x/commit/484637c8b1ed0aad84e8de119274578f11d48139))

* fix: remove deprecated var-outType from codebase *by Andy Thomas* ([`ce6fec2`](https://github.com/andythomas/matr1x/commit/ce6fec2eb78b6584ba2d175d2178d4c66dd4179a))

* fix(loadmatrix): use " :" for splitting in header (#1747) *by Dominik Kriegner* ([`1486377`](https://github.com/andythomas/matr1x/commit/14863770096f61f5f8b4d25051ba3165bb6198f2))

* fix(AutoSlot): do not use Generics and allow Unions (#1745) *by Andy Thomas* ([`878abd1`](https://github.com/andythomas/matr1x/commit/878abd190b77d4daf97a01ebc839239f4874fcd9))

* fix(AutoSlot): do not use Generics *by Andy Thomas* ([`878abd1`](https://github.com/andythomas/matr1x/commit/878abd190b77d4daf97a01ebc839239f4874fcd9))

* fix(matrix-preview): fix transpose button visibility (#1693) *by Dominik Kriegner* ([`27e523e`](https://github.com/andythomas/matr1x/commit/27e523e31cbbae4b08bc0189301670ea025e12bc))

* fix(control): make public var methods thread-safe (#1728) *by Andy Thomas* ([`93b2c05`](https://github.com/andythomas/matr1x/commit/93b2c0544f33d18dc41cf21f328fb1d7e5583d10))

* fix(post-install): minor integration issues (#1720) *by Andy Thomas* ([`62a5595`](https://github.com/andythomas/matr1x/commit/62a55959fff11ae587f5d92fc8f9ad913a35186a))

* fix(control): refactor, fix and improve control and related (#1716) *by Andy Thomas* ([`845c4bc`](https://github.com/andythomas/matr1x/commit/845c4bcf4b3b1fb9778ed3716926805c41b6fa5f))

* fix(matrix-script): carriage return issue in wait (#1705) *by Dominik Kriegner* ([`3413505`](https://github.com/andythomas/matr1x/commit/3413505acbd4afba8666ea102ebf0007f167717c))

* fix(matrix-script): carriage return issue in wait *by Dominik Kriegner* ([`3413505`](https://github.com/andythomas/matr1x/commit/3413505acbd4afba8666ea102ebf0007f167717c))

* fix(GuiDict): allow lazy instantiation (#1701) *by Andy Thomas* ([`1f33dcc`](https://github.com/andythomas/matr1x/commit/1f33dcc748792690e3a4ea9633da2caa32ffa393))

* fix: improve readability of logger table messages (#1708) *by Andy Thomas* ([`587880c`](https://github.com/andythomas/matr1x/commit/587880c4e3838a1254dc788d0bf5e59336a28181))

* fix(installation): clarify installation options and remove pip (#1707) *by Andy Thomas* ([`04d9c4f`](https://github.com/andythomas/matr1x/commit/04d9c4f1914228f5cd8f54ab85738d57b8008c40))

* fix(matrix-gui): unknown stdout triggers warning (#1709) *by Andy Thomas* ([`9b5ed0b`](https://github.com/andythomas/matr1x/commit/9b5ed0b9a7399c68d3ca847768de459050a0a2c4))

* fix(controlGUI): disable measurement access during panic mode (#1696) *by Dominik Kriegner* ([`6b486de`](https://github.com/andythomas/matr1x/commit/6b486de5e11080b6f5d8a3a0f840ff674d7af5f6))

* fix(controlGUI): disable measurement access during panic mode *by Dominik Kriegner* ([`6b486de`](https://github.com/andythomas/matr1x/commit/6b486de5e11080b6f5d8a3a0f840ff674d7af5f6))

* fix(post-install): more robust desktop integration (#1699) *by Andy Thomas* ([`18eedec`](https://github.com/andythomas/matr1x/commit/18eedecaaba5c733180d9d5ceb7cbc1db1791559))

* fix(datafilename): better automatic renaming of datafilenames with dots (#1689) *by Dominik Kriegner* ([`c793290`](https://github.com/andythomas/matr1x/commit/c793290425f61486dab78a08e834a77af10535e1))

* fix(control-dummy): make panic mode behavior more like in normal controlGUI (#1681) *by Dominik Kriegner* ([`79bd49b`](https://github.com/andythomas/matr1x/commit/79bd49b6e4a1a06a73d1fb448304c98a96ef60b3))

* fix(AJA): fix panic mode behavior (#1680) *by Dominik Kriegner* ([`83156d0`](https://github.com/andythomas/matr1x/commit/83156d0f07fd7d1ea2f8605bab01ce9cc0684432))

* fix(AJA): fix panic mode behavior *by Dominik Kriegner* ([`83156d0`](https://github.com/andythomas/matr1x/commit/83156d0f07fd7d1ea2f8605bab01ce9cc0684432))

* fix(typehint): make typehint fit to code behavior and docstring *by Dominik Kriegner* ([`83156d0`](https://github.com/andythomas/matr1x/commit/83156d0f07fd7d1ea2f8605bab01ce9cc0684432))

* fix(log window): improve usability (#1674) *by Andy Thomas* ([`2d14b0b`](https://github.com/andythomas/matr1x/commit/2d14b0b353f7a708aa12e52c5c0025e2af187fd9))

* fix(matrix-script): make duplicate_output_to_logfile functionality carriage return aware (#1673) *by Dominik Kriegner* ([`abc29ad`](https://github.com/andythomas/matr1x/commit/abc29ad9e27ed9a5ce44fff8ddcc8301dfdc8ec7))

* fix(modbusdevice): use correct attribute name and better default (#1663) *by Dominik Kriegner* ([`46b4d1d`](https://github.com/andythomas/matr1x/commit/46b4d1d5c2e5194c518c1e9f9f28868c62251398))

* fix(system): use "Easier to ask for forgiveness than permission" style (#1650) *by Dominik Kriegner* ([`fa7e53c`](https://github.com/andythomas/matr1x/commit/fa7e53cd2115593e20eb85ee282faafa7c97ce03))

* fix(system): make config_query use "Easier to ask for forgiveness than permission" style *by Dominik Kriegner* ([`fa7e53c`](https://github.com/andythomas/matr1x/commit/fa7e53cd2115593e20eb85ee282faafa7c97ce03))

* fix(modbusdevice): add method and arguments to output in case of an exception (#1659) *by Andy Thomas* ([`dd93f73`](https://github.com/andythomas/matr1x/commit/dd93f73399f3d2458f82ceceec514076bd6039c6))

* fix(fsw8): delete unused channel parameter (#1656) *by Andy Thomas* ([`93318fd`](https://github.com/andythomas/matr1x/commit/93318fdb57b843fc4ee4b28020c1209d63d3e876))

* fix(ppms): add default rate and fix typing (#1655) *by Andy Thomas* ([`7937e5c`](https://github.com/andythomas/matr1x/commit/7937e5cb74cbba4c71d314318f1e2cb6e4b4e819))

* fix(test): correct GUI teardown and test output capture (#1641) *by Dominik Kriegner* ([`78dc4ef`](https://github.com/andythomas/matr1x/commit/78dc4efc783ff650b1ffef54ec89db65ad68e937))

* fix(test): make pytest not swallow the printout *by Dominik Kriegner* ([`78dc4ef`](https://github.com/andythomas/matr1x/commit/78dc4efc783ff650b1ffef54ec89db65ad68e937))

### Features

* feat(control): introduce better validation and type safety for var (#1735) *by Andy Thomas* ([`ce6fec2`](https://github.com/andythomas/matr1x/commit/ce6fec2eb78b6584ba2d175d2178d4c66dd4179a))

* feat(pymeasure): better support for pymeasure Instruments (#1746) *by Dominik Kriegner* ([`e0405eb`](https://github.com/andythomas/matr1x/commit/e0405eb8b8d84261f37e6b6fca85816d97ced087))

* feat(matrix-gui): provide a GUI for the measurement thread (#1665) *by Andy Thomas* ([`9ee24c2`](https://github.com/andythomas/matr1x/commit/9ee24c26321beb9e957898251038138f472187fd))

* feat(matrix-script): reset date and metadata to script start upon init_datafile (#1692) *by Dominik Kriegner* ([`68e51b9`](https://github.com/andythomas/matr1x/commit/68e51b9c4f207fe7ab433fb1e5e58db8ed15e4f0))

* feat(controlwindow): utilize one logger for stdout and stderr (#1667) *by Andy Thomas* ([`045f8e0`](https://github.com/andythomas/matr1x/commit/045f8e0efb85c5ff8e42aeae5f719cea0ba537da))

* feat: remove custom installer and auto-perform desktop integration on first start-up (#1652) *by Andy Thomas* ([`f5717b3`](https://github.com/andythomas/matr1x/commit/f5717b3417d9725e59e7c2610d430ebaed13d1ac))

## v8.2.0 (2026-02-09)

### Bug fixes

* fix: update required pygit2 version for Py3.14 (#1638) *by Andy Thomas* ([`ed50538`](https://github.com/andythomas/matr1x/commit/ed5053899cad2eef03ef82e507c97db7da41cf1f))

* fix(pytest): increase rubustness of pytests (#1636) *by Andy Thomas* ([`f2bf9e1`](https://github.com/andythomas/matr1x/commit/f2bf9e1a311e931ef862ae2ee77191287a9eb531))

* fix(pytest): find ruff more robustly *by Andy Thomas* ([`f2bf9e1`](https://github.com/andythomas/matr1x/commit/f2bf9e1a311e931ef862ae2ee77191287a9eb531))

* fix(elabftw): make code us newest version of elabapi_python (#1627) *by Dominik Kriegner* ([`01f553a`](https://github.com/andythomas/matr1x/commit/01f553ac2fbad4f0e950cba985b428f97e76fc4c))

* fix(git): add additional type check (#1625) *by Dominik Kriegner* ([`e2ed344`](https://github.com/andythomas/matr1x/commit/e2ed344bdd0651a064b73ba19a6902de238e897c))

* fix(git): add additional type check *by Dominik Kriegner* ([`e2ed344`](https://github.com/andythomas/matr1x/commit/e2ed344bdd0651a064b73ba19a6902de238e897c))

* fix(matrix-script): correct handling of carriage return (#1618) *by Dominik Kriegner* ([`7b53eb6`](https://github.com/andythomas/matr1x/commit/7b53eb655ff2f9141f4892a9f3acde6d47107b60))

* fix(matrix-script): correct handling of carriage return *by Dominik Kriegner* ([`7b53eb6`](https://github.com/andythomas/matr1x/commit/7b53eb655ff2f9141f4892a9f3acde6d47107b60))

* fix(matrix-script): avoid timeout for interthread communication (#1613) *by Dominik Kriegner* ([`55665c1`](https://github.com/andythomas/matr1x/commit/55665c1af4dd1c28c912f8c1a468e5bda002ffef))

* fix(matrix-script): avoid manually defined timeout for interthread communication *by Dominik Kriegner* ([`55665c1`](https://github.com/andythomas/matr1x/commit/55665c1af4dd1c28c912f8c1a468e5bda002ffef))

* fix: address type checking issues (#1617) *by Andy Thomas* ([`76b0de6`](https://github.com/andythomas/matr1x/commit/76b0de60b354529c302104e944e5a3a39f12b73e))

* fix(controlGUI): avoid cross thread access of Qt objects (#1591) *by Dominik Kriegner* ([`d619767`](https://github.com/andythomas/matr1x/commit/d61976707d41f376963c6751cf9afaea90a474f7))

* fix(controlGUI): avoid cross thread access of Qt objects *by Dominik Kriegner* ([`d619767`](https://github.com/andythomas/matr1x/commit/d61976707d41f376963c6751cf9afaea90a474f7))

* fix(matrix-script): harden execution for very fast measurements (#1610) *by Andy Thomas* ([`a91f548`](https://github.com/andythomas/matr1x/commit/a91f548e0e4c4079b6e4dcee5414e0da452c36b6))

* fix(sweep-generator): fix deeper recursion (#1607) *by Andy Thomas* ([`60a7936`](https://github.com/andythomas/matr1x/commit/60a7936f4b898ddb4a72d38c1c22567cd82587d9))

* fix(matrix-script): add columns without unit (#1599) *by Andy Thomas* ([`e76fd64`](https://github.com/andythomas/matr1x/commit/e76fd64aec8a99fcccd9ae5612f55c2fafd63b5e))

* fix(logwindow): correct logwindow handling and link it between matrix-gui and sweep-generator (#1605) *by Dominik Kriegner* ([`7a9ad38`](https://github.com/andythomas/matr1x/commit/7a9ad382b86f1a86fdbaa8c1a65ee27137861588))

* fix(matrix-script): add columns without unit (#1599) *by Andy Thomas* ([`9c568bc`](https://github.com/andythomas/matr1x/commit/9c568bc5ccf45012c4848a3de2cf42c0a5af8617))

* fix: address type checking issues (#1602) *by Andy Thomas* ([`c49fde1`](https://github.com/andythomas/matr1x/commit/c49fde1f90f653b749e15c28e1ad8cfabd5ca2b4))

* fix(sweep-generator): correctly emit signals (#1597) *by Andy Thomas* ([`5d0d7e1`](https://github.com/andythomas/matr1x/commit/5d0d7e1392fcd2ae6f30bc5e0f0af17882b37585))

* fix: avoid segmentation fault in control-GUI (#1594) *by Dominik Kriegner* ([`405ff5a`](https://github.com/andythomas/matr1x/commit/405ff5ad6f558f2c0f9347edf7d8704a1c077f6f))

* fix: matrix-preview filename needs to be in raw-string (#1592) *by Dominik Kriegner* ([`afaef79`](https://github.com/andythomas/matr1x/commit/afaef79ab03e043264d791f6e60744b33f805e08))

* fix(controlGUI): use default sizePolicy for widgets (#1582) *by Dominik Kriegner* ([`742472a`](https://github.com/andythomas/matr1x/commit/742472a55a1fedf5895600055a38e30393e87dab))

* fix(GuiDict): improve logic of stop procedure (#1578) *by Dominik Kriegner* ([`15bc62a`](https://github.com/andythomas/matr1x/commit/15bc62a8f17382f48c0278125d54ecca62140c64))

* fix(matrix-preview): correct start synthax from other GUIs (#1577) *by Dominik Kriegner* ([`8a2c775`](https://github.com/andythomas/matr1x/commit/8a2c7751df14800645a011ecda0b94b3705bfe1a))

* fix: address type checking issues (#1576) *by Andy Thomas* ([`1a8ba68`](https://github.com/andythomas/matr1x/commit/1a8ba687ed36bc32cf3f87461ece1c994b64cb6b))

* fix: correctly run ruff format also on windows machines (#1571) *by Andy Thomas* ([`1365313`](https://github.com/andythomas/matr1x/commit/1365313b1f66b01d53242a2198bb1d9dc3d12eb8))

* fix: use more robust preview call (#1570) *by Andy Thomas* ([`0968b43`](https://github.com/andythomas/matr1x/commit/0968b43e10bde993b2a43087d22dc2e1a2b21018))

* fix: attempt to fix crash that occurs after preview use (#1563) *by Andy Thomas* ([`e14ceee`](https://github.com/andythomas/matr1x/commit/e14ceee601582a228444116b883db81c5151dff2))

* fix(matrix-script): correctly highlight executing line (#1560) *by Dominik Kriegner* ([`4a4be9a`](https://github.com/andythomas/matr1x/commit/4a4be9a8bd793d49234fb915e4473eea14dd9dcb))

* fix(sweep-generator): make matrix-gui callback use str argument (#1547) *by Dominik Kriegner* ([`8f3523f`](https://github.com/andythomas/matr1x/commit/8f3523f5868dfabc31fd76deed50572921b02af3))

* fix(sweep-generator, matrix-preview): enforce pyside use in pyqtgraph (#1543) *by Dominik Kriegner* ([`7ff5449`](https://github.com/andythomas/matr1x/commit/7ff544976fbd9405e85dc8c4eaf4753b8446750d))

* fix(sweep-generator, matrix-preview): enforce pyside use in pyqtgraph *by Dominik Kriegner* ([`7ff5449`](https://github.com/andythomas/matr1x/commit/7ff544976fbd9405e85dc8c4eaf4753b8446750d))

* fix(sweep-generator): fix pyside6 conversion issues (#1536) *by Andy Thomas* ([`eb65461`](https://github.com/andythomas/matr1x/commit/eb65461b07d66b221b54d4771bfba9653fe58b01))

* fix(tests): ensure software rendering during tests (#1530) *by Dominik Kriegner* ([`1439b54`](https://github.com/andythomas/matr1x/commit/1439b54d9218d9ffb18a8accff77e1384c61d65b))

* fix(controlGuis): store window settings automatically on close (#1523) *by Dominik Kriegner* ([`fd6c9d0`](https://github.com/andythomas/matr1x/commit/fd6c9d0b24b2db8b4d08c900fed6cf3d92a47829))

* fix(matrix-script): reset scriptname on "new-file" (#1514) *by Andy Thomas* ([`2e187d4`](https://github.com/andythomas/matr1x/commit/2e187d40104646e53a8aeb0b5f53a1657d61a112))

* fix(matrix-script): reset scriptname on "new-file" (#1514) *by Andy Thomas* ([`5c654c1`](https://github.com/andythomas/matr1x/commit/5c654c169e631c51c00caed6268b43215faa39c1))

* fix(matrix-script): fix and make the linter more robust (#1506) *by Andy Thomas* ([`510e36a`](https://github.com/andythomas/matr1x/commit/510e36ae1b73a7429b52b648b45f1c7a64ae5767))

* fix(matrix): fix pathlib conversion bug (#1512) *by Andy Thomas* ([`0282c80`](https://github.com/andythomas/matr1x/commit/0282c8089aa75f9ad968b0edfd5ef981158196a9))

* fix: auto-reset corrupt settings (#1507) *by Andy Thomas* ([`e88008b`](https://github.com/andythomas/matr1x/commit/e88008b9bc5cfe998840914355f4fdfff5667dee))

* fix: corrupt settings do not crash the apps *by Andy Thomas* ([`e88008b`](https://github.com/andythomas/matr1x/commit/e88008b9bc5cfe998840914355f4fdfff5667dee))

* fix(elabftw): template string detection with pathlib (#1489) *by Dominik Kriegner* ([`c56e80b`](https://github.com/andythomas/matr1x/commit/c56e80bce29b23277a8ea8362ad44299f887bfd6))

* fix(matrix-preview): add is not None checks (#1484) *by Dominik Kriegner* ([`6251802`](https://github.com/andythomas/matr1x/commit/62518020ec3146052204766be3add51f6e58359b))

* fix: introduce a plain coding error *by Dominik Kriegner* ([`ee75f9c`](https://github.com/andythomas/matr1x/commit/ee75f9ce0effde05047c0e42bafbec31f7b64096))

### Build system

* build: use default LICENSE file name (#1569) *by Dominik Kriegner* ([`0b35bad`](https://github.com/andythomas/matr1x/commit/0b35bad87d3ea535f2d509386cb82fe4977312f6))

### Code style

* style(matrix-script): use double quotes for autocomplete snippets (#1580) *by Dominik Kriegner* ([`700b5d8`](https://github.com/andythomas/matr1x/commit/700b5d8fb324e5d327a64be5c07b9840dafe47aa))

* style(matrix-script): use double quotes for autocomplete snippets *by Dominik Kriegner* ([`700b5d8`](https://github.com/andythomas/matr1x/commit/700b5d8fb324e5d327a64be5c07b9840dafe47aa))

* style: lint and format with biome (#1581) *by Dominik Kriegner* ([`700b5d8`](https://github.com/andythomas/matr1x/commit/700b5d8fb324e5d327a64be5c07b9840dafe47aa))

### Documentation

* docs(matrix-script): add startup help (back) (#1632) *by Andy Thomas* ([`db53ea5`](https://github.com/andythomas/matr1x/commit/db53ea5819fdbc57c8a3bce37aec1cef46ed6d6c))

* docs(_matrix_script_template): edit signatures and docstrings (#1614) *by Andy Thomas* ([`f92d61d`](https://github.com/andythomas/matr1x/commit/f92d61d1517febd026f23a83eb164498c04fc5b9))

### Features

* feat(matrix-script): add context sensitive auto-complete via LSP (#1633) *by Andy Thomas* ([`786b0be`](https://github.com/andythomas/matr1x/commit/786b0be573cbb41f0a8b5e384345d91d1499857e))

* feat(matrix-script): add hover info to user script (#1619) *by Andy Thomas* ([`e5e55dc`](https://github.com/andythomas/matr1x/commit/e5e55dc834367b4b286997d1db49ae7985c287e6))

* feat(matrix-script): allow multiple matrix-script editor windows (#1585) *by Dominik Kriegner* ([`e5f8711`](https://github.com/andythomas/matr1x/commit/e5f8711d57efeb914dceddea18a53b52a9b9ba66))

* feat(matrix-script): allow multiple matrix-script editor windows *by Dominik Kriegner* ([`e5f8711`](https://github.com/andythomas/matr1x/commit/e5f8711d57efeb914dceddea18a53b52a9b9ba66))

* feat: add a log console to the main applications (#1572) *by Andy Thomas* ([`1272446`](https://github.com/andythomas/matr1x/commit/12724463a832dcdc9a6929c8d9aa41a66be01dbf))

* feat(matrix-script): skip value checking in marked lines (#1552) *by Andy Thomas* ([`6e32eee`](https://github.com/andythomas/matr1x/commit/6e32eee5b9c2cb08eb3bc6211315ea23dce976d5))

* feat(matrix-script): add logging to editor (#1551) *by Andy Thomas* ([`89e7f50`](https://github.com/andythomas/matr1x/commit/89e7f50f2bb30aad5982ed8729d0aede8571048d))

* feat(reset): attempt to call System.reset also if an exception occurs (#1526) *by Dominik Kriegner* ([`ec6802a`](https://github.com/andythomas/matr1x/commit/ec6802a7d81f51e66915f9c3bf2feee04fd317f2))

* feat(reset): attempt to call System.reset also if an exception occurs *by Dominik Kriegner* ([`ec6802a`](https://github.com/andythomas/matr1x/commit/ec6802a7d81f51e66915f9c3bf2feee04fd317f2))

* feat(matrix-script): add tooltip descriptions and value placeholders to auto-complete (#1511) *by Andy Thomas* ([`d4af658`](https://github.com/andythomas/matr1x/commit/d4af6587d6d002e367414e2aaf10ed1e38892883))

* feat(matrix-script): replace editor with monaco (#1491) *by Andy Thomas* ([`2db819c`](https://github.com/andythomas/matr1x/commit/2db819ca13c3c37d185aabf0b669a91eb7f92e3b))

* feat(AJA): home made motor controller and other small changes (#1382) *by Dominik Kriegner* ([`db6d4fd`](https://github.com/andythomas/matr1x/commit/db6d4fd47208b5c6f37f388d0203e0391e5d9006))

* feat(AJA): new motor controller device driver *by Dominik Kriegner* ([`db6d4fd`](https://github.com/andythomas/matr1x/commit/db6d4fd47208b5c6f37f388d0203e0391e5d9006))

* feat(controlgui): simplify use of var objects by new default outType value *by Dominik Kriegner* ([`db6d4fd`](https://github.com/andythomas/matr1x/commit/db6d4fd47208b5c6f37f388d0203e0391e5d9006))

* feat(config): scientific notation in device config (#1492) *by Andy Thomas* ([`9460bd1`](https://github.com/andythomas/matr1x/commit/9460bd1cd0518a44ed5f083c121278ba9073ffc2))

* feat(config): scientific notation in device config *by Andy Thomas* ([`9460bd1`](https://github.com/andythomas/matr1x/commit/9460bd1cd0518a44ed5f083c121278ba9073ffc2))

* feat: extend AboutBox with python environment information (#1485) *by Dominik Kriegner* ([`7188a0e`](https://github.com/andythomas/matr1x/commit/7188a0e5006d0908d2b07d47044186d465e6c280))

* feat: extend AboutBox with python environment information *by Dominik Kriegner* ([`7188a0e`](https://github.com/andythomas/matr1x/commit/7188a0e5006d0908d2b07d47044186d465e6c280))

## v8.1.0 (2025-09-11)

### Bug fixes

* fix: remove faulty and unused IPS120 code (#1466) *by Dominik Kriegner* ([`5a34fa6`](https://github.com/andythomas/matr1x/commit/5a34fa6c007e6dc3080385b2391a01b992c96c1a))

* fix: address type-checker issues (#1438) *by Andy Thomas* ([`b5ddd4b`](https://github.com/andythomas/matr1x/commit/b5ddd4b7566dc1e5db63efdd7c2bf30c3ebfe1aa))

* fix(preview): more stable linked x-axis during autoupdate (#1461) *by Dominik Kriegner* ([`86c43d9`](https://github.com/andythomas/matr1x/commit/86c43d99f2206d0b8c799de6d38e5d4b35a1f344))

* fix(matrix-gui): recover preview functionality *by Dominik Kriegner* ([`0d0d6f4`](https://github.com/andythomas/matr1x/commit/0d0d6f4509f3e1b711d602144090d773a85e8158))

* fix(matrix-gui): recover preview functionality (#1453) *by Andy Thomas* ([`0a21637`](https://github.com/andythomas/matr1x/commit/0a216379209cfb70c2451c9d7243f7731a43739d))

* fix(matrix-gui): recover preview functionality *by Andy Thomas* ([`0a21637`](https://github.com/andythomas/matr1x/commit/0a216379209cfb70c2451c9d7243f7731a43739d))

* fix(pymeasure): improved thread safety and convenience methods. (#1451) *by Dominik Kriegner* ([`3ab73e6`](https://github.com/andythomas/matr1x/commit/3ab73e6fd68b0e86a92af30b1095597410fc8b86))

* fix(control): add log file header when new file is selected (#1450) *by Dominik Kriegner* ([`270ae1f`](https://github.com/andythomas/matr1x/commit/270ae1f3ff70098c873d3e39dd5c27d326403226))

* fix(loadmatrix): code quality improvement (#1441) *by Dominik Kriegner* ([`b8aa951`](https://github.com/andythomas/matr1x/commit/b8aa951a1c0d60fb074e9c95d5a4e6ec9bb67907))

* fix(loadmatrix): code quality improvement *by Dominik Kriegner* ([`b8aa951`](https://github.com/andythomas/matr1x/commit/b8aa951a1c0d60fb074e9c95d5a4e6ec9bb67907))

* fix(pymeasure): monkey patch pymeasure Instrument to make it thread safe (#1443) *by Dominik Kriegner* ([`39dbd53`](https://github.com/andythomas/matr1x/commit/39dbd5356dcd060158cbcc06054f40444a31040a))

* fix(pymeasure): monkey patch pymeasure Instrument to make it thread safe *by Dominik Kriegner* ([`39dbd53`](https://github.com/andythomas/matr1x/commit/39dbd5356dcd060158cbcc06054f40444a31040a))

* fix: resort package dependencies (#1427) *by Andy Thomas* ([`8154170`](https://github.com/andythomas/matr1x/commit/81541707828980f82c0859039872d73bc5013766))

* fix: resort package dependencies *by Andy Thomas* ([`8154170`](https://github.com/andythomas/matr1x/commit/81541707828980f82c0859039872d73bc5013766))

* fix(pyproject.toml): address inconsistencies (#1422) *by Andy Thomas* ([`3cb89ac`](https://github.com/andythomas/matr1x/commit/3cb89ac6c8e6141f3f361f0d43d911b351c1a8f9))

* fix(pyproject.toml): address inconsistencies *by Andy Thomas* ([`3cb89ac`](https://github.com/andythomas/matr1x/commit/3cb89ac6c8e6141f3f361f0d43d911b351c1a8f9))

* fix(config): use matr1x.toml for local config file (#1416) *by Dominik Kriegner* ([`54ca196`](https://github.com/andythomas/matr1x/commit/54ca19620f7fe3a88233f646b00571a3fb8eab98))

* fix(matrix-script): make timeout=0 for input dialogs behave like infinity (#1401) *by Dominik Kriegner* ([`eeae8f2`](https://github.com/andythomas/matr1x/commit/eeae8f2711c05fd4030e4433f9f7847a685057db))

* fix(ifw-mustang, -zora): make Keitley2611A use raw (#1406) *by Andy Thomas* ([`007a95b`](https://github.com/andythomas/matr1x/commit/007a95bab8adbb035e906e12358b3de4dbb939b7))

* fix(ifw-mustang, -zora): make Keitley2611A use raw *by Andy Thomas* ([`007a95b`](https://github.com/andythomas/matr1x/commit/007a95bab8adbb035e906e12358b3de4dbb939b7))

* fix(control-gui): better error message for not running control-gui (#1363) *by Dominik Kriegner* ([`d3786e6`](https://github.com/andythomas/matr1x/commit/d3786e637c5e45c56f756d1f814711211d5a4e79))

* fix(error-handling): detect pymeasure device name for error reporting *by Dominik Kriegner* ([`d3786e6`](https://github.com/andythomas/matr1x/commit/d3786e637c5e45c56f756d1f814711211d5a4e79))

* fix(control-dummy): guard device access by threading lock (#1396) *by Dominik Kriegner* ([`27555fa`](https://github.com/andythomas/matr1x/commit/27555fa3c4f7ab9f4464329ca670f63249b08e12))

* fix(control-dummy): guard device access by threading lock *by Dominik Kriegner* ([`27555fa`](https://github.com/andythomas/matr1x/commit/27555fa3c4f7ab9f4464329ca670f63249b08e12))

* fix(matrix-script): report absolute file path of datafile *by Andy Thomas* ([`9610ec4`](https://github.com/andythomas/matr1x/commit/9610ec43042614d489671d81a3254e5c01641c1d))

* fix: address pyright errors (#1348) *by Andy Thomas* ([`11ab5f4`](https://github.com/andythomas/matr1x/commit/11ab5f43f52c39c91ac01ffa730447f1d0e9d3a1))

* fix(matrix-script): allow short timeout for user input dialogs (#1384) *by Dominik Kriegner* ([`59b4e96`](https://github.com/andythomas/matr1x/commit/59b4e962aebd278d1eeea97c7c8b2fb627b2851d))

* fix(matrix-script): allow short timeout for user input dialogs *by Dominik Kriegner* ([`59b4e96`](https://github.com/andythomas/matr1x/commit/59b4e962aebd278d1eeea97c7c8b2fb627b2851d))

* fix(matrix-script): report absolute file path of datafile *by Dominik Kriegner* ([`09adc66`](https://github.com/andythomas/matr1x/commit/09adc6674d683ab43e7019c97682157d76102afe))

* fix(scpi_dev): drop problematic "cast" type to avoid errors for certain types *by pheowl* ([`361ea76`](https://github.com/andythomas/matr1x/commit/361ea7600409fe4e5589fcb796f928f04177abac))

* fix(system.py-and-control.aja): revert changes *by pheowl* ([`361ea76`](https://github.com/andythomas/matr1x/commit/361ea7600409fe4e5589fcb796f928f04177abac))

* fix(system_vna_aesws): migrate to correct format and update globals *by pheowl* ([`361ea76`](https://github.com/andythomas/matr1x/commit/361ea7600409fe4e5589fcb796f928f04177abac))

* fix(fsw8.py): fix dual definitions, move detector outside of averaging if clause, remove excess statement *by pheowl* ([`361ea76`](https://github.com/andythomas/matr1x/commit/361ea7600409fe4e5589fcb796f928f04177abac))

* fix(scpi_dev): make code style consistent, add comment on reason for change *by pheowl* ([`361ea76`](https://github.com/andythomas/matr1x/commit/361ea7600409fe4e5589fcb796f928f04177abac))

* fix(pytest): fix automatic testing for Python 3.9 (#1365) *by Andy Thomas* ([`bd1eab5`](https://github.com/andythomas/matr1x/commit/bd1eab52810c61249937a187b0272a5ff3d0928b))

* fix(pytest): fix automatic testing for Python 3.9 *by Andy Thomas* ([`bd1eab5`](https://github.com/andythomas/matr1x/commit/bd1eab52810c61249937a187b0272a5ff3d0928b))

* fix: recover python3.9 function (#1358) *by Andy Thomas* ([`05f2eb8`](https://github.com/andythomas/matr1x/commit/05f2eb828935dbd633c5dc76060a901c0dc8587d))

* fix: recover python3.9 *by Andy Thomas* ([`05f2eb8`](https://github.com/andythomas/matr1x/commit/05f2eb828935dbd633c5dc76060a901c0dc8587d))

### Build system

* build(ppms): adjust dependency due to upstream fix (#1463) *by Dominik Kriegner* ([`6a89230`](https://github.com/andythomas/matr1x/commit/6a89230d81d3ff3a6c4cc7582bd328e59dc65f84))

### Documentation

* docs(sphinx): update the sphinx config for automatic docs generation (#1354) *by Andy Thomas* ([`bdb1ac5`](https://github.com/andythomas/matr1x/commit/bdb1ac535358fffadd21c94d6d13e2a4ca655650))

### Features

* feat(aardvark): introduce new cryostat Aardvark (#1440) *by Andy Thomas* ([`e5abafe`](https://github.com/andythomas/matr1x/commit/e5abafedddaf6865bf270a8ffdf2294247519603))

* feat(matrix-preview): add "New preview" (#1434) *by Andy Thomas* ([`4d7bd29`](https://github.com/andythomas/matr1x/commit/4d7bd297e344e6f8b1242e747c0bc51097dc5130))

* feat(matrix-preview): add "New preview" *by Andy Thomas* ([`4d7bd29`](https://github.com/andythomas/matr1x/commit/4d7bd297e344e6f8b1242e747c0bc51097dc5130))

* feat(toml): introduce configuration validation (#1375) *by Andy Thomas* ([`70a564b`](https://github.com/andythomas/matr1x/commit/70a564b8112d0a868453c32572df684834ea05c6))

* feat(toml): introduce configuration validation *by Andy Thomas* ([`70a564b`](https://github.com/andythomas/matr1x/commit/70a564b8112d0a868453c32572df684834ea05c6))

* feat(gui-scripts): Locate matr1x toml (#1411) *by Andy Thomas* ([`7e558d6`](https://github.com/andythomas/matr1x/commit/7e558d65ab1b3c08647b9d248e84aa20b864958e))

* feat(gui-scripts): Locate matr1x toml *by Andy Thomas* ([`7e558d6`](https://github.com/andythomas/matr1x/commit/7e558d65ab1b3c08647b9d248e84aa20b864958e))

* feat(config): show system config options consistently in the preferences *by Andy Thomas* ([`9610ec4`](https://github.com/andythomas/matr1x/commit/9610ec43042614d489671d81a3254e5c01641c1d))

* feat(config): make temporary config options work (#1330) *by Dominik Kriegner* ([`09adc66`](https://github.com/andythomas/matr1x/commit/09adc6674d683ab43e7019c97682157d76102afe))

* feat(config): show system config options consistently in the preferences *by Dominik Kriegner* ([`09adc66`](https://github.com/andythomas/matr1x/commit/09adc6674d683ab43e7019c97682157d76102afe))

* feat(Optab update): get most recent changes from the TRASH lab - prepare update to current version (#1341) *by pheowl* ([`361ea76`](https://github.com/andythomas/matr1x/commit/361ea7600409fe4e5589fcb796f928f04177abac))

* feat(control_sane): implement changes to sane control for new setup *by pheowl* ([`361ea76`](https://github.com/andythomas/matr1x/commit/361ea7600409fe4e5589fcb796f928f04177abac))

* feat(system_waferprober): add system for custom wafer prober *by pheowl* ([`361ea76`](https://github.com/andythomas/matr1x/commit/361ea7600409fe4e5589fcb796f928f04177abac))

* feat(elise-systems): implement changes to system elise *by pheowl* ([`361ea76`](https://github.com/andythomas/matr1x/commit/361ea7600409fe4e5589fcb796f928f04177abac))

* feat(system_aesws): add system for spin wave spectroscopy *by pheowl* ([`361ea76`](https://github.com/andythomas/matr1x/commit/361ea7600409fe4e5589fcb796f928f04177abac))

## v8.0.1 (2025-07-14)

## v8.0.0 (2025-07-14)

### Bug fixes

* fix(nvm): 2nd attempt to fix Keithley2182A.configure method with reset=False (#1340) *by Dominik Kriegner* ([`8170268`](https://github.com/andythomas/matr1x/commit/81702687252b46d1899ed90aac8c5b9fe60eed1a))

* fix(NVM): make configure of a Keithley2182a work with reset=False *by Dominik Kriegner* ([`8170268`](https://github.com/andythomas/matr1x/commit/81702687252b46d1899ed90aac8c5b9fe60eed1a))

* fix(NVM): make configure of a Keithley2182a work with reset=False (#1339) *by Dominik Kriegner* ([`902b108`](https://github.com/andythomas/matr1x/commit/902b108765288c5bd635b6403c2796d680f1e1bd))

* fix(PPMS): connecting to the server by the with statement *by Dominik Kriegner* ([`50cd243`](https://github.com/andythomas/matr1x/commit/50cd24313cd350a8ed0851010eea81041d784220))

* fix: system renaming *by Dominik Kriegner* ([`50cd243`](https://github.com/andythomas/matr1x/commit/50cd24313cd350a8ed0851010eea81041d784220))

* fix(system_FZU_PPMS): small fixes for the FZU PPMS system *by Dominik Kriegner* ([`50cd243`](https://github.com/andythomas/matr1x/commit/50cd24313cd350a8ed0851010eea81041d784220))

* fix: ppms driver connection *by Dominik Kriegner* ([`50cd243`](https://github.com/andythomas/matr1x/commit/50cd24313cd350a8ed0851010eea81041d784220))

* fix: PPMS system IP address *by Dominik Kriegner* ([`50cd243`](https://github.com/andythomas/matr1x/commit/50cd24313cd350a8ed0851010eea81041d784220))

* fix(matrix-script): correctly enable remove system button (#1317) *by Dominik Kriegner* ([`4840d5a`](https://github.com/andythomas/matr1x/commit/4840d5aa3648af50548442579c74cd4a42dfdabe))

* fix(matrix-script): handling of newlines in input functions (#1313) *by Dominik Kriegner* ([`a33d994`](https://github.com/andythomas/matr1x/commit/a33d994bbfa3bed32888a75108b85650283bdfdb))

* fix(loadmatrix): correct parsing of multidevice nested query strings (#1307) *by Dominik Kriegner* ([`dad851b`](https://github.com/andythomas/matr1x/commit/dad851b7108ddbd2a19c6a05566737fd9c3463b4))

* fix(loadmatrix): correct parsing of multidevice nested query strings *by Dominik Kriegner* ([`dad851b`](https://github.com/andythomas/matr1x/commit/dad851b7108ddbd2a19c6a05566737fd9c3463b4))

* fix(matrix-script): add back system methods and improve help formatting. (#1287) *by Dominik Kriegner* ([`11b626a`](https://github.com/andythomas/matr1x/commit/11b626a31567b350b2320a2e9a3114182abab09a))

* fix(matrix-script): add back system methods and improve help formatting. *by Dominik Kriegner* ([`11b626a`](https://github.com/andythomas/matr1x/commit/11b626a31567b350b2320a2e9a3114182abab09a))

* fix(matrix-script): execution of empty scripts (#1280) *by Dominik Kriegner* ([`bb359aa`](https://github.com/andythomas/matr1x/commit/bb359aa04c1d0d4625253ed91e1ce3a352de4d99))

* fix(matrix-script): execution of empty scripts *by Dominik Kriegner* ([`bb359aa`](https://github.com/andythomas/matr1x/commit/bb359aa04c1d0d4625253ed91e1ce3a352de4d99))

* fix(matrix-script): extract column names correctly on windows (#1264) *by Dominik Kriegner* ([`83fc077`](https://github.com/andythomas/matr1x/commit/83fc0772abce78c9192d27e8d66859e34da7069c))

* fix(matrix-script): extract column names correctly on windows *by Dominik Kriegner* ([`83fc077`](https://github.com/andythomas/matr1x/commit/83fc0772abce78c9192d27e8d66859e34da7069c))

* fix(elabftw): better disable elabftw after connection error (#1265) *by Dominik Kriegner* ([`1c976a2`](https://github.com/andythomas/matr1x/commit/1c976a2ad757171e27598e5aa200bd848a04ea5b))

* fix(matrix-script): allow system help scrollbar (#1271) *by Andy Thomas* ([`2ac25a1`](https://github.com/andythomas/matr1x/commit/2ac25a10eaebfa6b00c96f827018d6a782596020))

* fix(matrix-script): allow system help scrollbar *by Andy Thomas* ([`2ac25a1`](https://github.com/andythomas/matr1x/commit/2ac25a10eaebfa6b00c96f827018d6a782596020))

* fix(sweep-generator): add "append to" action (#1268) *by Andy Thomas* ([`be16f17`](https://github.com/andythomas/matr1x/commit/be16f17f26c846784525bcb647770f50646a112b))

* fix(sweep-generator): add "append to" action *by Andy Thomas* ([`be16f17`](https://github.com/andythomas/matr1x/commit/be16f17f26c846784525bcb647770f50646a112b))

* fix(matrix_script): migrate custom linter to ast.parse *by Andy Thomas* ([`f913e6c`](https://github.com/andythomas/matr1x/commit/f913e6c5270438fe39b97273d23e7b3578e9443b))

* fix(matrix_script): fix minor details and missing check *by Andy Thomas* ([`f913e6c`](https://github.com/andythomas/matr1x/commit/f913e6c5270438fe39b97273d23e7b3578e9443b))

* fix(matrix-script): fix issue with non-termination of error checker after error found *by Andy Thomas* ([`f913e6c`](https://github.com/andythomas/matr1x/commit/f913e6c5270438fe39b97273d23e7b3578e9443b))

* fix: remove try+except clauses for type checking *by baduraan* ([`fe94b1e`](https://github.com/andythomas/matr1x/commit/fe94b1eff00da10d0e8290cbb0fc9f5504aa211f))

* fix(matrix-script): wrong use of global statement and missing definition (#1242) *by Dominik Kriegner* ([`8899967`](https://github.com/andythomas/matr1x/commit/88999679e7831ae3021ac6a763c2e1f726036dcf))

* fix(matrix-script): wrong use of global statement and missing definition *by Dominik Kriegner* ([`8899967`](https://github.com/andythomas/matr1x/commit/88999679e7831ae3021ac6a763c2e1f726036dcf))

* fix(matrix-script): disable metadata during run (#1229) *by Andy Thomas* ([`959fe57`](https://github.com/andythomas/matr1x/commit/959fe57268c5d44f0ee4e8081359d55d8af8afb5))

* fix(matrix-script): disable metadata during run *by Andy Thomas* ([`959fe57`](https://github.com/andythomas/matr1x/commit/959fe57268c5d44f0ee4e8081359d55d8af8afb5))

* fix(sweep-generator): restore open file function (#1226) *by Andy Thomas* ([`f1c9656`](https://github.com/andythomas/matr1x/commit/f1c96562e6dcfd655a4e7059a75a70b892bfeb93))

* fix(AboutBox): show git branch correctly if in detached head state (#1218) *by Dominik Kriegner* ([`e3be570`](https://github.com/andythomas/matr1x/commit/e3be570911038866a410c6e255e2920b4459cb96))

* fix(AboutBox): show git branch correctly if in detached head state *by Dominik Kriegner* ([`e3be570`](https://github.com/andythomas/matr1x/commit/e3be570911038866a410c6e255e2920b4459cb96))

* fix(matrix-script): allow to run multiple instances of matrix-script (#1204) *by Dominik Kriegner* ([`0777320`](https://github.com/andythomas/matr1x/commit/077732037255252326e8bb99db2fd481aa166bc9))

* fix(matrix-script): allow to run multiple instances of matrix-script *by Dominik Kriegner* ([`0777320`](https://github.com/andythomas/matr1x/commit/077732037255252326e8bb99db2fd481aa166bc9))

* fix(util): Returns functional line highlighting for python 3.13 (#1201) *by pheowl* ([`c3b6302`](https://github.com/andythomas/matr1x/commit/c3b6302291f3de2af0b92fdb331873aaa475bdcb))

* fix(util): return highlighter to working condition for python >3.13, also steps into functions *by pheowl* ([`c3b6302`](https://github.com/andythomas/matr1x/commit/c3b6302291f3de2af0b92fdb331873aaa475bdcb))

* fix(matrix_script,-util): remove unused parts of code and simplify, fix error statement in matrix_script *by pheowl* ([`c3b6302`](https://github.com/andythomas/matr1x/commit/c3b6302291f3de2af0b92fdb331873aaa475bdcb))

* fix(prcheck): detect changes applied by ruff in the github action (#1202) *by Dominik Kriegner* ([`11041b4`](https://github.com/andythomas/matr1x/commit/11041b4289a7fccea3fa0bb64d99651d5ec558f0))

* fix(prcheck): detect changes applied by ruff in the github action *by Dominik Kriegner* ([`11041b4`](https://github.com/andythomas/matr1x/commit/11041b4289a7fccea3fa0bb64d99651d5ec558f0))

* fix(system.py): minimal fix to avoid rewriting of format info to meta data on every format check (#1142) *by pheowl* ([`8691103`](https://github.com/andythomas/matr1x/commit/86911037cd9de3a6bb38a506e1590a66f7f49c86))

* fix(system.py): minimal fix to avoid rewriting of format info to meta data on every format check *by pheowl* ([`8691103`](https://github.com/andythomas/matr1x/commit/86911037cd9de3a6bb38a506e1590a66f7f49c86))

* fix(util.py): address comments by @dkriegner *by pheowl* ([`8691103`](https://github.com/andythomas/matr1x/commit/86911037cd9de3a6bb38a506e1590a66f7f49c86))

* fix(matrix-script): remove leftover line using undefined variable (#1195) *by Dominik Kriegner* ([`cd9e687`](https://github.com/andythomas/matr1x/commit/cd9e68717a86e4b1db1884d35733b66e99296a42))

* fix(Linux): Gtk palette bugfix (#1149) *by Andy Thomas* ([`bac3ffe`](https://github.com/andythomas/matr1x/commit/bac3ffe859103595da740a774a955085c34f7da6))

* fix(sweep_generator): make line breaks work in popup and improve text to help identifying the error *by Andy Thomas* ([`44b3663`](https://github.com/andythomas/matr1x/commit/44b36636b0abdb4a95ecf991a584fb9e515e832b))

* fix(matrix_preview.py): avoid window creep (#1127) *by Andy Thomas* ([`1a73b5e`](https://github.com/andythomas/matr1x/commit/1a73b5e8fd7fdbe35f7e96da13504f8f3b9e0f10))

* fix(matrix_preview.py): avoid window creep *by Andy Thomas* ([`1a73b5e`](https://github.com/andythomas/matr1x/commit/1a73b5e8fd7fdbe35f7e96da13504f8f3b9e0f10))

* fix: removing unnecessary connection clean-up *by Dominik Kriegner* ([`0567c71`](https://github.com/andythomas/matr1x/commit/0567c71daba6516b1ddb89bdcdfc987c1b08f19e))

* fix: removing shadowing "range" parameter in DMM6500 *by Dominik Kriegner* ([`fc049ec`](https://github.com/andythomas/matr1x/commit/fc049ec278a085e97e2801ebaa2f213c34cdab8a))

* fix: update copyright (#1123) *by Andy Thomas* ([`10e80a5`](https://github.com/andythomas/matr1x/commit/10e80a57f33494b5f4919f51fd9aab77909c1ad1))

* fix: update copyright *by Andy Thomas* ([`10e80a5`](https://github.com/andythomas/matr1x/commit/10e80a57f33494b5f4919f51fd9aab77909c1ad1))

* fix(lakeshore.py): use 'loop' for all heater functions (#1124) *by Andy Thomas* ([`eb99949`](https://github.com/andythomas/matr1x/commit/eb99949f6df0cd0da10c2e593d3e4b44883cd242))

* fix(lakeshore.py): use 'loop' for heater functions *by Andy Thomas* ([`eb99949`](https://github.com/andythomas/matr1x/commit/eb99949f6df0cd0da10c2e593d3e4b44883cd242))

* fix(matrix-script): clarify dialog for 'Open' (#1126) *by Andy Thomas* ([`db939e8`](https://github.com/andythomas/matr1x/commit/db939e8bf8dac944496ac429e570e51fc3c282a2))

* fix(controlwindow.py): allow one guidict (#1121) *by Andy Thomas* ([`b7b8f56`](https://github.com/andythomas/matr1x/commit/b7b8f56975e9994a0640bc729dceb0b4e1482df7))

* fix(controlwindow.py): allow one guidict *by Andy Thomas* ([`b7b8f56`](https://github.com/andythomas/matr1x/commit/b7b8f56975e9994a0640bc729dceb0b4e1482df7))

* fix(elab): redirect config read to core library (#1106) *by Dominik Kriegner* ([`39ccecf`](https://github.com/andythomas/matr1x/commit/39ccecf25c6a3940d7e3598f2305daf5f22b4116))

* fix: fix Qt 6.5 color palette on some linux machines (#1104) *by Andy Thomas* ([`510579e`](https://github.com/andythomas/matr1x/commit/510579e296b196527c628b08c52aa3c1a4c7f187))

* fix: fix color palette *by Andy Thomas* ([`510579e`](https://github.com/andythomas/matr1x/commit/510579e296b196527c628b08c52aa3c1a4c7f187))

* fix(System): correctly support nested properties for parameters (#1100) *by Dominik Kriegner* ([`f7314d0`](https://github.com/andythomas/matr1x/commit/f7314d0ac988e7c887c40eac60ebd78b78f9cde3))

* fix(system_elabftw): make resetting of tags in elab_post configurable by parameter *by pheowl* ([`a5fef37`](https://github.com/andythomas/matr1x/commit/a5fef379b129ddaa9d69c9128d7b63d1eb7b5ec0))

* fix(system_elab): avoid automatic creation of measurement entry if there is no data file *by pheowl* ([`71c3704`](https://github.com/andythomas/matr1x/commit/71c370417129636a10fa4976e2e13d398072f1d5))

* fix(system_elabftw): testing and bugfixes *by pheowl* ([`71c3704`](https://github.com/andythomas/matr1x/commit/71c370417129636a10fa4976e2e13d398072f1d5))

* fix(thorlabs,-control_sane): fix review comments *by pheowl* ([`644efb1`](https://github.com/andythomas/matr1x/commit/644efb1a1cc12cb4dd91125af3be894e8f90d913))

* fix(system_vna): migrate vna to use config *by pheowl* ([`644efb1`](https://github.com/andythomas/matr1x/commit/644efb1a1cc12cb4dd91125af3be894e8f90d913))

* fix(matrix-script): make the line number into more reasonable 10000 *by pheowl* ([`a2b0f26`](https://github.com/andythomas/matr1x/commit/a2b0f2698756aba161dd715e9609ca29dbb23808))

* fix(matrix-script): rely on internal qt function for limiting. increase boundary to allow for printing of roughly 100 lines/s while without introducing extensive delay *by pheowl* ([`a2b0f26`](https://github.com/andythomas/matr1x/commit/a2b0f2698756aba161dd715e9609ca29dbb23808))

* fix(gui_util): fix scrolling mode of meta data viewer to allow viewing larger entries than height of window *by pheowl* ([`9e254d5`](https://github.com/andythomas/matr1x/commit/9e254d5fc875d2b517d47b4e32cfc6f585ab7e24))

* fix(gui_util): restore scroll bar position on meta-data update *by pheowl* ([`9e254d5`](https://github.com/andythomas/matr1x/commit/9e254d5fc875d2b517d47b4e32cfc6f585ab7e24))

* fix(gui_util): fix missing check for key existence *by pheowl* ([`9e254d5`](https://github.com/andythomas/matr1x/commit/9e254d5fc875d2b517d47b4e32cfc6f585ab7e24))

* fix(gui_util): make file editor work, based on callback *by pheowl* ([`0bd67b5`](https://github.com/andythomas/matr1x/commit/0bd67b5e4b86eeb69e2b4a4f9fac4421f9b7637e))

* fix(gui_util): remove outdated todo *by pheowl* ([`0bd67b5`](https://github.com/andythomas/matr1x/commit/0bd67b5e4b86eeb69e2b4a4f9fac4421f9b7637e))

* fix(gui_util): fix issue introduced by linter *by pheowl* ([`0bd67b5`](https://github.com/andythomas/matr1x/commit/0bd67b5e4b86eeb69e2b4a4f9fac4421f9b7637e))

* fix(gui_util): remove reintroduced line *by pheowl* ([`0bd67b5`](https://github.com/andythomas/matr1x/commit/0bd67b5e4b86eeb69e2b4a4f9fac4421f9b7637e))

* fix(matr1x.__init__): add function that allows to reload the configuration *by pheowl* ([`0bd67b5`](https://github.com/andythomas/matr1x/commit/0bd67b5e4b86eeb69e2b4a4f9fac4421f9b7637e))

* fix(matr1x.init): make it a one line comment *by pheowl* ([`0bd67b5`](https://github.com/andythomas/matr1x/commit/0bd67b5e4b86eeb69e2b4a4f9fac4421f9b7637e))

* fix(gui_util): fix missing call when parsing bool values *by pheowl* ([`0bd67b5`](https://github.com/andythomas/matr1x/commit/0bd67b5e4b86eeb69e2b4a4f9fac4421f9b7637e))

* fix(gui_util): hide value while editor is active *by pheowl* ([`0bd67b5`](https://github.com/andythomas/matr1x/commit/0bd67b5e4b86eeb69e2b4a4f9fac4421f9b7637e))

* fix: save and restore config editor properties (#1084) *by Andy Thomas* ([`231cf0c`](https://github.com/andythomas/matr1x/commit/231cf0c7798247b012db2ef3d518f83e2f17b5ff))

* fix: save and restore config editor properties *by Andy Thomas* ([`231cf0c`](https://github.com/andythomas/matr1x/commit/231cf0c7798247b012db2ef3d518f83e2f17b5ff))

* fix(update-script): no save-nag for empty script (#1079) *by Andy Thomas* ([`13bb3ee`](https://github.com/andythomas/matr1x/commit/13bb3ee63c18a244c4f1d8ffb46bee9e527ba1cd))

* fix(update-script): no save-nag for empty script *by Andy Thomas* ([`13bb3ee`](https://github.com/andythomas/matr1x/commit/13bb3ee63c18a244c4f1d8ffb46bee9e527ba1cd))

* fix(DcData): avoid '@ap:' when entry is empty (#1076) *by Dominik Kriegner* ([`d5c67c6`](https://github.com/andythomas/matr1x/commit/d5c67c6403343dbc6345ec7a6dce1222819db974))

* fix: disable remove system for empty system list (#1070) *by Andy Thomas* ([`7206a6e`](https://github.com/andythomas/matr1x/commit/7206a6e1858fa20611d60a409db88360124eb688))

* fix: allow xcb selection (#1065) *by Andy Thomas* ([`aa46274`](https://github.com/andythomas/matr1x/commit/aa46274e752e58abe33424e408cfeaa442380634))

* fix(gui_util): avoid system duplicates (#1041) *by Andy Thomas* ([`1bdc84d`](https://github.com/andythomas/matr1x/commit/1bdc84d46610adc14cdf89b392ce2d51a3ec782e))

* fix(gui_util): avoid system duplicates *by Andy Thomas* ([`1bdc84d`](https://github.com/andythomas/matr1x/commit/1bdc84d46610adc14cdf89b392ce2d51a3ec782e))

* fix(matrix-script): make executing line highlighting work more reliable (#1011) *by Dominik Kriegner* ([`122f279`](https://github.com/andythomas/matr1x/commit/122f2798b655c1ea394bd8cb40962b6e473a9995))

* fix(matrix-script): make executing line highlighting work more reliable *by Dominik Kriegner* ([`122f279`](https://github.com/andythomas/matr1x/commit/122f2798b655c1ea394bd8cb40962b6e473a9995))

* fix(system_chaos): migrate to new format, remove excess code *by pheowl* ([`f3d445f`](https://github.com/andythomas/matr1x/commit/f3d445f16ce1f85e54a0d8fea64281768aefe516))

* fix(system_chaos): migrate to new format, remove excess code *by pheowl* ([`1dea8d4`](https://github.com/andythomas/matr1x/commit/1dea8d4c9fab5b0e7e52570e5d902a24da8be941))

* fix: regain python 3.9 compatibility (#978) *by Andy Thomas* ([`6ca9eb5`](https://github.com/andythomas/matr1x/commit/6ca9eb510832bbd368c4e6e1083de3b54a5e5951))

* fix(EmittingStream): correct use of class constructor (#981) *by Dominik Kriegner* ([`f78e191`](https://github.com/andythomas/matr1x/commit/f78e191b4e62d63928bd8a776590e4e4400d2de2))

* fix(eval): add missing import *by Dominik Kriegner* ([`bd11cad`](https://github.com/andythomas/matr1x/commit/bd11cadc0758176c2e38ffa883ec48bd2a428d70))

### Code style

* style: fix various random linting errors detected by flake8 (#1294) *by Dominik Kriegner* ([`732a4a8`](https://github.com/andythomas/matr1x/commit/732a4a8e4b1d52edb9aa9455ed33349b3aae0a6f))

* style: fix various random linting errors detected by flake8 *by Dominik Kriegner* ([`732a4a8`](https://github.com/andythomas/matr1x/commit/732a4a8e4b1d52edb9aa9455ed33349b3aae0a6f))

* style: modify icons and colors to improve legibility (in dark mode) (#985) *by Andy Thomas* ([`f90c17b`](https://github.com/andythomas/matr1x/commit/f90c17ba6075da3c7cea44fa6529513c0f9337f4))

### Documentation

* docs(tests): add docstrings to test code and remove ruff exception (#1279) *by Dominik Kriegner* ([`c7a0caf`](https://github.com/andythomas/matr1x/commit/c7a0cafb495962b1e9a3f42e2aade6dd7cf796fa))

* docs: discourage device package use (#1266) *by Dominik Kriegner* ([`d137b99`](https://github.com/andythomas/matr1x/commit/d137b99bd064071130e037e768b51240b26cc16b))

* docs: discourage device package use *by Dominik Kriegner* ([`d137b99`](https://github.com/andythomas/matr1x/commit/d137b99bd064071130e037e768b51240b26cc16b))

* docs(matrix-script): add documentation on testing the limit *by pheowl* ([`a2b0f26`](https://github.com/andythomas/matr1x/commit/a2b0f2698756aba161dd715e9609ca29dbb23808))

* docs(gui_util): improve docs for linter *by pheowl* ([`0bd67b5`](https://github.com/andythomas/matr1x/commit/0bd67b5e4b86eeb69e2b4a4f9fac4421f9b7637e))

* docs(gui_util): further improve docs *by pheowl* ([`0bd67b5`](https://github.com/andythomas/matr1x/commit/0bd67b5e4b86eeb69e2b4a4f9fac4421f9b7637e))

* docs(matr1x.__init__): add docs *by pheowl* ([`0bd67b5`](https://github.com/andythomas/matr1x/commit/0bd67b5e4b86eeb69e2b4a4f9fac4421f9b7637e))

* docs(visadevice): add note on negative time delays *by pheowl* ([`f3d445f`](https://github.com/andythomas/matr1x/commit/f3d445f16ce1f85e54a0d8fea64281768aefe516))

* docs(visadevice): add note on negative time delays *by pheowl* ([`1dea8d4`](https://github.com/andythomas/matr1x/commit/1dea8d4c9fab5b0e7e52570e5d902a24da8be941))

* docs(v8): add migration notes for version 8 (#980) *by Dominik Kriegner* ([`5be9582`](https://github.com/andythomas/matr1x/commit/5be9582be69c57ae02de9504e16ff860837e8ba6))

* docs(v8): add migration notes for version 8 *by Dominik Kriegner* ([`5be9582`](https://github.com/andythomas/matr1x/commit/5be9582be69c57ae02de9504e16ff860837e8ba6))

### Features

* feat: introduce tray notifications (#1328) *by Andy Thomas* ([`b5aaf3d`](https://github.com/andythomas/matr1x/commit/b5aaf3d0ba7daca07e7a063fcfea54022d2c74ff))

* feat: introduce tray notifications *by Andy Thomas* ([`b5aaf3d`](https://github.com/andythomas/matr1x/commit/b5aaf3d0ba7daca07e7a063fcfea54022d2c74ff))

* feat(PPMS): add Quantum design drivers and control GUI for a PPMS (#1320) *by Dominik Kriegner* ([`50cd243`](https://github.com/andythomas/matr1x/commit/50cd24313cd350a8ed0851010eea81041d784220))

* feat: correct handling of the voltage and current source mode in 2400 *by Dominik Kriegner* ([`50cd243`](https://github.com/andythomas/matr1x/commit/50cd24313cd350a8ed0851010eea81041d784220))

* feat(devices): new PPMS device *by Dominik Kriegner* ([`50cd243`](https://github.com/andythomas/matr1x/commit/50cd24313cd350a8ed0851010eea81041d784220))

* feat(control_fzu): new control window for FZU PPMS *by Dominik Kriegner* ([`50cd243`](https://github.com/andythomas/matr1x/commit/50cd24313cd350a8ed0851010eea81041d784220))

* feat(ppms): ppms updates *by Dominik Kriegner* ([`50cd243`](https://github.com/andythomas/matr1x/commit/50cd24313cd350a8ed0851010eea81041d784220))

* feat: adding a new PPMS device *by Dominik Kriegner* ([`50cd243`](https://github.com/andythomas/matr1x/commit/50cd24313cd350a8ed0851010eea81041d784220))

* feat: new control window for the PPMS *by Dominik Kriegner* ([`50cd243`](https://github.com/andythomas/matr1x/commit/50cd24313cd350a8ed0851010eea81041d784220))

* feat: new system for PPMS control window *by Dominik Kriegner* ([`50cd243`](https://github.com/andythomas/matr1x/commit/50cd24313cd350a8ed0851010eea81041d784220))

* feat: common system for PPMS *by Dominik Kriegner* ([`50cd243`](https://github.com/andythomas/matr1x/commit/50cd24313cd350a8ed0851010eea81041d784220))

* feat(controlgui): simplify use of var objects by new default outType (#1318) *by Dominik Kriegner* ([`8326148`](https://github.com/andythomas/matr1x/commit/8326148b776afac951b37db4ad457c46e43eae33))

* feat(controlgui): simplify use of var objects by new default outType value *by Dominik Kriegner* ([`8326148`](https://github.com/andythomas/matr1x/commit/8326148b776afac951b37db4ad457c46e43eae33))

* feat(HorstHTMC11): add device driver for bakeout controller (#1018) *by Dominik Kriegner* ([`388ee8c`](https://github.com/andythomas/matr1x/commit/388ee8c2a0b835c0c7a3f89ca4cd57b4fbd73f82))

* feat(HorstHTMC11): add device driver for bakeout controller *by Dominik Kriegner* ([`388ee8c`](https://github.com/andythomas/matr1x/commit/388ee8c2a0b835c0c7a3f89ca4cd57b4fbd73f82))

* feat(matrix-preview): link x-axis limits of subplots (#1309) *by Dominik Kriegner* ([`8003394`](https://github.com/andythomas/matr1x/commit/8003394f09523219ab3586211decfa6413ef5cda))

* feat(matrix-preview): link x-axis limits of subplots if the use the same x-column *by Dominik Kriegner* ([`8003394`](https://github.com/andythomas/matr1x/commit/8003394f09523219ab3586211decfa6413ef5cda))

* feat(matrix-script): optional timeout option for user input dialogs (#1283) *by Dominik Kriegner* ([`c249cbe`](https://github.com/andythomas/matr1x/commit/c249cbed4f9d5b63126c85ba99ad7e13d5581b95))

* feat(matrix-script): optional timeout option for user input dialogs *by Dominik Kriegner* ([`c249cbe`](https://github.com/andythomas/matr1x/commit/c249cbed4f9d5b63126c85ba99ad7e13d5581b95))

* feat(gui_util): add update button to allow reloading config from file (#1282) *by pheowl* ([`c870cbe`](https://github.com/andythomas/matr1x/commit/c870cbe5fe7b67b911c2df47418671c816d5b2f6))

* feat(matrix-script): column name linter (#1144) *by Andy Thomas* ([`f913e6c`](https://github.com/andythomas/matr1x/commit/f913e6c5270438fe39b97273d23e7b3578e9443b))

* feat(matrix-script): provide information on how to highlight custom errors *by Andy Thomas* ([`f913e6c`](https://github.com/andythomas/matr1x/commit/f913e6c5270438fe39b97273d23e7b3578e9443b))

* feat(Lakeshore 335): implementing functions for Lakeshore 335 control *by baduraan* ([`484c277`](https://github.com/andythomas/matr1x/commit/484c277d6e02aaf839fb3f6baddaacba9676e66c))

* feat(elab): allow disabling the elabftw system by a config setting (#1254) *by Dominik Kriegner* ([`a55a611`](https://github.com/andythomas/matr1x/commit/a55a61114f6945d778255a5509331bd20edbd3a9))

* feat(elabftw): allow use in sweep-generator without server access (#1221) *by Dominik Kriegner* ([`8c10bb4`](https://github.com/andythomas/matr1x/commit/8c10bb4185ff77052be5000e9e0cd12131f54ea5))

* feat(elabftw): allow use in sweep-generator without server access *by Dominik Kriegner* ([`8c10bb4`](https://github.com/andythomas/matr1x/commit/8c10bb4185ff77052be5000e9e0cd12131f54ea5))

* feat(sweep-generator): Indicate save state in the window title (#1222) *by Andy Thomas* ([`c4b3627`](https://github.com/andythomas/matr1x/commit/c4b362766be9ff20369ad520738aca3cece1c0f4))

* feat(sweep-generator): run "draft sweep" on open (#1245) *by Andy Thomas* ([`97f63ce`](https://github.com/andythomas/matr1x/commit/97f63ce318e95b14819eede4367eb92077b14cf6))

* feat(matrix-script): provide information on how to highlight custom errors *by Andy Thomas* ([`48679e7`](https://github.com/andythomas/matr1x/commit/48679e7c4af5a199ad55d8953a6a8ee890292e61))

* feat(sweep-generator): allow multi-row parameter settings (#1199) *by Andy Thomas* ([`2b2016f`](https://github.com/andythomas/matr1x/commit/2b2016f48844adef7e2dd31c231f39a04e8502b0))

* feat(matrix-script): add more functions to menu (#1214) *by Andy Thomas* ([`0e868e4`](https://github.com/andythomas/matr1x/commit/0e868e439c2a980e7ddcda33cdbd78874c31ce76))

* feat(controlgui): allow running multiple controlguis in parallel (#1211) *by Dominik Kriegner* ([`034264f`](https://github.com/andythomas/matr1x/commit/034264fe86e6a3b64311d46009a57932432ee098))

* feat(controlgui): allow running multiple controlguis in parallel *by Dominik Kriegner* ([`034264f`](https://github.com/andythomas/matr1x/commit/034264fe86e6a3b64311d46009a57932432ee098))

* feat(controlgui): allow initial values for progressbar gui entries (#1210) *by Dominik Kriegner* ([`4e69e29`](https://github.com/andythomas/matr1x/commit/4e69e29f36e8d782e1cfde8557e239b02f3d4ebf))

* feat(sweep-generator): selected column visual cue *by Andy Thomas* ([`21ab970`](https://github.com/andythomas/matr1x/commit/21ab970c386d4fc0c66d7c751790f5a69c53ea9f))

* feat(controlwindow.py): introduce menu and toolbar (#1132) *by Andy Thomas* ([`475062a`](https://github.com/andythomas/matr1x/commit/475062a968db01f6604dd5c77b3964fc9a25ccad))

* feat(controlwindow.py): introduce menubar *by Andy Thomas* ([`475062a`](https://github.com/andythomas/matr1x/commit/475062a968db01f6604dd5c77b3964fc9a25ccad))

* feat(sweep-generator): selected column visual cue (#1162) *by Andy Thomas* ([`1a5f521`](https://github.com/andythomas/matr1x/commit/1a5f5217343c882004d10bc56b7491f5ef733782))

* feat(sweep-generator): selected column visual cue *by Andy Thomas* ([`1a5f521`](https://github.com/andythomas/matr1x/commit/1a5f5217343c882004d10bc56b7491f5ef733782))

* feat: add "New file" to matrix-script and sweep generator (#1130) *by Andy Thomas* ([`e5009a8`](https://github.com/andythomas/matr1x/commit/e5009a82e3510c5f6813b39f7ec68e0da61a2ee5))

* feat(matrix-script.py): add 'New File' option *by Andy Thomas* ([`e5009a8`](https://github.com/andythomas/matr1x/commit/e5009a82e3510c5f6813b39f7ec68e0da61a2ee5))

* feat(system_elabftw): add filename to title, parse first line of description for tags (#1092) *by pheowl* ([`71c3704`](https://github.com/andythomas/matr1x/commit/71c370417129636a10fa4976e2e13d398072f1d5))

* feat(system_elabftw): add filename to title, parse first line of description for tags *by pheowl* ([`71c3704`](https://github.com/andythomas/matr1x/commit/71c370417129636a10fa4976e2e13d398072f1d5))

* feat(optab): updates and fixes from optical table setup (#1094) *by pheowl* ([`644efb1`](https://github.com/andythomas/matr1x/commit/644efb1a1cc12cb4dd91125af3be894e8f90d913))

* feat(matrix-script): limit maximum number of lines in matrix-script status preview (#1089) *by pheowl* ([`a2b0f26`](https://github.com/andythomas/matr1x/commit/a2b0f2698756aba161dd715e9609ca29dbb23808))

* feat(matrix-script): limit maximum number of lines in matrix-script status preview *by pheowl* ([`a2b0f26`](https://github.com/andythomas/matr1x/commit/a2b0f2698756aba161dd715e9609ca29dbb23808))

* feat(matrix_preview): also update meta data on file update (#1082) *by pheowl* ([`9e254d5`](https://github.com/andythomas/matr1x/commit/9e254d5fc875d2b517d47b4e32cfc6f585ab7e24))

* feat(matrix_preview): also update meta data on file update *by pheowl* ([`9e254d5`](https://github.com/andythomas/matr1x/commit/9e254d5fc875d2b517d47b4e32cfc6f585ab7e24))

* feat(gui_util): Config editor and types (#1031) *by pheowl* ([`0bd67b5`](https://github.com/andythomas/matr1x/commit/0bd67b5e4b86eeb69e2b4a4f9fac4421f9b7637e))

* feat(config): implement first version of variable config editor, path edit missing *by pheowl* ([`0bd67b5`](https://github.com/andythomas/matr1x/commit/0bd67b5e4b86eeb69e2b4a4f9fac4421f9b7637e))

* feat(gui_util): add non-functional code for path edit with tool button to open menu *by pheowl* ([`0bd67b5`](https://github.com/andythomas/matr1x/commit/0bd67b5e4b86eeb69e2b4a4f9fac4421f9b7637e))

* feat(gui_util): include functional changes for distinguishing file/folder paths and float decimals *by pheowl* ([`0bd67b5`](https://github.com/andythomas/matr1x/commit/0bd67b5e4b86eeb69e2b4a4f9fac4421f9b7637e))

* feat(gui_util): support bool type, add documentation *by pheowl* ([`0bd67b5`](https://github.com/andythomas/matr1x/commit/0bd67b5e4b86eeb69e2b4a4f9fac4421f9b7637e))

* feat(matrix-script): configurable script output redirection (#1055) *by Dominik Kriegner* ([`1e74a5b`](https://github.com/andythomas/matr1x/commit/1e74a5b720c7c3aef2fc80bc216a109b1f03f875))

* feat(matrix-script): allow output redirection to a file *by Dominik Kriegner* ([`1e74a5b`](https://github.com/andythomas/matr1x/commit/1e74a5b720c7c3aef2fc80bc216a109b1f03f875))

* feat(matrix-script): allow redirecting of all print messages to a comment in the datafile *by Dominik Kriegner* ([`1e74a5b`](https://github.com/andythomas/matr1x/commit/1e74a5b720c7c3aef2fc80bc216a109b1f03f875))

* feat(matrix-script): add tooltips (#1042) *by Andy Thomas* ([`c9d5a58`](https://github.com/andythomas/matr1x/commit/c9d5a587189116348d2c9aa6da00605849f4b7ba))

* feat(matrix-script): add tooltips *by Andy Thomas* ([`c9d5a58`](https://github.com/andythomas/matr1x/commit/c9d5a587189116348d2c9aa6da00605849f4b7ba))

* feat(matrix-gui): Quality of life improvements (#1044) *by Andy Thomas* ([`9a2db0e`](https://github.com/andythomas/matr1x/commit/9a2db0e9725dcda3a662a9c84747455ba3a91c1b))

* feat(matrix-gui): scroll to added q item *by Andy Thomas* ([`9a2db0e`](https://github.com/andythomas/matr1x/commit/9a2db0e9725dcda3a662a9c84747455ba3a91c1b))

* feat: allow client side decorations for main scripts (#1037) *by Andy Thomas* ([`e9b3981`](https://github.com/andythomas/matr1x/commit/e9b398109beab51e2c5e35077e6484aabd81f6d9))

* feat: allow client decorations for windows *by Andy Thomas* ([`e9b3981`](https://github.com/andythomas/matr1x/commit/e9b398109beab51e2c5e35077e6484aabd81f6d9))

* feat(matrix-preview): allow data export as text (#1023) *by Andy Thomas* ([`46d83a3`](https://github.com/andythomas/matr1x/commit/46d83a3036c9fcd3a67d63ad1f80fb12a783fcbf))

* feat: allow multiple system selection (#1021) *by Andy Thomas* ([`cd12724`](https://github.com/andythomas/matr1x/commit/cd127243f9a67c11874510a0faa07097997e2c5b))

* feat: allow multiple system selection *by Andy Thomas* ([`cd12724`](https://github.com/andythomas/matr1x/commit/cd127243f9a67c11874510a0faa07097997e2c5b))

* feat: add relation metadata field (#1027) *by Andy Thomas* ([`ace7baf`](https://github.com/andythomas/matr1x/commit/ace7baf08cf4bca924e91c837adacd6b96ac933b))

* feat: add relation metadata field *by Andy Thomas* ([`ace7baf`](https://github.com/andythomas/matr1x/commit/ace7baf08cf4bca924e91c837adacd6b96ac933b))

* feat(matrix-script/system_elab): add documentation to script, implement linking of relation *by Andy Thomas* ([`ace7baf`](https://github.com/andythomas/matr1x/commit/ace7baf08cf4bca924e91c837adacd6b96ac933b))

* feat: add keyboard shortcuts to main scripts (#1009) *by Andy Thomas* ([`b18c1b4`](https://github.com/andythomas/matr1x/commit/b18c1b4a3fa7b612bf8caab784278b6dc64093dd))

* feat: add keyboard shortcuts to main scripts *by Andy Thomas* ([`b18c1b4`](https://github.com/andythomas/matr1x/commit/b18c1b4a3fa7b612bf8caab784278b6dc64093dd))

* feat(matrix-script): improved wait command with more options (#987) *by Dominik Kriegner* ([`f5c0fc8`](https://github.com/andythomas/matr1x/commit/f5c0fc8458b76b4ef2ea4896e5f26eb724f3faca))

* feat(matrix-script): improved wait command with more options *by Dominik Kriegner* ([`f5c0fc8`](https://github.com/andythomas/matr1x/commit/f5c0fc8458b76b4ef2ea4896e5f26eb724f3faca))

* feat(emma): Emma update (#1006) *by pheowl* ([`f3d445f`](https://github.com/andythomas/matr1x/commit/f3d445f16ce1f85e54a0d8fea64281768aefe516))

* feat(EMMA): updates from emma PC *by pheowl* ([`f3d445f`](https://github.com/andythomas/matr1x/commit/f3d445f16ce1f85e54a0d8fea64281768aefe516))

* feat(chaos/control_chaos): update changes from chaos, note oxford_mercury (#1003) *by pheowl* ([`f3d445f`](https://github.com/andythomas/matr1x/commit/f3d445f16ce1f85e54a0d8fea64281768aefe516))

* feat(chaos/control_chaos): update changes from chaos, note oxford_mercury *by pheowl* ([`f3d445f`](https://github.com/andythomas/matr1x/commit/f3d445f16ce1f85e54a0d8fea64281768aefe516))

* feat(gui_util): add custom icon "play" *by Andy Thomas* ([`f90c17b`](https://github.com/andythomas/matr1x/commit/f90c17ba6075da3c7cea44fa6529513c0f9337f4))

* feat(chaos/control_chaos): update changes from chaos, note oxford_mercury (#1003) *by pheowl* ([`1dea8d4`](https://github.com/andythomas/matr1x/commit/1dea8d4c9fab5b0e7e52570e5d902a24da8be941))

* feat(chaos/control_chaos): update changes from chaos, note oxford_mercury *by pheowl* ([`1dea8d4`](https://github.com/andythomas/matr1x/commit/1dea8d4c9fab5b0e7e52570e5d902a24da8be941))

* feat: add quit menu to all main scripts (#990) *by Andy Thomas* ([`6fdd80b`](https://github.com/andythomas/matr1x/commit/6fdd80bb08eb92a874d0583813d706cab8d9c08b))

### Unknown

* ruff action fixes (#1244) *by github-actions[bot]* ([`52595a4`](https://github.com/andythomas/matr1x/commit/52595a4dab4d2767c29a22ea30d9a28be06a5774))

* properly delete QWidgets (#1247) *by Andy Thomas* ([`f69196b`](https://github.com/andythomas/matr1x/commit/f69196bb8aaa57a1b66f247ad4e407c740c41045))

* feature(matrix-script): introduce "code" menu (#1186) *by Andy Thomas* ([`208bfe9`](https://github.com/andythomas/matr1x/commit/208bfe9a253abdaddc4650402a2d28e8769b9923))

* ruff action fixes (#974) *by github-actions[bot]* ([`070be64`](https://github.com/andythomas/matr1x/commit/070be6437febb36e24858f68b9785d5eee33bdee))

## v7.5.0 (2024-10-28)

### Bug fixes

* fix(system.py): closes issue #920, force reloading of modules on reimport (#941) *by pheowl* ([`46c655e`](https://github.com/andythomas/matr1x/commit/46c655e27f82cdf1c50fb1e1466bf63c9b3e12fc))

* fix(system.py): closes issue #920, force reloading of modules on reimport *by pheowl* ([`46c655e`](https://github.com/andythomas/matr1x/commit/46c655e27f82cdf1c50fb1e1466bf63c9b3e12fc))

* fix(system): fix naming error related to shadowing of import *by pheowl* ([`46c655e`](https://github.com/andythomas/matr1x/commit/46c655e27f82cdf1c50fb1e1466bf63c9b3e12fc))

* fix(many): fix linter comments *by Dominik Kriegner* ([`40fb195`](https://github.com/andythomas/matr1x/commit/40fb195d5e93f534ef38cbd91bf9f5e518e48b15))

* fix(spectrum_analyzer): remove spectrum analyzer file, already included in keysight library *by Dominik Kriegner* ([`40fb195`](https://github.com/andythomas/matr1x/commit/40fb195d5e93f534ef38cbd91bf9f5e518e48b15))

* fix(PR-check): use correct reference for darker (#716) *by Dominik Kriegner* ([`40fb195`](https://github.com/andythomas/matr1x/commit/40fb195d5e93f534ef38cbd91bf9f5e518e48b15))

* fix(PR-check): avoid formatting changes in main *by Dominik Kriegner* ([`40fb195`](https://github.com/andythomas/matr1x/commit/40fb195d5e93f534ef38cbd91bf9f5e518e48b15))

* fix(PR-check): correctly reference main *by Dominik Kriegner* ([`40fb195`](https://github.com/andythomas/matr1x/commit/40fb195d5e93f534ef38cbd91bf9f5e518e48b15))

* fix(PR-check): correct reference *by Dominik Kriegner* ([`40fb195`](https://github.com/andythomas/matr1x/commit/40fb195d5e93f534ef38cbd91bf9f5e518e48b15))

* fix(danfysik): address comments by @dkriegner *by Dominik Kriegner* ([`40fb195`](https://github.com/andythomas/matr1x/commit/40fb195d5e93f534ef38cbd91bf9f5e518e48b15))

* fix(pico.py): fix typos, wrong code and linter-induced errors *by Dominik Kriegner* ([`40fb195`](https://github.com/andythomas/matr1x/commit/40fb195d5e93f534ef38cbd91bf9f5e518e48b15))

* fix(pico): some more linter fixes *by Dominik Kriegner* ([`40fb195`](https://github.com/andythomas/matr1x/commit/40fb195d5e93f534ef38cbd91bf9f5e518e48b15))

* fix(system_elise/vna): merge current changes to ELISE system *by Dominik Kriegner* ([`40fb195`](https://github.com/andythomas/matr1x/commit/40fb195d5e93f534ef38cbd91bf9f5e518e48b15))

* fix(elise-systems): fix minor issues *by Dominik Kriegner* ([`40fb195`](https://github.com/andythomas/matr1x/commit/40fb195d5e93f534ef38cbd91bf9f5e518e48b15))

* fix(keysight.py): fix wrong reference to connection *by Dominik Kriegner* ([`40fb195`](https://github.com/andythomas/matr1x/commit/40fb195d5e93f534ef38cbd91bf9f5e518e48b15))

* fix(agilent.py): remove wrong file *by Dominik Kriegner* ([`40fb195`](https://github.com/andythomas/matr1x/commit/40fb195d5e93f534ef38cbd91bf9f5e518e48b15))

* fix(__init__.py): potentially fix linter issues *by Dominik Kriegner* ([`40fb195`](https://github.com/andythomas/matr1x/commit/40fb195d5e93f534ef38cbd91bf9f5e518e48b15))

* fix(__init__.py): move noqa statemtnt *by Dominik Kriegner* ([`40fb195`](https://github.com/andythomas/matr1x/commit/40fb195d5e93f534ef38cbd91bf9f5e518e48b15))

* fix(__init__.py): move noqa statement back to original position *by Dominik Kriegner* ([`40fb195`](https://github.com/andythomas/matr1x/commit/40fb195d5e93f534ef38cbd91bf9f5e518e48b15))

* fix(__init__.py): implement change by darker *by Dominik Kriegner* ([`40fb195`](https://github.com/andythomas/matr1x/commit/40fb195d5e93f534ef38cbd91bf9f5e518e48b15))

* fix(system_halbach,-nanotec): fix minor issues, adapt more recent code style for system_halbach *by Dominik Kriegner* ([`40fb195`](https://github.com/andythomas/matr1x/commit/40fb195d5e93f534ef38cbd91bf9f5e518e48b15))

* fix(caenels): reduce code, replace write/read combo with query *by Dominik Kriegner* ([`40fb195`](https://github.com/andythomas/matr1x/commit/40fb195d5e93f534ef38cbd91bf9f5e518e48b15))

* fix(caenels): add missing header *by Dominik Kriegner* ([`40fb195`](https://github.com/andythomas/matr1x/commit/40fb195d5e93f534ef38cbd91bf9f5e518e48b15))

* fix(control_chaos): Update chaos control to most recent version and start testing, minor fix to MPT200 driver *by Dominik Kriegner* ([`40fb195`](https://github.com/andythomas/matr1x/commit/40fb195d5e93f534ef38cbd91bf9f5e518e48b15))

* fix(oxford_mercury): introduce timeout into mercury after timeout error in control_chaos, watch! *by Dominik Kriegner* ([`40fb195`](https://github.com/andythomas/matr1x/commit/40fb195d5e93f534ef38cbd91bf9f5e518e48b15))

* fix(diverse-files): remove leftover changes from debugging *by Dominik Kriegner* ([`40fb195`](https://github.com/andythomas/matr1x/commit/40fb195d5e93f534ef38cbd91bf9f5e518e48b15))

* fix(control_chaos): fix wrong reference to instance variable *by Dominik Kriegner* ([`40fb195`](https://github.com/andythomas/matr1x/commit/40fb195d5e93f534ef38cbd91bf9f5e518e48b15))

* fix(system_makrocamera_fixeddureation): remove last excess system *by Dominik Kriegner* ([`40fb195`](https://github.com/andythomas/matr1x/commit/40fb195d5e93f534ef38cbd91bf9f5e518e48b15))

* fix(control_farmic): remove excess imports *by Dominik Kriegner* ([`40fb195`](https://github.com/andythomas/matr1x/commit/40fb195d5e93f534ef38cbd91bf9f5e518e48b15))

* fix(release.yml): upload wheels (#793) *by Dominik Kriegner* ([`40fb195`](https://github.com/andythomas/matr1x/commit/40fb195d5e93f534ef38cbd91bf9f5e518e48b15))

* fix(release.yml): upload wheels *by Dominik Kriegner* ([`40fb195`](https://github.com/andythomas/matr1x/commit/40fb195d5e93f534ef38cbd91bf9f5e518e48b15))

* fix(release.yml): add tag to github release upload *by Dominik Kriegner* ([`40fb195`](https://github.com/andythomas/matr1x/commit/40fb195d5e93f534ef38cbd91bf9f5e518e48b15))

* fix(aja): make control-gui more error resistant *by Dominik Kriegner* ([`40fb195`](https://github.com/andythomas/matr1x/commit/40fb195d5e93f534ef38cbd91bf9f5e518e48b15))

* fix(update_icons): do not use refs (#821) *by Dominik Kriegner* ([`40fb195`](https://github.com/andythomas/matr1x/commit/40fb195d5e93f534ef38cbd91bf9f5e518e48b15))

* fix(sweep-generator.svg): paper sheet is now white (#852) *by Dominik Kriegner* ([`40fb195`](https://github.com/andythomas/matr1x/commit/40fb195d5e93f534ef38cbd91bf9f5e518e48b15))

* fix(sweep-generator.svg): paper sheet is now white *by Dominik Kriegner* ([`40fb195`](https://github.com/andythomas/matr1x/commit/40fb195d5e93f534ef38cbd91bf9f5e518e48b15))

* fix(control-dummy): return correct value (#868) *by Dominik Kriegner* ([`40fb195`](https://github.com/andythomas/matr1x/commit/40fb195d5e93f534ef38cbd91bf9f5e518e48b15))

* fix(controlAJA): add RF switchbox capabilities, more error resistance (#901) *by Dominik Kriegner* ([`40fb195`](https://github.com/andythomas/matr1x/commit/40fb195d5e93f534ef38cbd91bf9f5e518e48b15))

* fix(AJA): more customization capabilities in wait_temperature *by Dominik Kriegner* ([`40fb195`](https://github.com/andythomas/matr1x/commit/40fb195d5e93f534ef38cbd91bf9f5e518e48b15))

* fix(controlAJA): add more graceful error handling *by Dominik Kriegner* ([`40fb195`](https://github.com/andythomas/matr1x/commit/40fb195d5e93f534ef38cbd91bf9f5e518e48b15))

* fix(system.py): closes issue #920, force reloading of modules on reimport (#941) *by Dominik Kriegner* ([`40fb195`](https://github.com/andythomas/matr1x/commit/40fb195d5e93f534ef38cbd91bf9f5e518e48b15))

* fix(system.py): closes issue #920, force reloading of modules on reimport *by Dominik Kriegner* ([`40fb195`](https://github.com/andythomas/matr1x/commit/40fb195d5e93f534ef38cbd91bf9f5e518e48b15))

* fix(system): fix naming error related to shadowing of import *by Dominik Kriegner* ([`40fb195`](https://github.com/andythomas/matr1x/commit/40fb195d5e93f534ef38cbd91bf9f5e518e48b15))

* fix(matrix-preview): allow displaying of categorical data (#964) *by Dominik Kriegner* ([`e569538`](https://github.com/andythomas/matr1x/commit/e56953826d8f4083b3d13d3d8bf682d7a1780f57))

* fix(matrix-preview): allow displaying of categorical data *by Dominik Kriegner* ([`e569538`](https://github.com/andythomas/matr1x/commit/e56953826d8f4083b3d13d3d8bf682d7a1780f57))

* fix(system): avoid shadowing builtin 'sys' package (#959) *by Dominik Kriegner* ([`2eba23c`](https://github.com/andythomas/matr1x/commit/2eba23cf74209b6cad6714cce5ea8169023ee21f))

* fix(system): avoid shadowing builtin 'sys' package *by Dominik Kriegner* ([`2eba23c`](https://github.com/andythomas/matr1x/commit/2eba23cf74209b6cad6714cce5ea8169023ee21f))

* fix(diverse-files): find further mentions of `sys` *by Dominik Kriegner* ([`2eba23c`](https://github.com/andythomas/matr1x/commit/2eba23cf74209b6cad6714cce5ea8169023ee21f))

* fix(shadowing): rename variables as needed to not use builtins (#961) *by Dominik Kriegner* ([`58ec680`](https://github.com/andythomas/matr1x/commit/58ec680f58c1373eec96b2a698aa7f25329eeee8))

* fix(shadowing): rename variables as needed to not use builtin expressions *by Dominik Kriegner* ([`58ec680`](https://github.com/andythomas/matr1x/commit/58ec680f58c1373eec96b2a698aa7f25329eeee8))

* fix(matrix-script, matrix-gui): proper start size (#939) *by Andy Thomas* ([`03994d4`](https://github.com/andythomas/matr1x/commit/03994d413d3b6f5ea8449384136bc4fa0adc664a))

* fix(matrix-script, matrix-gui): proper start size *by Andy Thomas* ([`03994d4`](https://github.com/andythomas/matr1x/commit/03994d413d3b6f5ea8449384136bc4fa0adc664a))

* fix(system.py): forces reload of system on import, makes sure to reflect changes of files (#921) *by pheowl* ([`e1971b7`](https://github.com/andythomas/matr1x/commit/e1971b78e5a263f0958abcfcf8432a7aeeb7f5d7))

* fix(system.py): forces reload of system on import, makes sure to reflect changes of files *by pheowl* ([`e1971b7`](https://github.com/andythomas/matr1x/commit/e1971b78e5a263f0958abcfcf8432a7aeeb7f5d7))

* fix(system.py): properly reload systems from file when reimported, always updates modules to current file version *by pheowl* ([`e1971b7`](https://github.com/andythomas/matr1x/commit/e1971b78e5a263f0958abcfcf8432a7aeeb7f5d7))

* fix(system.py): rename sys package to _sys *by pheowl* ([`e1971b7`](https://github.com/andythomas/matr1x/commit/e1971b78e5a263f0958abcfcf8432a7aeeb7f5d7))

* fix(system): implement change suggested by @dkriegner *by pheowl* ([`e1971b7`](https://github.com/andythomas/matr1x/commit/e1971b78e5a263f0958abcfcf8432a7aeeb7f5d7))

* fix(system): fix missing sys and ensure tests work *by pheowl* ([`e1971b7`](https://github.com/andythomas/matr1x/commit/e1971b78e5a263f0958abcfcf8432a7aeeb7f5d7))

* fix(gui_util): make ruff happy *by pheowl* ([`f3abe18`](https://github.com/andythomas/matr1x/commit/f3abe18b5abfedb0d9063812bf558f9f5fbad2a5))

* fix(eval): fix potential unbound variable warning, improve code quality *by Dominik Kriegner* ([`5ee1794`](https://github.com/andythomas/matr1x/commit/5ee1794291f3310f1f84b1fef94f84322869f4a3))

* fix(System): ensure deterministic order in dcdata (#922) *by Dominik Kriegner* ([`7825a2e`](https://github.com/andythomas/matr1x/commit/7825a2e0255fed5a233a9f00d61c2c9da3c1dfa8))

* fix(PyQt5): remove PyQt5 from full code base (#906) *by Dominik Kriegner* ([`993ea3d`](https://github.com/andythomas/matr1x/commit/993ea3db1cf4d880278301b60870927a65257244))

* fix(PyQt5): remove PyQt5 from full code base *by Dominik Kriegner* ([`993ea3d`](https://github.com/andythomas/matr1x/commit/993ea3db1cf4d880278301b60870927a65257244))

* fix: correctly set app names on a mac (#887) *by Andy Thomas* ([`807c0cd`](https://github.com/andythomas/matr1x/commit/807c0cd8fee3a81ec304b0fa35de75584968b34d))

* fix: correctly set app names on a mac *by Andy Thomas* ([`807c0cd`](https://github.com/andythomas/matr1x/commit/807c0cd8fee3a81ec304b0fa35de75584968b34d))

* fix(ruff): do not auto-test docstrings *by Andy Thomas* ([`ab07d61`](https://github.com/andythomas/matr1x/commit/ab07d613cc1000a22d0bd7fe7e17c0dc12a1d3f5))

* fix(ci-dev): allow chore as semantic commit message *by Andy Thomas* ([`ab07d61`](https://github.com/andythomas/matr1x/commit/ab07d613cc1000a22d0bd7fe7e17c0dc12a1d3f5))

* fix(ci): allow chore as semantic commit message *by Andy Thomas* ([`ab07d61`](https://github.com/andythomas/matr1x/commit/ab07d613cc1000a22d0bd7fe7e17c0dc12a1d3f5))

* fix(install.py): make uninstall work on a Mac *by Dominik Kriegner* ([`a91f271`](https://github.com/andythomas/matr1x/commit/a91f271d5e51b9995a410498bbd17d724d3358d6))

* fix(__init__): make config parser immune to other value types *by pheowl* ([`ad3cc83`](https://github.com/andythomas/matr1x/commit/ad3cc83c17ed9e14c62dcb04f8bde55ccec354d4))

* fix(gui_util): rewrite full custom config without overwriting unspecified options *by pheowl* ([`ad3cc83`](https://github.com/andythomas/matr1x/commit/ad3cc83c17ed9e14c62dcb04f8bde55ccec354d4))

* fix(matrix-script): add preferences docstring *by pheowl* ([`ad3cc83`](https://github.com/andythomas/matr1x/commit/ad3cc83c17ed9e14c62dcb04f8bde55ccec354d4))

* fix(matrix-script): fix linter issues *by pheowl* ([`ad3cc83`](https://github.com/andythomas/matr1x/commit/ad3cc83c17ed9e14c62dcb04f8bde55ccec354d4))

* fix(main->development): merge main into development to provide most recent matr1x.devices (#877) *by pheowl* ([`4441837`](https://github.com/andythomas/matr1x/commit/444183762010012233b046c0dea0e35ae7566e7e))

* fix(many): fix linter comments *by pheowl* ([`4441837`](https://github.com/andythomas/matr1x/commit/444183762010012233b046c0dea0e35ae7566e7e))

* fix(spectrum_analyzer): remove spectrum analyzer file, already included in keysight library *by pheowl* ([`4441837`](https://github.com/andythomas/matr1x/commit/444183762010012233b046c0dea0e35ae7566e7e))

* fix(PR-check): use correct reference for darker (#716) *by pheowl* ([`4441837`](https://github.com/andythomas/matr1x/commit/444183762010012233b046c0dea0e35ae7566e7e))

* fix(PR-check): avoid formatting changes in main *by pheowl* ([`4441837`](https://github.com/andythomas/matr1x/commit/444183762010012233b046c0dea0e35ae7566e7e))

* fix(PR-check): correctly reference main *by pheowl* ([`4441837`](https://github.com/andythomas/matr1x/commit/444183762010012233b046c0dea0e35ae7566e7e))

* fix(PR-check): correct reference *by pheowl* ([`4441837`](https://github.com/andythomas/matr1x/commit/444183762010012233b046c0dea0e35ae7566e7e))

* fix(danfysik): address comments by @dkriegner *by pheowl* ([`4441837`](https://github.com/andythomas/matr1x/commit/444183762010012233b046c0dea0e35ae7566e7e))

* fix(pico.py): fix typos, wrong code and linter-induced errors *by pheowl* ([`4441837`](https://github.com/andythomas/matr1x/commit/444183762010012233b046c0dea0e35ae7566e7e))

* fix(pico): some more linter fixes *by pheowl* ([`4441837`](https://github.com/andythomas/matr1x/commit/444183762010012233b046c0dea0e35ae7566e7e))

* fix(system_elise/vna): merge current changes to ELISE system *by pheowl* ([`4441837`](https://github.com/andythomas/matr1x/commit/444183762010012233b046c0dea0e35ae7566e7e))

* fix(elise-systems): fix minor issues *by pheowl* ([`4441837`](https://github.com/andythomas/matr1x/commit/444183762010012233b046c0dea0e35ae7566e7e))

* fix(keysight.py): fix wrong reference to connection *by pheowl* ([`4441837`](https://github.com/andythomas/matr1x/commit/444183762010012233b046c0dea0e35ae7566e7e))

* fix(agilent.py): remove wrong file *by pheowl* ([`4441837`](https://github.com/andythomas/matr1x/commit/444183762010012233b046c0dea0e35ae7566e7e))

* fix(__init__.py): potentially fix linter issues *by pheowl* ([`4441837`](https://github.com/andythomas/matr1x/commit/444183762010012233b046c0dea0e35ae7566e7e))

* fix(__init__.py): move noqa statemtnt *by pheowl* ([`4441837`](https://github.com/andythomas/matr1x/commit/444183762010012233b046c0dea0e35ae7566e7e))

* fix(__init__.py): move noqa statement back to original position *by pheowl* ([`4441837`](https://github.com/andythomas/matr1x/commit/444183762010012233b046c0dea0e35ae7566e7e))

* fix(__init__.py): implement change by darker *by pheowl* ([`4441837`](https://github.com/andythomas/matr1x/commit/444183762010012233b046c0dea0e35ae7566e7e))

* fix(system_halbach,-nanotec): fix minor issues, adapt more recent code style for system_halbach *by pheowl* ([`4441837`](https://github.com/andythomas/matr1x/commit/444183762010012233b046c0dea0e35ae7566e7e))

* fix(caenels): reduce code, replace write/read combo with query *by pheowl* ([`4441837`](https://github.com/andythomas/matr1x/commit/444183762010012233b046c0dea0e35ae7566e7e))

* fix(caenels): add missing header *by pheowl* ([`4441837`](https://github.com/andythomas/matr1x/commit/444183762010012233b046c0dea0e35ae7566e7e))

* fix(control_chaos): Update chaos control to most recent version and start testing, minor fix to MPT200 driver *by pheowl* ([`4441837`](https://github.com/andythomas/matr1x/commit/444183762010012233b046c0dea0e35ae7566e7e))

* fix(oxford_mercury): introduce timeout into mercury after timeout error in control_chaos, watch! *by pheowl* ([`4441837`](https://github.com/andythomas/matr1x/commit/444183762010012233b046c0dea0e35ae7566e7e))

* fix(diverse-files): remove leftover changes from debugging *by pheowl* ([`4441837`](https://github.com/andythomas/matr1x/commit/444183762010012233b046c0dea0e35ae7566e7e))

* fix(control_chaos): fix wrong reference to instance variable *by pheowl* ([`4441837`](https://github.com/andythomas/matr1x/commit/444183762010012233b046c0dea0e35ae7566e7e))

* fix(system_makrocamera_fixeddureation): remove last excess system *by pheowl* ([`4441837`](https://github.com/andythomas/matr1x/commit/444183762010012233b046c0dea0e35ae7566e7e))

* fix(control_farmic): remove excess imports *by pheowl* ([`4441837`](https://github.com/andythomas/matr1x/commit/444183762010012233b046c0dea0e35ae7566e7e))

* fix(release.yml): upload wheels (#793) *by pheowl* ([`4441837`](https://github.com/andythomas/matr1x/commit/444183762010012233b046c0dea0e35ae7566e7e))

* fix(release.yml): upload wheels *by pheowl* ([`4441837`](https://github.com/andythomas/matr1x/commit/444183762010012233b046c0dea0e35ae7566e7e))

* fix(release.yml): add tag to github release upload *by pheowl* ([`4441837`](https://github.com/andythomas/matr1x/commit/444183762010012233b046c0dea0e35ae7566e7e))

* fix(aja): make control-gui more error resistant *by pheowl* ([`4441837`](https://github.com/andythomas/matr1x/commit/444183762010012233b046c0dea0e35ae7566e7e))

* fix(update_icons): do not use refs (#821) *by pheowl* ([`4441837`](https://github.com/andythomas/matr1x/commit/444183762010012233b046c0dea0e35ae7566e7e))

* fix(sweep-generator.svg): paper sheet is now white (#852) *by pheowl* ([`4441837`](https://github.com/andythomas/matr1x/commit/444183762010012233b046c0dea0e35ae7566e7e))

* fix(sweep-generator.svg): paper sheet is now white *by pheowl* ([`4441837`](https://github.com/andythomas/matr1x/commit/444183762010012233b046c0dea0e35ae7566e7e))

* fix(control-dummy): return correct value (#868) *by pheowl* ([`4441837`](https://github.com/andythomas/matr1x/commit/444183762010012233b046c0dea0e35ae7566e7e))

* fix(github-workflows): remove changes to github workflows introduced in main *by pheowl* ([`4441837`](https://github.com/andythomas/matr1x/commit/444183762010012233b046c0dea0e35ae7566e7e))

* fix(control_dummy): reject changes introduced by merge *by pheowl* ([`4441837`](https://github.com/andythomas/matr1x/commit/444183762010012233b046c0dea0e35ae7566e7e))

* fix(ifwlib-systems): make new systems use lowercase meta data *by pheowl* ([`4441837`](https://github.com/andythomas/matr1x/commit/444183762010012233b046c0dea0e35ae7566e7e))

* fix(build-system,-control_dummy): reapply mistakenly removed changes from main *by pheowl* ([`4441837`](https://github.com/andythomas/matr1x/commit/444183762010012233b046c0dea0e35ae7566e7e))

* fix(control_dummy): reapply GPL header *by pheowl* ([`4441837`](https://github.com/andythomas/matr1x/commit/444183762010012233b046c0dea0e35ae7566e7e))

* fix(system_noise_mfli): fix linter error *by pheowl* ([`4441837`](https://github.com/andythomas/matr1x/commit/444183762010012233b046c0dea0e35ae7566e7e))

* fix(pyproject.toml): remove deprecated dependency *by pheowl* ([`4441837`](https://github.com/andythomas/matr1x/commit/444183762010012233b046c0dea0e35ae7566e7e))

* fix(util): move towards property implementation for finished variable *by Andy Thomas* ([`1939da6`](https://github.com/andythomas/matr1x/commit/1939da621c07bf8614edb32c3f80cde19bcf9aa7))

* fix(matrix): remove debug print *by Andy Thomas* ([`1939da6`](https://github.com/andythomas/matr1x/commit/1939da621c07bf8614edb32c3f80cde19bcf9aa7))

* fix(matrix_script,-util): make code work with changes from development, fix font issue *by Andy Thomas* ([`1939da6`](https://github.com/andythomas/matr1x/commit/1939da621c07bf8614edb32c3f80cde19bcf9aa7))

* fix(matrix_script): remove leftover import *by Andy Thomas* ([`1939da6`](https://github.com/andythomas/matr1x/commit/1939da621c07bf8614edb32c3f80cde19bcf9aa7))

* fix(gui_util): make meta data loading use the correct keys *by Andy Thomas* ([`0174fdd`](https://github.com/andythomas/matr1x/commit/0174fdd6ed4384cdf445151edb2aacd815e5419e))

* fix(matrix-script): fix merge leftover *by Andy Thomas* ([`0174fdd`](https://github.com/andythomas/matr1x/commit/0174fdd6ed4384cdf445151edb2aacd815e5419e))

* fix(sweep-generator.svg): paper sheet is now white (#852) *by Andy Thomas* ([`0174fdd`](https://github.com/andythomas/matr1x/commit/0174fdd6ed4384cdf445151edb2aacd815e5419e))

* fix(sweep-generator.svg): paper sheet is now white *by Andy Thomas* ([`0174fdd`](https://github.com/andythomas/matr1x/commit/0174fdd6ed4384cdf445151edb2aacd815e5419e))

* fix(main-scripts): remove unused imports *by Andy Thomas* ([`0174fdd`](https://github.com/andythomas/matr1x/commit/0174fdd6ed4384cdf445151edb2aacd815e5419e))

* fix(matrix-script): fix merge leftovers *by Andy Thomas* ([`0174fdd`](https://github.com/andythomas/matr1x/commit/0174fdd6ed4384cdf445151edb2aacd815e5419e))

* fix(gui_util): dc entries are lowercase *by Andy Thomas* ([`0174fdd`](https://github.com/andythomas/matr1x/commit/0174fdd6ed4384cdf445151edb2aacd815e5419e))

* fix(gui_util,-matrix_gui): make preview work again *by Andy Thomas* ([`0174fdd`](https://github.com/andythomas/matr1x/commit/0174fdd6ed4384cdf445151edb2aacd815e5419e))

* fix(gui-util): docstring, properly name variable *by Andy Thomas* ([`0174fdd`](https://github.com/andythomas/matr1x/commit/0174fdd6ed4384cdf445151edb2aacd815e5419e))

* fix(matr1x-ma8-file-format): attempt to fix the data file format, everything moved to lowercase (#855) *by pheowl* ([`7c75ea6`](https://github.com/andythomas/matr1x/commit/7c75ea64a96037a507347ed9cd8ac5eb2c0afe29))

* fix(matr1x-ma8-file-format): attempt to fix the data file format, everything moved to lowercase *by pheowl* ([`7c75ea6`](https://github.com/andythomas/matr1x/commit/7c75ea64a96037a507347ed9cd8ac5eb2c0afe29))

* fix(testing-and-eval): remove parsing for transient file state *by pheowl* ([`7c75ea6`](https://github.com/andythomas/matr1x/commit/7c75ea64a96037a507347ed9cd8ac5eb2c0afe29))

* fix(testing): fix tests to current version with status *by pheowl* ([`7c75ea6`](https://github.com/andythomas/matr1x/commit/7c75ea64a96037a507347ed9cd8ac5eb2c0afe29))

* fix(matrix-input-file-system): migrate input files to lowercase, add version string *by pheowl* ([`7c75ea6`](https://github.com/andythomas/matr1x/commit/7c75ea64a96037a507347ed9cd8ac5eb2c0afe29))

* fix: proper comments and status entry in datafile (#843) *by Dominik Kriegner* ([`c4aa3f5`](https://github.com/andythomas/matr1x/commit/c4aa3f583e34211cc3eae9d9795ce308675d6114))

* fix: proper comments and status entry in datafile *by Dominik Kriegner* ([`c4aa3f5`](https://github.com/andythomas/matr1x/commit/c4aa3f583e34211cc3eae9d9795ce308675d6114))

* fix(matrix-script): properly reset start check (#847) *by Andy Thomas* ([`a17ebdd`](https://github.com/andythomas/matr1x/commit/a17ebdd250ae6047fee8ced4d2418ef9d1a71a84))

* fix(gui_util): display length 1 list/tuples as strings directly *by Dominik Kriegner* ([`3b711ec`](https://github.com/andythomas/matr1x/commit/3b711ecc7a28cf1aa4d2ad4f4c9f96d4908d77f4))

* fix(gui_util): correct name of data file, fix issue with length 0 arrays *by Dominik Kriegner* ([`3b711ec`](https://github.com/andythomas/matr1x/commit/3b711ecc7a28cf1aa4d2ad4f4c9f96d4908d77f4))

* fix(system_dummy_feature): fix case of meta data key *by Dominik Kriegner* ([`3b711ec`](https://github.com/andythomas/matr1x/commit/3b711ecc7a28cf1aa4d2ad4f4c9f96d4908d77f4))

* fix(gui_util): remove some spare lines from coding *by Dominik Kriegner* ([`3b711ec`](https://github.com/andythomas/matr1x/commit/3b711ecc7a28cf1aa4d2ad4f4c9f96d4908d77f4))

* fix(gui_util): make meta data loading use the correct keys *by pheowl* ([`36a2a3b`](https://github.com/andythomas/matr1x/commit/36a2a3b5be22e7298d22a21bc21e2d3bc9c60582))

* fix(utit,-tests): address review comments *by pheowl* ([`47b848e`](https://github.com/andythomas/matr1x/commit/47b848e82ff220ab05c6dd6426dadcd946dfdc15))

* fix(pyproject.toml-(ifwlib)): add missing dependency to ifwlib *by nadnab* ([`0c1b5be`](https://github.com/andythomas/matr1x/commit/0c1b5bee4b978ab1d2eaa5f1befecb8cd8ffc836))

* fix(pyproject.toml): make dependency for elab optional *by nadnab* ([`0c1b5be`](https://github.com/andythomas/matr1x/commit/0c1b5bee4b978ab1d2eaa5f1befecb8cd8ffc836))

* fix: remove control_dummy warning *by nadnab* ([`0c1b5be`](https://github.com/andythomas/matr1x/commit/0c1b5bee4b978ab1d2eaa5f1befecb8cd8ffc836))

* fix(tests): fix matrix-script linting test code (#752) *by nadnab* ([`0c1b5be`](https://github.com/andythomas/matr1x/commit/0c1b5bee4b978ab1d2eaa5f1befecb8cd8ffc836))

* fix(matrix,-matrix_script,-util): match behavior between matrix-script and matrix-gui *by nadnab* ([`0c1b5be`](https://github.com/andythomas/matr1x/commit/0c1b5bee4b978ab1d2eaa5f1befecb8cd8ffc836))

* fix(matrix_gui): improved handling of absence of file on input modification *by nadnab* ([`0c1b5be`](https://github.com/andythomas/matr1x/commit/0c1b5bee4b978ab1d2eaa5f1befecb8cd8ffc836))

* fix(matrix): remove some of the shouting *by nadnab* ([`0c1b5be`](https://github.com/andythomas/matr1x/commit/0c1b5bee4b978ab1d2eaa5f1befecb8cd8ffc836))

* fix(diverse-files): testing, refactoring, introducing editable flag, bugfixes *by nadnab* ([`0c1b5be`](https://github.com/andythomas/matr1x/commit/0c1b5bee4b978ab1d2eaa5f1befecb8cd8ffc836))

* fix(test_matrix): fix matrix tests to reflect changes to meta_data *by nadnab* ([`0c1b5be`](https://github.com/andythomas/matr1x/commit/0c1b5bee4b978ab1d2eaa5f1befecb8cd8ffc836))

* fix(eval.py): fix issue with loadmatrix trying to access nonexistent key "comments" in (old) hdf5 files (#761) *by nadnab* ([`0c1b5be`](https://github.com/andythomas/matr1x/commit/0c1b5bee4b978ab1d2eaa5f1befecb8cd8ffc836))

* fix(eval): use l/rstrip instead of removeprefix/suffix (#763) *by nadnab* ([`0c1b5be`](https://github.com/andythomas/matr1x/commit/0c1b5bee4b978ab1d2eaa5f1befecb8cd8ffc836))

* fix(scpi): multiline messages (#825) *by Dominik Kriegner* ([`ab89c47`](https://github.com/andythomas/matr1x/commit/ab89c4720b6a0805e227310e517a79886015abfc))

* fix(scpi): multiline messages *by Dominik Kriegner* ([`ab89c47`](https://github.com/andythomas/matr1x/commit/ab89c4720b6a0805e227310e517a79886015abfc))

* fix(matrix-script): allow floating metadata *by Andy Thomas* ([`3d2b367`](https://github.com/andythomas/matr1x/commit/3d2b367d703a1502fb2ce4d704726ba84ffb0e59))

* fix(matrix-script): allow stacked toolbars *by Andy Thomas* ([`3d2b367`](https://github.com/andythomas/matr1x/commit/3d2b367d703a1502fb2ce4d704726ba84ffb0e59))

* fix(matrix-script): allow stacked bottom and top *by Andy Thomas* ([`3d2b367`](https://github.com/andythomas/matr1x/commit/3d2b367d703a1502fb2ce4d704726ba84ffb0e59))

* fix(matrix-script): delete unused QPoint import *by Andy Thomas* ([`3d2b367`](https://github.com/andythomas/matr1x/commit/3d2b367d703a1502fb2ce4d704726ba84ffb0e59))

* fix(matrix-script): restore metadata size *by Andy Thomas* ([`3d2b367`](https://github.com/andythomas/matr1x/commit/3d2b367d703a1502fb2ce4d704726ba84ffb0e59))

* fix(matrix/script/util): address review comments, transition to finished/aborted and mark finished by default *by pheowl* ([`215e48a`](https://github.com/andythomas/matr1x/commit/215e48a97d5d308650f6ccd72bec89aaf85bee8f))

* fix(util.py): fix spurious added line *by pheowl* ([`215e48a`](https://github.com/andythomas/matr1x/commit/215e48a97d5d308650f6ccd72bec89aaf85bee8f))

* fix(matrix_preview): fix issue with repeated generation of w_meta_view (#806) *by pheowl* ([`11b7b4c`](https://github.com/andythomas/matr1x/commit/11b7b4c7df2c7f4c75bf72b3d263a525e575874e))

* fix(matrix_preview): fix issue with repeated generation of w_meta_view *by pheowl* ([`11b7b4c`](https://github.com/andythomas/matr1x/commit/11b7b4c7df2c7f4c75bf72b3d263a525e575874e))

* fix(matrix_preview): show file dir in window title *by pheowl* ([`11b7b4c`](https://github.com/andythomas/matr1x/commit/11b7b4c7df2c7f4c75bf72b3d263a525e575874e))

* fix(matrix-script): warn unsaved changes on open (#812) *by Andy Thomas* ([`76a15ed`](https://github.com/andythomas/matr1x/commit/76a15ed26866e9049caffe2d0d3728fb684eece1))

* fix(matrix-script): warn unsaved changes on open *by Andy Thomas* ([`76a15ed`](https://github.com/andythomas/matr1x/commit/76a15ed26866e9049caffe2d0d3728fb684eece1))

* fix(matrix-script): add back description to meta data (#801) *by Dominik Kriegner* ([`60abe13`](https://github.com/andythomas/matr1x/commit/60abe13caf816063c9af88b9c8bf08464e1a295f))

* fix(matrix-script): add back description to meta data *by Dominik Kriegner* ([`60abe13`](https://github.com/andythomas/matr1x/commit/60abe13caf816063c9af88b9c8bf08464e1a295f))

* fix(matrix-script): get metadata from widget *by Dominik Kriegner* ([`60abe13`](https://github.com/andythomas/matr1x/commit/60abe13caf816063c9af88b9c8bf08464e1a295f))

* fix(matrix-script): fix save behavior (#804) *by Andy Thomas* ([`6f26728`](https://github.com/andythomas/matr1x/commit/6f267289d6bc0601c96eca0375e716f4a920d630))

* fix(matrix-script): running script prevents close (#787) *by Andy Thomas* ([`0237c88`](https://github.com/andythomas/matr1x/commit/0237c885ed0794bf20b246eb0f7730ff61317df3))

* fix(matrix-script): running script prevents close *by Andy Thomas* ([`0237c88`](https://github.com/andythomas/matr1x/commit/0237c885ed0794bf20b246eb0f7730ff61317df3))

* fix(matrix-script): add quit in menu for win/linux *by Andy Thomas* ([`0237c88`](https://github.com/andythomas/matr1x/commit/0237c885ed0794bf20b246eb0f7730ff61317df3))

* fix(matrix-script): warn about running first *by Andy Thomas* ([`0237c88`](https://github.com/andythomas/matr1x/commit/0237c885ed0794bf20b246eb0f7730ff61317df3))

* fix(matrix-script): use proper win shortcut *by Andy Thomas* ([`0237c88`](https://github.com/andythomas/matr1x/commit/0237c885ed0794bf20b246eb0f7730ff61317df3))

* fix(gui_util): remove unused QDialogButtonBox *by Andy Thomas* ([`4eefb5b`](https://github.com/andythomas/matr1x/commit/4eefb5b6e0b65ef71961f2a6ad71cf1c0a20f2e7))

* fix(matrix-script): fix date in about box *by Andy Thomas* ([`82accdd`](https://github.com/andythomas/matr1x/commit/82accdd1933a37c401d2ec419258ca8fd6834aae))

* fix(eval): make loadmatrix rely on removeprefix for newer python version (#768) *by pheowl* ([`f6ca6f0`](https://github.com/andythomas/matr1x/commit/f6ca6f05c98add0ee958ecd8b5d303c98f91d83b))

* fix(eval): make loadmatrix rely on removeprefix for newer python version *by pheowl* ([`f6ca6f0`](https://github.com/andythomas/matr1x/commit/f6ca6f05c98add0ee958ecd8b5d303c98f91d83b))

* fix(eval): add missing _info *by pheowl* ([`f6ca6f0`](https://github.com/andythomas/matr1x/commit/f6ca6f05c98add0ee958ecd8b5d303c98f91d83b))

* fix(matrix-script): add metadata to toolbar *by Andy Thomas* ([`236255c`](https://github.com/andythomas/matr1x/commit/236255c8d03aa5c4361f1d964f7e3d7dbe58445b))

* fix(matrix-script): always append output on end of the output field *by Andy Thomas* ([`236255c`](https://github.com/andythomas/matr1x/commit/236255c8d03aa5c4361f1d964f7e3d7dbe58445b))

* fix(matrix-script): remove old metadata fields *by Andy Thomas* ([`236255c`](https://github.com/andythomas/matr1x/commit/236255c8d03aa5c4361f1d964f7e3d7dbe58445b))

* fix(matrix-script): fix toolbar right-click *by Andy Thomas* ([`236255c`](https://github.com/andythomas/matr1x/commit/236255c8d03aa5c4361f1d964f7e3d7dbe58445b))

* fix(matrix-script): fix empty script linter error *by Andy Thomas* ([`236255c`](https://github.com/andythomas/matr1x/commit/236255c8d03aa5c4361f1d964f7e3d7dbe58445b))

* fix(matrix-script): delete unused items *by Andy Thomas* ([`236255c`](https://github.com/andythomas/matr1x/commit/236255c8d03aa5c4361f1d964f7e3d7dbe58445b))

* fix(matrix-script): fix merge remains *by Andy Thomas* ([`236255c`](https://github.com/andythomas/matr1x/commit/236255c8d03aa5c4361f1d964f7e3d7dbe58445b))

* fix(matrix-script): prepare toml configuration *by Andy Thomas* ([`236255c`](https://github.com/andythomas/matr1x/commit/236255c8d03aa5c4361f1d964f7e3d7dbe58445b))

* fix(matrix-script): more merge fixes *by Andy Thomas* ([`236255c`](https://github.com/andythomas/matr1x/commit/236255c8d03aa5c4361f1d964f7e3d7dbe58445b))

* fix(matrix-script): do not import QPushButton *by Andy Thomas* ([`236255c`](https://github.com/andythomas/matr1x/commit/236255c8d03aa5c4361f1d964f7e3d7dbe58445b))

* fix(matrix-script): address comments in #742 *by Andy Thomas* ([`236255c`](https://github.com/andythomas/matr1x/commit/236255c8d03aa5c4361f1d964f7e3d7dbe58445b))

* fix(matrix-script): fix cancel/close behavior *by Andy Thomas* ([`236255c`](https://github.com/andythomas/matr1x/commit/236255c8d03aa5c4361f1d964f7e3d7dbe58445b))

* fix(matrix-script): delete unused QLineEdit *by Andy Thomas* ([`236255c`](https://github.com/andythomas/matr1x/commit/236255c8d03aa5c4361f1d964f7e3d7dbe58445b))

* fix(matrix-script): do not hard-code font size *by Andy Thomas* ([`236255c`](https://github.com/andythomas/matr1x/commit/236255c8d03aa5c4361f1d964f7e3d7dbe58445b))

* fix(matrix-script): remove toml imports *by Andy Thomas* ([`236255c`](https://github.com/andythomas/matr1x/commit/236255c8d03aa5c4361f1d964f7e3d7dbe58445b))

* fix(matrix-script): address review comments *by Andy Thomas* ([`236255c`](https://github.com/andythomas/matr1x/commit/236255c8d03aa5c4361f1d964f7e3d7dbe58445b))

* fix(docstrings): fix docstrings *by Andy Thomas* ([`236255c`](https://github.com/andythomas/matr1x/commit/236255c8d03aa5c4361f1d964f7e3d7dbe58445b))

* fix(eval): use l/rstrip instead of removeprefix/suffix (#763) *by pheowl* ([`36a26e1`](https://github.com/andythomas/matr1x/commit/36a26e18d0ba61fa416544f448588c1f12fa9fd5))

* fix(eval.py): fix issue with loadmatrix trying to access nonexistent key "comments" in (old) hdf5 files (#761) *by pheowl* ([`724c1b6`](https://github.com/andythomas/matr1x/commit/724c1b6f7588d82017330f96f7266030390fe499))

* fix(matrix,-matrix_script,-util): match behavior between matrix-script and matrix-gui *by pheowl* ([`16edf81`](https://github.com/andythomas/matr1x/commit/16edf8138153cd7e835030d0bd0fd6cd010336b2))

* fix(matrix_gui): improved handling of absence of file on input modification *by pheowl* ([`16edf81`](https://github.com/andythomas/matr1x/commit/16edf8138153cd7e835030d0bd0fd6cd010336b2))

* fix(matrix): remove some of the shouting *by pheowl* ([`16edf81`](https://github.com/andythomas/matr1x/commit/16edf8138153cd7e835030d0bd0fd6cd010336b2))

* fix(diverse-files): testing, refactoring, introducing editable flag, bugfixes *by pheowl* ([`16edf81`](https://github.com/andythomas/matr1x/commit/16edf8138153cd7e835030d0bd0fd6cd010336b2))

* fix(test_matrix): fix matrix tests to reflect changes to meta_data *by pheowl* ([`16edf81`](https://github.com/andythomas/matr1x/commit/16edf8138153cd7e835030d0bd0fd6cd010336b2))

* fix(tests): fix matrix-script linting test code (#752) *by Dominik Kriegner* ([`ab22dd2`](https://github.com/andythomas/matr1x/commit/ab22dd2fbbd7205fc6f913ef4268d7f353b83468))

* fix: remove control_dummy warning *by Andy Thomas* ([`80ee766`](https://github.com/andythomas/matr1x/commit/80ee766e3433205450f06a1e3b6f80179ada5e9c))

* fix(matrix-script): restore functionality of code in this PR *by Dominik Kriegner* ([`61f01e9`](https://github.com/andythomas/matr1x/commit/61f01e9309f7230ff413e875daf8b93ede83ce38))

* fix(PR-check): avoid formatting changes in main *by Dominik Kriegner* ([`61f01e9`](https://github.com/andythomas/matr1x/commit/61f01e9309f7230ff413e875daf8b93ede83ce38))

* fix(PR-check): correctly reference main *by Dominik Kriegner* ([`61f01e9`](https://github.com/andythomas/matr1x/commit/61f01e9309f7230ff413e875daf8b93ede83ce38))

* fix(PR-check): correct reference *by Dominik Kriegner* ([`61f01e9`](https://github.com/andythomas/matr1x/commit/61f01e9309f7230ff413e875daf8b93ede83ce38))

* fix(Keithley): write/read replaced by query in Keithley2450 *by baduraan* ([`95a8424`](https://github.com/andythomas/matr1x/commit/95a8424bbe8b8ea93a3ae5d3e4c1aa346c574556))

* fix(control-dummy): return correct value (#868) *by Andy Thomas* ([`7ec38d6`](https://github.com/andythomas/matr1x/commit/7ec38d6424a675e539568948ad1fa298b087d67a))

* fix(sweep-generator.svg): paper sheet is now white (#852) *by Andy Thomas* ([`315ab89`](https://github.com/andythomas/matr1x/commit/315ab89ac6954e9dfb22965d7e5371a1c9fe2e16))

* fix(sweep-generator.svg): paper sheet is now white *by Andy Thomas* ([`315ab89`](https://github.com/andythomas/matr1x/commit/315ab89ac6954e9dfb22965d7e5371a1c9fe2e16))

* fix(caenels): add missing header *by pheowl* ([`5fa1d47`](https://github.com/andythomas/matr1x/commit/5fa1d4712a176e88b47cd6503d088b7d894a8735))

* fix(caenels): reduce code, replace write/read combo with query *by pheowl* ([`b496f1e`](https://github.com/andythomas/matr1x/commit/b496f1eb0c2cd542a8d01130d4f11e97ad7319d3))

* fix(system_halbach,-nanotec): fix minor issues, adapt more recent code style for system_halbach *by pheowl* ([`90441ea`](https://github.com/andythomas/matr1x/commit/90441ea5e0fcbb2021cab587e8059eadc8ae53b6))

* fix(agilent.py): remove wrong file *by pheowl* ([`996bf6b`](https://github.com/andythomas/matr1x/commit/996bf6b2518c0a5af3cf8cea16641b93d80dfd6c))

* fix(__init__.py): potentially fix linter issues *by pheowl* ([`996bf6b`](https://github.com/andythomas/matr1x/commit/996bf6b2518c0a5af3cf8cea16641b93d80dfd6c))

* fix(__init__.py): move noqa statemtnt *by pheowl* ([`996bf6b`](https://github.com/andythomas/matr1x/commit/996bf6b2518c0a5af3cf8cea16641b93d80dfd6c))

* fix(__init__.py): move noqa statement back to original position *by pheowl* ([`996bf6b`](https://github.com/andythomas/matr1x/commit/996bf6b2518c0a5af3cf8cea16641b93d80dfd6c))

* fix(__init__.py): implement change by darker *by pheowl* ([`996bf6b`](https://github.com/andythomas/matr1x/commit/996bf6b2518c0a5af3cf8cea16641b93d80dfd6c))

* fix(many): fix linter comments *by Luise Siegl* ([`d5586cb`](https://github.com/andythomas/matr1x/commit/d5586cb0b8085ac007c7daf7e1be82d47ccaaf94))

* fix(spectrum_analyzer): remove spectrum analyzer file, already included in keysight library *by Luise Siegl* ([`d5586cb`](https://github.com/andythomas/matr1x/commit/d5586cb0b8085ac007c7daf7e1be82d47ccaaf94))

* fix(PR-check): use correct reference for darker (#716) *by Luise Siegl* ([`d5586cb`](https://github.com/andythomas/matr1x/commit/d5586cb0b8085ac007c7daf7e1be82d47ccaaf94))

* fix(PR-check): avoid formatting changes in main *by Luise Siegl* ([`d5586cb`](https://github.com/andythomas/matr1x/commit/d5586cb0b8085ac007c7daf7e1be82d47ccaaf94))

* fix(PR-check): correctly reference main *by Luise Siegl* ([`d5586cb`](https://github.com/andythomas/matr1x/commit/d5586cb0b8085ac007c7daf7e1be82d47ccaaf94))

* fix(PR-check): correct reference *by Luise Siegl* ([`d5586cb`](https://github.com/andythomas/matr1x/commit/d5586cb0b8085ac007c7daf7e1be82d47ccaaf94))

* fix(danfysik): address comments by @dkriegner *by Luise Siegl* ([`d5586cb`](https://github.com/andythomas/matr1x/commit/d5586cb0b8085ac007c7daf7e1be82d47ccaaf94))

* fix(pico.py): fix typos, wrong code and linter-induced errors *by Luise Siegl* ([`d5586cb`](https://github.com/andythomas/matr1x/commit/d5586cb0b8085ac007c7daf7e1be82d47ccaaf94))

* fix(pico): some more linter fixes *by Luise Siegl* ([`d5586cb`](https://github.com/andythomas/matr1x/commit/d5586cb0b8085ac007c7daf7e1be82d47ccaaf94))

* fix(system_elise/vna): merge current changes to ELISE system *by Luise Siegl* ([`d5586cb`](https://github.com/andythomas/matr1x/commit/d5586cb0b8085ac007c7daf7e1be82d47ccaaf94))

* fix(elise-systems): fix minor issues *by Luise Siegl* ([`d5586cb`](https://github.com/andythomas/matr1x/commit/d5586cb0b8085ac007c7daf7e1be82d47ccaaf94))

* fix(keysight.py): fix wrong reference to connection *by Luise Siegl* ([`d5586cb`](https://github.com/andythomas/matr1x/commit/d5586cb0b8085ac007c7daf7e1be82d47ccaaf94))

### Code style

* style: new icon colors improve visibility (#915) *by Andy Thomas* ([`a2dc0ca`](https://github.com/andythomas/matr1x/commit/a2dc0ca2b0f305bb3bcfb45179a02953cad54729))

* style: new icon colors improve visibility *by Andy Thomas* ([`a2dc0ca`](https://github.com/andythomas/matr1x/commit/a2dc0ca2b0f305bb3bcfb45179a02953cad54729))

* style(matrix-script): make linter happy :) *by Andy Thomas* ([`1939da6`](https://github.com/andythomas/matr1x/commit/1939da621c07bf8614edb32c3f80cde19bcf9aa7))

* style(matrix-script): fix documentation and review comments *by pheowl* ([`47b848e`](https://github.com/andythomas/matr1x/commit/47b848e82ff220ab05c6dd6426dadcd946dfdc15))

* style(matrix-script): reformat code autocompletion to match PEP484 *by pheowl* ([`47b848e`](https://github.com/andythomas/matr1x/commit/47b848e82ff220ab05c6dd6426dadcd946dfdc15))

* style(matrix-script): new default systems toolbar *by Andy Thomas* ([`3d2b367`](https://github.com/andythomas/matr1x/commit/3d2b367d703a1502fb2ce4d704726ba84ffb0e59))

* style(matrix-script): system icons get text *by Andy Thomas* ([`3d2b367`](https://github.com/andythomas/matr1x/commit/3d2b367d703a1502fb2ce4d704726ba84ffb0e59))

### Documentation

* docs: add/update docstrings to increase numpydoc compatible (#926) *by Dominik Kriegner* ([`5ee1794`](https://github.com/andythomas/matr1x/commit/5ee1794291f3310f1f84b1fef94f84322869f4a3))

* docs(util): add/update docstrings to be numpydoc compatible *by Dominik Kriegner* ([`5ee1794`](https://github.com/andythomas/matr1x/commit/5ee1794291f3310f1f84b1fef94f84322869f4a3))

* docs(system): reformat docstrings to numpydoc format *by Dominik Kriegner* ([`5ee1794`](https://github.com/andythomas/matr1x/commit/5ee1794291f3310f1f84b1fef94f84322869f4a3))

* docs(scpi-server): fix docstring format *by Dominik Kriegner* ([`5ee1794`](https://github.com/andythomas/matr1x/commit/5ee1794291f3310f1f84b1fef94f84322869f4a3))

* docs(gui_util): add/update docstrings to be numpydoc compatible *by Dominik Kriegner* ([`5ee1794`](https://github.com/andythomas/matr1x/commit/5ee1794291f3310f1f84b1fef94f84322869f4a3))

* docs: add docstrings to all matr1x/systems (#908) *by Dominik Kriegner* ([`c6b67de`](https://github.com/andythomas/matr1x/commit/c6b67de250f3904c2d305638318d69b8a55ada67))

* docs: AI assisted docstrings in matr1x/control (#904) *by Dominik Kriegner* ([`b63f2e3`](https://github.com/andythomas/matr1x/commit/b63f2e3e73581e314147f34183837ada74fbc435))

* docs: let zed ai format the docstrings *by Dominik Kriegner* ([`b63f2e3`](https://github.com/andythomas/matr1x/commit/b63f2e3e73581e314147f34183837ada74fbc435))

* docs(hdf5): add note on the in/efficiency of the hdf5 format (#866) *by Dominik Kriegner* ([`cf4a1c5`](https://github.com/andythomas/matr1x/commit/cf4a1c542ec2c5db9bd9f8bf1ecd361c27e08523))

* docs(hdf5): add note on the in/efficiency of the hdf5 format *by Dominik Kriegner* ([`cf4a1c5`](https://github.com/andythomas/matr1x/commit/cf4a1c542ec2c5db9bd9f8bf1ecd361c27e08523))

* docs: reformat several docstrings (#735) *by nadnab* ([`0c1b5be`](https://github.com/andythomas/matr1x/commit/0c1b5bee4b978ab1d2eaa5f1befecb8cd8ffc836))

* docs(matrix/eval.py): reformat docstrings ReST *by nadnab* ([`0c1b5be`](https://github.com/andythomas/matr1x/commit/0c1b5bee4b978ab1d2eaa5f1befecb8cd8ffc836))

* docs(matrix/eval.py): use numpydoc style *by nadnab* ([`0c1b5be`](https://github.com/andythomas/matr1x/commit/0c1b5bee4b978ab1d2eaa5f1befecb8cd8ffc836))

* docs(matrix/eval.py): use ruff *by nadnab* ([`0c1b5be`](https://github.com/andythomas/matr1x/commit/0c1b5bee4b978ab1d2eaa5f1befecb8cd8ffc836))

* docs: reformat several docstrings (#735) *by Andy Thomas* ([`8d0992b`](https://github.com/andythomas/matr1x/commit/8d0992b215faf1259d6c32cfa96d6fbeec1b3fb2))

* docs(matrix/eval.py): reformat docstrings ReST *by Andy Thomas* ([`8d0992b`](https://github.com/andythomas/matr1x/commit/8d0992b215faf1259d6c32cfa96d6fbeec1b3fb2))

* docs(matrix/eval.py): use numpydoc style *by Andy Thomas* ([`8d0992b`](https://github.com/andythomas/matr1x/commit/8d0992b215faf1259d6c32cfa96d6fbeec1b3fb2))

* docs(matrix/eval.py): use ruff *by Andy Thomas* ([`8d0992b`](https://github.com/andythomas/matr1x/commit/8d0992b215faf1259d6c32cfa96d6fbeec1b3fb2))

* docs: more detailed comments regarding the decorator use *by Dominik Kriegner* ([`61f01e9`](https://github.com/andythomas/matr1x/commit/61f01e9309f7230ff413e875daf8b93ede83ce38))

### Features

* feat(AJA): add pulsed heating option to allow stabilizing lower temperature (#930) *by Dominik Kriegner* ([`3583e39`](https://github.com/andythomas/matr1x/commit/3583e3963305e3ab326f063e7e6ad5532efdd485))

* feat(controlAJA): Merge vacuum related guidicts (#928) *by Dominik Kriegner* ([`39b7d6e`](https://github.com/andythomas/matr1x/commit/39b7d6e29103e97d24ef1ba70d621621469d199c))

* feat(emil): Ukon fmr emil (#686) *by Dominik Kriegner* ([`40fb195`](https://github.com/andythomas/matr1x/commit/40fb195d5e93f534ef38cbd91bf9f5e518e48b15))

* feat(system_picovna,-pico): added new driver for picovna running with picovna5 software *by Dominik Kriegner* ([`40fb195`](https://github.com/andythomas/matr1x/commit/40fb195d5e93f534ef38cbd91bf9f5e518e48b15))

* feat(keyisght.py): Agilent8114 driver (#727) *by Dominik Kriegner* ([`40fb195`](https://github.com/andythomas/matr1x/commit/40fb195d5e93f534ef38cbd91bf9f5e518e48b15))

* feat(agilent.py): Initial draft of Agilent8114A driver *by Dominik Kriegner* ([`40fb195`](https://github.com/andythomas/matr1x/commit/40fb195d5e93f534ef38cbd91bf9f5e518e48b15))

* feat(keysight): Add driver for Agilent8114A pulse generator *by Dominik Kriegner* ([`40fb195`](https://github.com/andythomas/matr1x/commit/40fb195d5e93f534ef38cbd91bf9f5e518e48b15))

* feat(Halbach update): merge most recent changes from Halbach setup. (#730) *by Dominik Kriegner* ([`40fb195`](https://github.com/andythomas/matr1x/commit/40fb195d5e93f534ef38cbd91bf9f5e518e48b15))

* feat(halbach-system): bring halbach system to current state *by Dominik Kriegner* ([`40fb195`](https://github.com/andythomas/matr1x/commit/40fb195d5e93f534ef38cbd91bf9f5e518e48b15))

* feat(moke-setup): Mfli integrated reduced branch, containing only essential parts of system (#732) *by Dominik Kriegner* ([`40fb195`](https://github.com/andythomas/matr1x/commit/40fb195d5e93f534ef38cbd91bf9f5e518e48b15))

* feat(control_chaos): Chaos update, introduce changes after bugfixing and migration (#736) *by Dominik Kriegner* ([`40fb195`](https://github.com/andythomas/matr1x/commit/40fb195d5e93f534ef38cbd91bf9f5e518e48b15))

* feat(farmic): Merge main components from Faraday microscope (#741) *by Dominik Kriegner* ([`40fb195`](https://github.com/andythomas/matr1x/commit/40fb195d5e93f534ef38cbd91bf9f5e518e48b15))

* feat(systems,-control_farmic): remove excess systems, add optional dependency for vmbpy *by Dominik Kriegner* ([`40fb195`](https://github.com/andythomas/matr1x/commit/40fb195d5e93f534ef38cbd91bf9f5e518e48b15))

* feat(controlAJA): add PID parameters, RF4 output, and some tweaks (#795) *by Dominik Kriegner* ([`40fb195`](https://github.com/andythomas/matr1x/commit/40fb195d5e93f534ef38cbd91bf9f5e518e48b15))

* feat(AJA): add PID parameters, RF forward/reverse power *by Dominik Kriegner* ([`40fb195`](https://github.com/andythomas/matr1x/commit/40fb195d5e93f534ef38cbd91bf9f5e518e48b15))

* feat(controlAJA): Merge vacuum related guidicts (#928) *by Dominik Kriegner* ([`40fb195`](https://github.com/andythomas/matr1x/commit/40fb195d5e93f534ef38cbd91bf9f5e518e48b15))

* feat(AJA): add pulsed heating option to allow stabilizing lower temperature (#930) *by Dominik Kriegner* ([`40fb195`](https://github.com/andythomas/matr1x/commit/40fb195d5e93f534ef38cbd91bf9f5e518e48b15))

* feat(matrix-preview): add initial toolbar and menu *by Dominik Kriegner* ([`2eba23c`](https://github.com/andythomas/matr1x/commit/2eba23cf74209b6cad6714cce5ea8169023ee21f))

* feat(matrix-preview): add toolbar and menu (#946) *by Andy Thomas* ([`15bbc55`](https://github.com/andythomas/matr1x/commit/15bbc553edc72ce3a4c2ff4935d971a71d037b3a))

* feat(matrix-preview): add initial toolbar and menu *by Andy Thomas* ([`15bbc55`](https://github.com/andythomas/matr1x/commit/15bbc553edc72ce3a4c2ff4935d971a71d037b3a))

* feat(gui_util): Preview change active plot on click (#943) *by pheowl* ([`f3abe18`](https://github.com/andythomas/matr1x/commit/f3abe18b5abfedb0d9063812bf558f9f5fbad2a5))

* feat(gui_util): clicking on plot changes currently selected plot window *by pheowl* ([`f3abe18`](https://github.com/andythomas/matr1x/commit/f3abe18b5abfedb0d9063812bf558f9f5fbad2a5))

* feat(sweep-generator): introduce menu bar for sweep generator (#910) *by Andy Thomas* ([`c49b745`](https://github.com/andythomas/matr1x/commit/c49b745bd115efe2ab2a5f83420d9bf89bfabae6))

* feat(matrix-gui): add 'show toolbar' to view menu (#913) *by Andy Thomas* ([`d52ed4c`](https://github.com/andythomas/matr1x/commit/d52ed4c625f4964b2623c13bba0fe7931e1fe1a5))

* feat(installer): new based Python cross-platform installer (#864) *by Dominik Kriegner* ([`a91f271`](https://github.com/andythomas/matr1x/commit/a91f271d5e51b9995a410498bbd17d724d3358d6))

* feat(install): initial python based installer *by Dominik Kriegner* ([`a91f271`](https://github.com/andythomas/matr1x/commit/a91f271d5e51b9995a410498bbd17d724d3358d6))

* feat(lakeshore.py): allow control of manual offset (#882) *by Andy Thomas* ([`5ebc772`](https://github.com/andythomas/matr1x/commit/5ebc772906304fe17df0f1ae833206933d088144))

* feat(gui_util): add config editor that allows to modify the system config (#853) *by pheowl* ([`ad3cc83`](https://github.com/andythomas/matr1x/commit/ad3cc83c17ed9e14c62dcb04f8bde55ccec354d4))

* feat(gui_util): add config editor that allows to modify the configuration *by pheowl* ([`ad3cc83`](https://github.com/andythomas/matr1x/commit/ad3cc83c17ed9e14c62dcb04f8bde55ccec354d4))

* feat(emil): Ukon fmr emil (#686) *by pheowl* ([`4441837`](https://github.com/andythomas/matr1x/commit/444183762010012233b046c0dea0e35ae7566e7e))

* feat(system_picovna,-pico): added new driver for picovna running with picovna5 software *by pheowl* ([`4441837`](https://github.com/andythomas/matr1x/commit/444183762010012233b046c0dea0e35ae7566e7e))

* feat(keyisght.py): Agilent8114 driver (#727) *by pheowl* ([`4441837`](https://github.com/andythomas/matr1x/commit/444183762010012233b046c0dea0e35ae7566e7e))

* feat(agilent.py): Initial draft of Agilent8114A driver *by pheowl* ([`4441837`](https://github.com/andythomas/matr1x/commit/444183762010012233b046c0dea0e35ae7566e7e))

* feat(keysight): Add driver for Agilent8114A pulse generator *by pheowl* ([`4441837`](https://github.com/andythomas/matr1x/commit/444183762010012233b046c0dea0e35ae7566e7e))

* feat(Halbach update): merge most recent changes from Halbach setup. (#730) *by pheowl* ([`4441837`](https://github.com/andythomas/matr1x/commit/444183762010012233b046c0dea0e35ae7566e7e))

* feat(halbach-system): bring halbach system to current state *by pheowl* ([`4441837`](https://github.com/andythomas/matr1x/commit/444183762010012233b046c0dea0e35ae7566e7e))

* feat(moke-setup): Mfli integrated reduced branch, containing only essential parts of system (#732) *by pheowl* ([`4441837`](https://github.com/andythomas/matr1x/commit/444183762010012233b046c0dea0e35ae7566e7e))

* feat(control_chaos): Chaos update, introduce changes after bugfixing and migration (#736) *by pheowl* ([`4441837`](https://github.com/andythomas/matr1x/commit/444183762010012233b046c0dea0e35ae7566e7e))

* feat(farmic): Merge main components from Faraday microscope (#741) *by pheowl* ([`4441837`](https://github.com/andythomas/matr1x/commit/444183762010012233b046c0dea0e35ae7566e7e))

* feat(systems,-control_farmic): remove excess systems, add optional dependency for vmbpy *by pheowl* ([`4441837`](https://github.com/andythomas/matr1x/commit/444183762010012233b046c0dea0e35ae7566e7e))

* feat(controlAJA): add PID parameters, RF4 output, and some tweaks (#795) *by pheowl* ([`4441837`](https://github.com/andythomas/matr1x/commit/444183762010012233b046c0dea0e35ae7566e7e))

* feat(AJA): add PID parameters, RF forward/reverse power *by pheowl* ([`4441837`](https://github.com/andythomas/matr1x/commit/444183762010012233b046c0dea0e35ae7566e7e))

* feat(system_noise): add systems to measure electronic noise *by pheowl* ([`4441837`](https://github.com/andythomas/matr1x/commit/444183762010012233b046c0dea0e35ae7566e7e))

* feat(matrix-script): allow to set abort state in the GUI (#862) *by Andy Thomas* ([`1939da6`](https://github.com/andythomas/matr1x/commit/1939da621c07bf8614edb32c3f80cde19bcf9aa7))

* feat(matrix-script): add buttons for stop mode *by Andy Thomas* ([`1939da6`](https://github.com/andythomas/matr1x/commit/1939da621c07bf8614edb32c3f80cde19bcf9aa7))

* feat(matrix/matrix_script-backend): add capability to externally abort/finish the measurement *by Andy Thomas* ([`1939da6`](https://github.com/andythomas/matr1x/commit/1939da621c07bf8614edb32c3f80cde19bcf9aa7))

* feat(matrix-gui): introduce menu bar for matrix gui (#871) *by Andy Thomas* ([`0174fdd`](https://github.com/andythomas/matr1x/commit/0174fdd6ed4384cdf445151edb2aacd815e5419e))

* feat(matrix_gui): use same Widget for meta data as matrix-script *by Andy Thomas* ([`0174fdd`](https://github.com/andythomas/matr1x/commit/0174fdd6ed4384cdf445151edb2aacd815e5419e))

* feat(matrix-gui): introduce toolbar *by Andy Thomas* ([`0174fdd`](https://github.com/andythomas/matr1x/commit/0174fdd6ed4384cdf445151edb2aacd815e5419e))

* feat(gui_util): allow more icons *by Andy Thomas* ([`0174fdd`](https://github.com/andythomas/matr1x/commit/0174fdd6ed4384cdf445151edb2aacd815e5419e))

* feat(gui_util): introduce MLineEdit *by Andy Thomas* ([`0174fdd`](https://github.com/andythomas/matr1x/commit/0174fdd6ed4384cdf445151edb2aacd815e5419e))

* feat(matrix-gui): save and restore window *by Andy Thomas* ([`0174fdd`](https://github.com/andythomas/matr1x/commit/0174fdd6ed4384cdf445151edb2aacd815e5419e))

* feat(ma8): parse System query string back to dictionary (#830) *by Dominik Kriegner* ([`3b711ec`](https://github.com/andythomas/matr1x/commit/3b711ecc7a28cf1aa4d2ad4f4c9f96d4908d77f4))

* feat(matrix-script): allow storing the user script *by Dominik Kriegner* ([`3b711ec`](https://github.com/andythomas/matr1x/commit/3b711ecc7a28cf1aa4d2ad4f4c9f96d4908d77f4))

* feat(ma8): parse System query string back to dictionary *by Dominik Kriegner* ([`3b711ec`](https://github.com/andythomas/matr1x/commit/3b711ecc7a28cf1aa4d2ad4f4c9f96d4908d77f4))

* feat(gui_util/MetaViewerWidget): migrate metaviewerwidget to tree view *by Dominik Kriegner* ([`3b711ec`](https://github.com/andythomas/matr1x/commit/3b711ecc7a28cf1aa4d2ad4f4c9f96d4908d77f4))

* feat(gui_util): improve capabilities of meta data viewer widget *by Dominik Kriegner* ([`3b711ec`](https://github.com/andythomas/matr1x/commit/3b711ecc7a28cf1aa4d2ad4f4c9f96d4908d77f4))

* feat(matrix_gui): use same widget for meta data as matrix-script (#827) *by pheowl* ([`36a2a3b`](https://github.com/andythomas/matr1x/commit/36a2a3b5be22e7298d22a21bc21e2d3bc9c60582))

* feat(matrix_gui): use same Widget for meta data as matrix-script *by pheowl* ([`36a2a3b`](https://github.com/andythomas/matr1x/commit/36a2a3b5be22e7298d22a21bc21e2d3bc9c60582))

* feat(matrix_script): allow direct opening of the current data file with matrix_preview from matrix_script (#831) *by pheowl* ([`47b848e`](https://github.com/andythomas/matr1x/commit/47b848e82ff220ab05c6dd6426dadcd946dfdc15))

* feat(matrix_script): allow direct opening of the current data file with matrix_preview from matrix_script *by pheowl* ([`47b848e`](https://github.com/andythomas/matr1x/commit/47b848e82ff220ab05c6dd6426dadcd946dfdc15))

* feat(system_eLabFTW): system for eLabFTW (#671) *by nadnab* ([`0c1b5be`](https://github.com/andythomas/matr1x/commit/0c1b5bee4b978ab1d2eaa5f1befecb8cd8ffc836))

* feat(tests/data): add data from different software versions ([h5.]ma6/ma7) to test backwards compatibility *by nadnab* ([`0c1b5be`](https://github.com/andythomas/matr1x/commit/0c1b5bee4b978ab1d2eaa5f1befecb8cd8ffc836))

* feat(ma8): transform file format to ma8 (#722) *by nadnab* ([`0c1b5be`](https://github.com/andythomas/matr1x/commit/0c1b5bee4b978ab1d2eaa5f1befecb8cd8ffc836))

* feat(ma8): transform file format to ma8 *by nadnab* ([`0c1b5be`](https://github.com/andythomas/matr1x/commit/0c1b5bee4b978ab1d2eaa5f1befecb8cd8ffc836))

* feat(meta data handling): Improved and consistent meta data handling. (#746) *by nadnab* ([`0c1b5be`](https://github.com/andythomas/matr1x/commit/0c1b5bee4b978ab1d2eaa5f1befecb8cd8ffc836))

* feat(matrix-meta-data-subsystem): implement first draft of matrix-gui with meta-data visibility *by nadnab* ([`0c1b5be`](https://github.com/andythomas/matr1x/commit/0c1b5bee4b978ab1d2eaa5f1befecb8cd8ffc836))

* feat(config): change config to toml format and merge with install.cfg (#759) *by nadnab* ([`0c1b5be`](https://github.com/andythomas/matr1x/commit/0c1b5bee4b978ab1d2eaa5f1befecb8cd8ffc836))

* feat(matrix-script): allow storing the user script in the datafile (#823) *by Dominik Kriegner* ([`130eece`](https://github.com/andythomas/matr1x/commit/130eeced2a32c05433116267fed712c914c9ff92))

* feat(matrix-script): allow storing the user script *by Dominik Kriegner* ([`130eece`](https://github.com/andythomas/matr1x/commit/130eeced2a32c05433116267fed712c914c9ff92))

* feat(matrix-script): add a pulldown menu to save (#814) *by Andy Thomas* ([`384fb73`](https://github.com/andythomas/matr1x/commit/384fb73cae52f4e87ee802f8544852907b74c6a1))

* feat(matrix-script): remember layout of the widgets (#810) *by Andy Thomas* ([`3d2b367`](https://github.com/andythomas/matr1x/commit/3d2b367d703a1502fb2ce4d704726ba84ffb0e59))

* feat(matrix-script): remember layout *by Andy Thomas* ([`3d2b367`](https://github.com/andythomas/matr1x/commit/3d2b367d703a1502fb2ce4d704726ba84ffb0e59))

* feat(matrix_script/util): add `end_script` function to matrix_script (#797) *by pheowl* ([`215e48a`](https://github.com/andythomas/matr1x/commit/215e48a97d5d308650f6ccd72bec89aaf85bee8f))

* feat(matrix_script/util): add `end_script` function to matrix_script *by pheowl* ([`215e48a`](https://github.com/andythomas/matr1x/commit/215e48a97d5d308650f6ccd72bec89aaf85bee8f))

* feat(gui_util): add MetaDataViewer/Editor based on Tabular display *by Andy Thomas* ([`4eefb5b`](https://github.com/andythomas/matr1x/commit/4eefb5b6e0b65ef71961f2a6ad71cf1c0a20f2e7))

* feat(matrix-script): introduce new GUI (#742) *by Andy Thomas* ([`236255c`](https://github.com/andythomas/matr1x/commit/236255c8d03aa5c4361f1d964f7e3d7dbe58445b))

* feat(matrix-script): new metadata editor dialog and menu *by Andy Thomas* ([`236255c`](https://github.com/andythomas/matr1x/commit/236255c8d03aa5c4361f1d964f7e3d7dbe58445b))

* feat(matrix-script): add menu items *by Andy Thomas* ([`236255c`](https://github.com/andythomas/matr1x/commit/236255c8d03aa5c4361f1d964f7e3d7dbe58445b))

* feat(matrix-script): add edit menu *by Andy Thomas* ([`236255c`](https://github.com/andythomas/matr1x/commit/236255c8d03aa5c4361f1d964f7e3d7dbe58445b))

* feat(matrix-script): add info box *by Andy Thomas* ([`236255c`](https://github.com/andythomas/matr1x/commit/236255c8d03aa5c4361f1d964f7e3d7dbe58445b))

* feat(matrix-script): introduce view menu *by Andy Thomas* ([`236255c`](https://github.com/andythomas/matr1x/commit/236255c8d03aa5c4361f1d964f7e3d7dbe58445b))

* feat(matrix-script): shortcut via configuration *by Andy Thomas* ([`236255c`](https://github.com/andythomas/matr1x/commit/236255c8d03aa5c4361f1d964f7e3d7dbe58445b))

* feat(matrix-script): add 'save' functionality *by Andy Thomas* ([`236255c`](https://github.com/andythomas/matr1x/commit/236255c8d03aa5c4361f1d964f7e3d7dbe58445b))

* feat(matrix-script): delete key in system list *by Andy Thomas* ([`236255c`](https://github.com/andythomas/matr1x/commit/236255c8d03aa5c4361f1d964f7e3d7dbe58445b))

* feat(config): change config to toml format and merge with install.cfg (#759) *by Dominik Kriegner* ([`44753ab`](https://github.com/andythomas/matr1x/commit/44753aba9a055751e1c177157b43683d28252eb3))

* feat(meta data handling): Improved and consistent meta data handling. (#746) *by pheowl* ([`16edf81`](https://github.com/andythomas/matr1x/commit/16edf8138153cd7e835030d0bd0fd6cd010336b2))

* feat(matrix-meta-data-subsystem): implement first draft of matrix-gui with meta-data visibility *by pheowl* ([`16edf81`](https://github.com/andythomas/matr1x/commit/16edf8138153cd7e835030d0bd0fd6cd010336b2))

* feat(ma8): transform file format to ma8 (#722) *by Dominik Kriegner* ([`cd3e043`](https://github.com/andythomas/matr1x/commit/cd3e043ec3f03f01085e1bfb739302aabe9e64e4))

* feat(ma8): transform file format to ma8 *by Dominik Kriegner* ([`cd3e043`](https://github.com/andythomas/matr1x/commit/cd3e043ec3f03f01085e1bfb739302aabe9e64e4))

* feat(tests/data): add data from different software versions ([h5.]ma6/ma7) to test backwards compatibility *by Dominik Kriegner* ([`138c78b`](https://github.com/andythomas/matr1x/commit/138c78b6404e3c31b10a0ceba7a4a51f9c5bd2c3))

* feat(matrix): add comments to datafile upon aborting (#694) *by Dominik Kriegner* ([`61f01e9`](https://github.com/andythomas/matr1x/commit/61f01e9309f7230ff413e875daf8b93ede83ce38))

* feat(matrix): add comments to datafile upon aborting *by Dominik Kriegner* ([`61f01e9`](https://github.com/andythomas/matr1x/commit/61f01e9309f7230ff413e875daf8b93ede83ce38))

* feat: Keithley nvm: making sure the device is ready after config *by baduraan* ([`0ee5111`](https://github.com/andythomas/matr1x/commit/0ee5111c2525f008342ceaa1640bce3978a389a3))

* feat(moke-setup): Mfli integrated reduced branch, containing only essential parts of system (#732) *by pheowl* ([`b496f1e`](https://github.com/andythomas/matr1x/commit/b496f1eb0c2cd542a8d01130d4f11e97ad7319d3))

* feat(Halbach update): merge most recent changes from Halbach setup. (#730) *by pheowl* ([`90441ea`](https://github.com/andythomas/matr1x/commit/90441ea5e0fcbb2021cab587e8059eadc8ae53b6))

* feat(halbach-system): bring halbach system to current state *by pheowl* ([`90441ea`](https://github.com/andythomas/matr1x/commit/90441ea5e0fcbb2021cab587e8059eadc8ae53b6))

* feat(keyisght.py): Agilent8114 driver (#727) *by pheowl* ([`996bf6b`](https://github.com/andythomas/matr1x/commit/996bf6b2518c0a5af3cf8cea16641b93d80dfd6c))

* feat(agilent.py): Initial draft of Agilent8114A driver *by pheowl* ([`996bf6b`](https://github.com/andythomas/matr1x/commit/996bf6b2518c0a5af3cf8cea16641b93d80dfd6c))

* feat(keysight): Add driver for Agilent8114A pulse generator *by pheowl* ([`996bf6b`](https://github.com/andythomas/matr1x/commit/996bf6b2518c0a5af3cf8cea16641b93d80dfd6c))

* feat(emil): Ukon fmr emil (#686) *by Luise Siegl* ([`d5586cb`](https://github.com/andythomas/matr1x/commit/d5586cb0b8085ac007c7daf7e1be82d47ccaaf94))

* feat(system_picovna,-pico): added new driver for picovna running with picovna5 software *by Luise Siegl* ([`d5586cb`](https://github.com/andythomas/matr1x/commit/d5586cb0b8085ac007c7daf7e1be82d47ccaaf94))

### Unknown

* make twickenham header equal to other headers *by Dominik Kriegner* ([`0ee4471`](https://github.com/andythomas/matr1x/commit/0ee4471da2e148bca2ccc956c96de9f2b59d94e3))

* Update core_library/matr1x/devices/keithley.py *by baduraan* ([`6120cee`](https://github.com/andythomas/matr1x/commit/6120cee61b1168ac49a8b34fa2f04f0d1d8f88b7))

* remove change of default timeouts from DMM, NVM, SMU2450 *by baduraan* ([`834830f`](https://github.com/andythomas/matr1x/commit/834830fe08cf6eb6bb1279317a6cc8935c68afc8))

* call unwrapped function in isodevice *by baduraan* ([`982eb0f`](https://github.com/andythomas/matr1x/commit/982eb0fb683f2c8a2c9fcd0a8a6b799f633582cc))

* ruff action fixes (#925) *by github-actions[bot]* ([`ea1d549`](https://github.com/andythomas/matr1x/commit/ea1d5496b612efa9e2cd4724c80ae483c224482d))

* fix problems found by ruff *by baduraan* ([`770000f`](https://github.com/andythomas/matr1x/commit/770000fe1485e78d3c851fc734a1d84ad975c650))

* move Twickenham helium level meter *by baduraan* ([`075a80c`](https://github.com/andythomas/matr1x/commit/075a80c977b548b0ab1d59558abe941e90535590))

* remove not needed imports *by baduraan* ([`824550f`](https://github.com/andythomas/matr1x/commit/824550fabddcf97d957072037cbb10404ecc380c))

* fix merge problems *by baduraan* ([`8f417bb`](https://github.com/andythomas/matr1x/commit/8f417bbea43b3a66dfb4b690a6420b1d39ee415d))

## v7.4.0 (2024-08-20)

### Bug fixes

* fix(matrix-script): always append output on end of the output field (#713) *by Dominik Kriegner* ([`884baba`](https://github.com/andythomas/matr1x/commit/884baba0320961936b347fee8a83fd35049341b5))

* fix(INSTALL): remove leftover inconsistencies *by Andy Thomas* ([`6ebf1ef`](https://github.com/andythomas/matr1x/commit/6ebf1ef2c7e29c8e1cd6d78b170a679717fa89ca))

* fix(matrix-script): completely remove send_button usage *by Dominik Kriegner* ([`b71a5ce`](https://github.com/andythomas/matr1x/commit/b71a5ceca4eb7d5e9bf2fbc9744dcbdf97268941))

* fix(INSTALL): refactor Windows installer *by Andy Thomas* ([`9036b41`](https://github.com/andythomas/matr1x/commit/9036b41f1b2699c70ac0eb340205a263baed56af))

* fix(INSTALL.ps1): correct powershell created by Mac-User *by Andy Thomas* ([`9036b41`](https://github.com/andythomas/matr1x/commit/9036b41f1b2699c70ac0eb340205a263baed56af))

* fix(loadmatrix): replace None by 0 instead of NaN (#666) *by Dominik Kriegner* ([`f968e32`](https://github.com/andythomas/matr1x/commit/f968e3249aba90630cd88a939b88b494b58507c8))

* fix(loadmatrix): replace None by 0 instead of NaN *by Dominik Kriegner* ([`f968e32`](https://github.com/andythomas/matr1x/commit/f968e3249aba90630cd88a939b88b494b58507c8))

* fix(loadmatrix): replace numpy.genfromtxt by pandas.read_csv *by Dominik Kriegner* ([`f968e32`](https://github.com/andythomas/matr1x/commit/f968e3249aba90630cd88a939b88b494b58507c8))

* fix(loadmatrix): ignore comment lines starting with '#' *by Dominik Kriegner* ([`f968e32`](https://github.com/andythomas/matr1x/commit/f968e3249aba90630cd88a939b88b494b58507c8))

* fix(nanotec): fix linter error *by Luise Siegl* ([`53fb1b8`](https://github.com/andythomas/matr1x/commit/53fb1b87ed4f597d3e6c5f4166d3c6e43b07b6df))

* fix(devices): add device description for less known devices *by Luise Siegl* ([`53fb1b8`](https://github.com/andythomas/matr1x/commit/53fb1b87ed4f597d3e6c5f4166d3c6e43b07b6df))

* fix(scpi_dev): scpi_dev must answer to satisfy communication requirements (#669) *by Dominik Kriegner* ([`ec32a50`](https://github.com/andythomas/matr1x/commit/ec32a508511dd404fdd959b08b53ab22cc66d8fe))

* fix(matrix-preview): allow showing columns with some None values (#652) *by Dominik Kriegner* ([`93f460c`](https://github.com/andythomas/matr1x/commit/93f460c72cf36c47c36492ae6e154a1d4cd45ca9))

* fix(ci): update, fix and upgrade automated release workflows (#654) *by Andy Thomas* ([`6c9dff3`](https://github.com/andythomas/matr1x/commit/6c9dff3b3cb63a80dfbffc5884d62ae58dbb08d1))

* fix(pyproject.toml): Use correct version number *by Andy Thomas* ([`6c9dff3`](https://github.com/andythomas/matr1x/commit/6c9dff3b3cb63a80dfbffc5884d62ae58dbb08d1))

* fix: fix workflow syntax *by Andy Thomas* ([`6c9dff3`](https://github.com/andythomas/matr1x/commit/6c9dff3b3cb63a80dfbffc5884d62ae58dbb08d1))

* fix: fix another workflow syntax error *by Andy Thomas* ([`6c9dff3`](https://github.com/andythomas/matr1x/commit/6c9dff3b3cb63a80dfbffc5884d62ae58dbb08d1))

* fix: use correct environment variable *by Andy Thomas* ([`6c9dff3`](https://github.com/andythomas/matr1x/commit/6c9dff3b3cb63a80dfbffc5884d62ae58dbb08d1))

* fix(gui_util): address comments by @dkriegner, implemented option 1 *by pheowl* ([`f27c23f`](https://github.com/andythomas/matr1x/commit/f27c23fbfa2cae27638c3ae85710741df4797969))

* fix(gui_util): adapt format of license statement *by pheowl* ([`f27c23f`](https://github.com/andythomas/matr1x/commit/f27c23fbfa2cae27638c3ae85710741df4797969))

* fix(gui_util): make date distinction a bit more fine grained *by pheowl* ([`f27c23f`](https://github.com/andythomas/matr1x/commit/f27c23fbfa2cae27638c3ae85710741df4797969))

* fix(eval.py,-gui_util.py): fix handling of data files containing just a single data point (#643) *by pheowl* ([`54be5f8`](https://github.com/andythomas/matr1x/commit/54be5f84be8cddef7b09aad65fa6957d94257ad2))

* fix(matrix): catch common errors and misconfigurations (#636) *by Andy Thomas* ([`360fff1`](https://github.com/andythomas/matr1x/commit/360fff139a461d45918cc8f8ee2ba3fc0a310407))

* fix(matrix.py): move the socket communication outside of function to prevent the gui getting stuck *by Andy Thomas* ([`360fff1`](https://github.com/andythomas/matr1x/commit/360fff139a461d45918cc8f8ee2ba3fc0a310407))

* fix(matrix.py): add missing close of input file after reading the header *by Andy Thomas* ([`360fff1`](https://github.com/andythomas/matr1x/commit/360fff139a461d45918cc8f8ee2ba3fc0a310407))

* fix(matrix.py): address comments by @dkriegner, 2. still missing *by Andy Thomas* ([`360fff1`](https://github.com/andythomas/matr1x/commit/360fff139a461d45918cc8f8ee2ba3fc0a310407))

* fix: graceful handling of misconfiguration of systemsDirectory. *by Andy Thomas* ([`360fff1`](https://github.com/andythomas/matr1x/commit/360fff139a461d45918cc8f8ee2ba3fc0a310407))

* fix(matrix_script.py): make linter less agressive, only halt script execution on syntax errors (#631) *by pheowl* ([`bf360fc`](https://github.com/andythomas/matr1x/commit/bf360fc7bda0c294c85e7731b0a5047f4bc9663b))

* fix(matrix_script.py): make linter less agressive, only halt script execution on syntax errors *by pheowl* ([`bf360fc`](https://github.com/andythomas/matr1x/commit/bf360fc7bda0c294c85e7731b0a5047f4bc9663b))

* fix(matrix_script): fix code issue with linter failing on message_args of wrong type, distinguish linter errors and warnings based on list *by pheowl* ([`bf360fc`](https://github.com/andythomas/matr1x/commit/bf360fc7bda0c294c85e7731b0a5047f4bc9663b))

* fix(matrix_script.py): disable load and help system buttons when script is executed. closes #621 (#628) *by pheowl* ([`6d68078`](https://github.com/andythomas/matr1x/commit/6d68078bb334be73580548e8614dc16aca91b17b))

* fix(matrix): Avoid implicit type conversion *by Andy Thomas* ([`5b06be9`](https://github.com/andythomas/matr1x/commit/5b06be90c2d76d8f97b35c65f2d6474978036cfe))

* fix(control-aja): manually set baud rate in devices *by Dominik Kriegner* ([`0922deb`](https://github.com/andythomas/matr1x/commit/0922deb3ac8e5cb1e0d08afbf7c05fafda116ed8))

* fix(system): make correct file name printed *by Dominik Kriegner* ([`6d4aacd`](https://github.com/andythomas/matr1x/commit/6d4aacd868f846e236a8c2ace37a2e401f16d3b3))

* fix(control_ln2cry,-cryovac): add comments, fix minor issues, address comments by @dkriegner *by pheowl* ([`bc668b6`](https://github.com/andythomas/matr1x/commit/bc668b68246c5869e62175f72036520c891b39ad))

* fix(control_ln2cryo): fix wrong key *by pheowl* ([`bc668b6`](https://github.com/andythomas/matr1x/commit/bc668b68246c5869e62175f72036520c891b39ad))

* fix(control-aja): setup logging and hiding (#590) *by Dominik Kriegner* ([`dc17a35`](https://github.com/andythomas/matr1x/commit/dc17a35bda4623d9f61621cce12b106a2266164c))

* fix(system_dummy_feature/hdf5/meas): fix comments/description, remove custom function area *by Dominik Kriegner* ([`5145e48`](https://github.com/andythomas/matr1x/commit/5145e4848d9f4e00f5e81e4967a72c37c6cd8eb7))

* fix(matrix_script): fix broken system check *by pheowl* ([`1e89d78`](https://github.com/andythomas/matr1x/commit/1e89d78da0599002d7d49038a8ab5a8622c21fe4))

* fix(control-subsystem): fix behavior of logging checkboxes (#571) *by pheowl* ([`619fa67`](https://github.com/andythomas/matr1x/commit/619fa6742a0eb52b2e5bb7ca768878c95e5d0dc4))

* fix(control-subsystem): fix behavior of logging checkboxes *by pheowl* ([`619fa67`](https://github.com/andythomas/matr1x/commit/619fa6742a0eb52b2e5bb7ca768878c95e5d0dc4))

* fix(matrix-script): use defined execution path for scripts (#559) *by Dominik Kriegner* ([`ac35f65`](https://github.com/andythomas/matr1x/commit/ac35f65b38c2608818a9251ebf5e42735668050e))

* fix(matrix-script): use defined execution path for scripts *by Dominik Kriegner* ([`ac35f65`](https://github.com/andythomas/matr1x/commit/ac35f65b38c2608818a9251ebf5e42735668050e))

* fix(matrix-script): make the new script communication work on windows (#558) *by Dominik Kriegner* ([`a040eab`](https://github.com/andythomas/matr1x/commit/a040eab2775e11d3fc5ff26662adeb3d90da5754))

* fix(matrix-script): make the new script communication work on windows *by Dominik Kriegner* ([`a040eab`](https://github.com/andythomas/matr1x/commit/a040eab2775e11d3fc5ff26662adeb3d90da5754))

* fix(GUI): make gui on windows use fusion style (#555) *by Dominik Kriegner* ([`fb539db`](https://github.com/andythomas/matr1x/commit/fb539db2c1eef9a086df7e20ebf17064d8dd0a46))

* fix(GUI): make gui on windows use fusion style *by Dominik Kriegner* ([`fb539db`](https://github.com/andythomas/matr1x/commit/fb539db2c1eef9a086df7e20ebf17064d8dd0a46))

* fix(GUI): make PyQt5 imports work (#560) *by Dominik Kriegner* ([`674a6c5`](https://github.com/andythomas/matr1x/commit/674a6c533d33bff37f29838211f17ea913c1b2ed))

* fix(matrix_script,-util): fix erroneous output to stdout (#545) *by pheowl* ([`0b846f6`](https://github.com/andythomas/matr1x/commit/0b846f6380b689c87a35f45ac0ca05e9f7167be5))

* fix(matrix_script,-util): fix erroneous output to stdout *by pheowl* ([`0b846f6`](https://github.com/andythomas/matr1x/commit/0b846f6380b689c87a35f45ac0ca05e9f7167be5))

* fix(matrix_script,-util): use stdout routed via socket for all communication from thread *by pheowl* ([`0b846f6`](https://github.com/andythomas/matr1x/commit/0b846f6380b689c87a35f45ac0ca05e9f7167be5))

* fix(util): fix CI error *by pheowl* ([`0b846f6`](https://github.com/andythomas/matr1x/commit/0b846f6380b689c87a35f45ac0ca05e9f7167be5))

* fix(matrix_script,-util): clean up code, add comment, remove clutter from debugging *by pheowl* ([`0b846f6`](https://github.com/andythomas/matr1x/commit/0b846f6380b689c87a35f45ac0ca05e9f7167be5))

* fix(util): fix errors discovered by pytest *by pheowl* ([`b9b808f`](https://github.com/andythomas/matr1x/commit/b9b808f4f78d3114feb0eb851b3066746289df32))

* fix(system_dummy_hdf5): remove "f16" type that seems to be problematic for windows and mac *by pheowl* ([`b9b808f`](https://github.com/andythomas/matr1x/commit/b9b808f4f78d3114feb0eb851b3066746289df32))

* fix: remove the use of a function which will be removed in numpy2.0 (#542) *by Dominik Kriegner* ([`38f20cd`](https://github.com/andythomas/matr1x/commit/38f20cdd20c8c50a5b9405c24cc505bbe58314ce))

* fix(util): allow for running the script without being connected to the gui *by pheowl* ([`8b956bf`](https://github.com/andythomas/matr1x/commit/8b956bf610cdfc84b5f7ae0616330e6cc19d935c))

* fix(matrix_script,-util): address comments by @dkriegner, fixes behavior of \r, introduces \0 as message terminator *by pheowl* ([`8b956bf`](https://github.com/andythomas/matr1x/commit/8b956bf610cdfc84b5f7ae0616330e6cc19d935c))

* fix(matrix_script,-util): make communications wait for message termination, still times out occasionally, produces image artifacts in the gui for very long strings (long meaning >1M symbols) *by pheowl* ([`8b956bf`](https://github.com/andythomas/matr1x/commit/8b956bf610cdfc84b5f7ae0616330e6cc19d935c))

* fix(matrix_script,-util): document timeout, gracefully handle long texts in QTextEdit status_preview *by pheowl* ([`8b956bf`](https://github.com/andythomas/matr1x/commit/8b956bf610cdfc84b5f7ae0616330e6cc19d935c))

* fix(matrix_script): fix behavior of editor when using " or ' with sel… (#521) *by pheowl* ([`1ff7d34`](https://github.com/andythomas/matr1x/commit/1ff7d348b4a29d5f0f747eb952eb7d68809a3e3c))

* fix(matrix_script): fix behavior of editor when using " or ' with selected text, should now resemble the behavior of VScode. Closes issue #512 *by pheowl* ([`1ff7d34`](https://github.com/andythomas/matr1x/commit/1ff7d348b4a29d5f0f747eb952eb7d68809a3e3c))

* fix(matrix_script): fix behavior of toggle commenting with selection by triple-click *by pheowl* ([`1ff7d34`](https://github.com/andythomas/matr1x/commit/1ff7d348b4a29d5f0f747eb952eb7d68809a3e3c))

* fix(matrix_preview): fix auto update not reloading the plot, implements update of file information on reload, closes #514 (#520) *by pheowl* ([`c6b9304`](https://github.com/andythomas/matr1x/commit/c6b9304f3c6e3e8d04d31a77104ac0f108195a66))

* fix(different-gui-scripts): address changes in issue #502, path handling aligned on previous selected path *by pheowl* ([`c550d8d`](https://github.com/andythomas/matr1x/commit/c550d8d37f4928ce7f26e29614836402c4877a18))

* fix(matrix_preview.py): closes #408 , also update all subplots on manual interaction *by pheowl* ([`c550d8d`](https://github.com/andythomas/matr1x/commit/c550d8d37f4928ce7f26e29614836402c4877a18))

* fix(matrix_script.py-and-util.py): address comments by @dkriegner, update hints to reflect current state *by pheowl* ([`c550d8d`](https://github.com/andythomas/matr1x/commit/c550d8d37f4928ce7f26e29614836402c4877a18))

* fix(matrix_script-and-util): make breakpoint interrupt always, make input resistant to multiple sends and make it properly receive only single command *by pheowl* ([`c550d8d`](https://github.com/andythomas/matr1x/commit/c550d8d37f4928ce7f26e29614836402c4877a18))

* fix(different-gui-scripts): address changes in issue #502, path handl… (#506) *by pheowl* ([`904922f`](https://github.com/andythomas/matr1x/commit/904922fa60490fd2055a54ffe5304e8277016241))

* fix(different-gui-scripts): address changes in issue #502, path handling aligned on previous selected path *by pheowl* ([`904922f`](https://github.com/andythomas/matr1x/commit/904922fa60490fd2055a54ffe5304e8277016241))

* fix(matrix_preview.py): closes #408 , also update all subplots on manual interaction (#507) *by pheowl* ([`904922f`](https://github.com/andythomas/matr1x/commit/904922fa60490fd2055a54ffe5304e8277016241))

* fix(matrix_script): add proper handling of add system also for matrix_script *by pheowl* ([`904922f`](https://github.com/andythomas/matr1x/commit/904922fa60490fd2055a54ffe5304e8277016241))

* fix(PyQt5): add deprecation warnings for PyQt5 use (#486) *by Dominik Kriegner* ([`177ac56`](https://github.com/andythomas/matr1x/commit/177ac562e1ff484edbb3a98e48e0622c9898c642))

* fix(PyQt5): add deprecation warnings for PyQt5 use *by Dominik Kriegner* ([`177ac56`](https://github.com/andythomas/matr1x/commit/177ac562e1ff484edbb3a98e48e0622c9898c642))

* fix(pico.py): fix typos, wrong code and linter-induced errors *by pheowl* ([`9731f5c`](https://github.com/andythomas/matr1x/commit/9731f5c8403144b9032cd08e9cd976a025491e00))

* fix(pico): some more linter fixes *by pheowl* ([`9731f5c`](https://github.com/andythomas/matr1x/commit/9731f5c8403144b9032cd08e9cd976a025491e00))

* fix(pyproject.toml): fix missing autopep8 dependency (#488) *by pheowl* ([`3682a96`](https://github.com/andythomas/matr1x/commit/3682a96257e7e3de4fdd3cc8edb3371754b57fa0))

* fix(matrix_script): add new dependency to readme, make style more consistent, remove leftover code *by pheowl* ([`83f0f17`](https://github.com/andythomas/matr1x/commit/83f0f17421d415ec7ec28b7b40ac49f33ded8a30))

* fix(matrix-script): add creator/identifier keyword to autocompletion *by pheowl* ([`83f0f17`](https://github.com/andythomas/matr1x/commit/83f0f17421d415ec7ec28b7b40ac49f33ded8a30))

* fix(matrix_script.py): make toggle comment function as in vs code, allow block commenting *by pheowl* ([`83f0f17`](https://github.com/andythomas/matr1x/commit/83f0f17421d415ec7ec28b7b40ac49f33ded8a30))

* fix(matrix_script.py): make toggle comment work as proposed by @dkriegner *by pheowl* ([`83f0f17`](https://github.com/andythomas/matr1x/commit/83f0f17421d415ec7ec28b7b40ac49f33ded8a30))

* fix(matrix_script): fix open issues with commenting, add help button for editor commands *by pheowl* ([`83f0f17`](https://github.com/andythomas/matr1x/commit/83f0f17421d415ec7ec28b7b40ac49f33ded8a30))

* fix(matrix-script): fix problem if linter has no message_args *by pheowl* ([`83f0f17`](https://github.com/andythomas/matr1x/commit/83f0f17421d415ec7ec28b7b40ac49f33ded8a30))

* fix(matrix-script): move autopep8 import to the top *by pheowl* ([`83f0f17`](https://github.com/andythomas/matr1x/commit/83f0f17421d415ec7ec28b7b40ac49f33ded8a30))

* fix(matrix_script): fix remaining comments by @dkriegner *by pheowl* ([`83f0f17`](https://github.com/andythomas/matr1x/commit/83f0f17421d415ec7ec28b7b40ac49f33ded8a30))

* fix(matrix-script): improved commenting *by pheowl* ([`83f0f17`](https://github.com/andythomas/matr1x/commit/83f0f17421d415ec7ec28b7b40ac49f33ded8a30))

* fix(matrix-script): further added comments and removed some unneccesary lines *by pheowl* ([`83f0f17`](https://github.com/andythomas/matr1x/commit/83f0f17421d415ec7ec28b7b40ac49f33ded8a30))

* fix(eval): change loadmatrix to use locking parameter in h5py opening… (#452) *by pheowl* ([`648745f`](https://github.com/andythomas/matr1x/commit/648745fbe89548b5b35f62cd9b3e0624881778c4))

* fix(eval): change loadmatrix to use locking parameter in h5py opening instead of trying to assert the global variable (already known issues with this import...) *by pheowl* ([`648745f`](https://github.com/andythomas/matr1x/commit/648745fbe89548b5b35f62cd9b3e0624881778c4))

* fix(pyproject.toml): add missing dependency 'requests' *by pheowl* ([`648745f`](https://github.com/andythomas/matr1x/commit/648745fbe89548b5b35f62cd9b3e0624881778c4))

* fix(desktop-integration): also link ma6 files to matrix-preview *by pheowl* ([`19fd0e6`](https://github.com/andythomas/matr1x/commit/19fd0e645388fab7809b4656a32946831dce8c6a))

* fix(owis): refactor code and improve documentation *by pheowl* ([`ff9a7d5`](https://github.com/andythomas/matr1x/commit/ff9a7d519e7a8f90daec89c1a1dd95ecf049d012))

* fix(owis): address linter comments *by pheowl* ([`ff9a7d5`](https://github.com/andythomas/matr1x/commit/ff9a7d519e7a8f90daec89c1a1dd95ecf049d012))

* fix(INSTALL): use correct python for venv *by Dominik Kriegner* ([`549f9e1`](https://github.com/andythomas/matr1x/commit/549f9e1bf205ce2dad22f67c2e0aed04c7ef4cdf))

* fix(INSTALL): regex requires raw string in 3.12 *by Dominik Kriegner* ([`549f9e1`](https://github.com/andythomas/matr1x/commit/549f9e1bf205ce2dad22f67c2e0aed04c7ef4cdf))

* fix(GUI): set AppUserModelID in control_aja *by Dominik Kriegner* ([`b70c507`](https://github.com/andythomas/matr1x/commit/b70c507c021390c2a798737220898a5c3ac4f24c))

* fix(ptarmigan): more informative button label *by Dominik Kriegner* ([`b70c507`](https://github.com/andythomas/matr1x/commit/b70c507c021390c2a798737220898a5c3ac4f24c))

* fix(AJA): easier interaction with vacuum gauge switch *by Dominik Kriegner* ([`b70c507`](https://github.com/andythomas/matr1x/commit/b70c507c021390c2a798737220898a5c3ac4f24c))

* fix(controlGUI): better restore features from saved config *by Dominik Kriegner* ([`b70c507`](https://github.com/andythomas/matr1x/commit/b70c507c021390c2a798737220898a5c3ac4f24c))

* fix(gui_util.py,-eval.py): fixes two bugs, one regarding legacy files (ma6), one regarding changed definition in qt (#450) *by pheowl* ([`8a4eb8b`](https://github.com/andythomas/matr1x/commit/8a4eb8b1aa0c43dcafc1113506fcc7e7dfe8b8c0))

* fix(control_sane.py): bring control for sane setup (xyz stage) back to working condition *by pheowl* ([`ec93294`](https://github.com/andythomas/matr1x/commit/ec93294ea356b89abb95a1785484ce04567f4693))

* fix(control_sane-and-thorlabs-driver): migrate the config file into the control GUI, migrate control UI to new format *by pheowl* ([`ec93294`](https://github.com/andythomas/matr1x/commit/ec93294ea356b89abb95a1785484ce04567f4693))

* fix(control_sane): fix linter error *by pheowl* ([`ec93294`](https://github.com/andythomas/matr1x/commit/ec93294ea356b89abb95a1785484ce04567f4693))

* fix(visadevice.py): changing docstring to represent the modified behavior of the visadevice write function *by pheowl* ([`ec93294`](https://github.com/andythomas/matr1x/commit/ec93294ea356b89abb95a1785484ce04567f4693))

* fix(pico.py): fix typos, wrong code and linter-induced errors *by pheowl* ([`cd466cf`](https://github.com/andythomas/matr1x/commit/cd466cfd6a182ed22bd2a47f4fa9529a5cedce47))

* fix(pico): some more linter fixes *by pheowl* ([`cd466cf`](https://github.com/andythomas/matr1x/commit/cd466cfd6a182ed22bd2a47f4fa9529a5cedce47))

* fix(matrix_preview): workaround that selects each subplot upon file change to force update, fixes issue #408 *by pheowl* ([`3fe2ad9`](https://github.com/andythomas/matr1x/commit/3fe2ad986eb9f3af9bd3c6ea5dbd530a590ca679))

* fix(matrix-gui): force sweep generator back to normal if it is minimized and the sweep generator button is pressed *by pheowl* ([`3fe2ad9`](https://github.com/andythomas/matr1x/commit/3fe2ad986eb9f3af9bd3c6ea5dbd530a590ca679))

* fix(GUI): remove desktop file extenstion *by Dominik Kriegner* ([`130006d`](https://github.com/andythomas/matr1x/commit/130006dad35eeea6f1bbe8a5c79c34a71f2ed924))

* fix(system.py): fixes issue that multi column parameters cannot use h… (#419) *by pheowl* ([`bab038b`](https://github.com/andythomas/matr1x/commit/bab038b17c10039a7561a8dfff0183c0d56b4036))

* fix(system.py): fixes issue that multi column parameters cannot use higher dimension in h5 files *by pheowl* ([`bab038b`](https://github.com/andythomas/matr1x/commit/bab038b17c10039a7561a8dfff0183c0d56b4036))

* fix(test_matrix.py): fix test to match with new system_dummy_hdf5 *by pheowl* ([`bab038b`](https://github.com/andythomas/matr1x/commit/bab038b17c10039a7561a8dfff0183c0d56b4036))

* fix(matrix_preview): workaround that selects each subplot upon file change to force update, fixes issue #408 (#417) *by pheowl* ([`b636108`](https://github.com/andythomas/matr1x/commit/b63610848ae4695d823196d5043150d2c8ad078e))

* fix(matrix_preview): allow reloading the files in combo box dynamical… (#415) *by pheowl* ([`f8a124c`](https://github.com/andythomas/matr1x/commit/f8a124c152487975d615fb350006904aa89759de))

* fix(matrix_preview): allow reloading the files in combo box dynamically, fixes #409 *by pheowl* ([`f8a124c`](https://github.com/andythomas/matr1x/commit/f8a124c152487975d615fb350006904aa89759de))

* fix(loadmatrix): enable loading boolean types *by Dominik Kriegner* ([`dbf3d67`](https://github.com/andythomas/matr1x/commit/dbf3d67cdc0c0addf812a0348f901e40ea15e51f))

* fix(VisaDevice): do not close manager *by Dominik Kriegner* ([`18e7066`](https://github.com/andythomas/matr1x/commit/18e70668a2086854a5b461191ca2db994a780d36))

* fix(controlGUI): better restore features from saved config *by Dominik Kriegner* ([`cdb6215`](https://github.com/andythomas/matr1x/commit/cdb6215baa1b805e1f931ca815c3087e857786ee))

* fix(VisaDevice,Lakeshore): (re)add VisaDevice.open (#388) *by Dominik Kriegner* ([`48dcd39`](https://github.com/andythomas/matr1x/commit/48dcd39fab34e408d9657774fe362a0c13211d22))

* fix(VisaDevice,Lakeshore): (re)add VisaDevice.open *by Dominik Kriegner* ([`48dcd39`](https://github.com/andythomas/matr1x/commit/48dcd39fab34e408d9657774fe362a0c13211d22))

* fix(PyQt5): make custom qwidgets work with PyQt5 *by Dominik Kriegner* ([`33c5b88`](https://github.com/andythomas/matr1x/commit/33c5b888691470cd80d0276d5b42f04d5b50f358))

* fix(controlGUI): avoid undocking of last widget *by Dominik Kriegner* ([`33c5b88`](https://github.com/andythomas/matr1x/commit/33c5b888691470cd80d0276d5b42f04d5b50f358))

* fix(copyright): update copyright year *by Dominik Kriegner* ([`43f3fef`](https://github.com/andythomas/matr1x/commit/43f3fefd7d4801936e29d9be6c16f00ac1ce7bb5))

* fix(VisaDevice): fix code using VisaDevice.connection *by Dominik Kriegner* ([`1cc075d`](https://github.com/andythomas/matr1x/commit/1cc075d43953e56f6b515445336af8a83a0d4b41))

* fix(sweep_generator): PyQt6 fix of reading checkbox state (#366) *by Dominik Kriegner* ([`68cb5b8`](https://github.com/andythomas/matr1x/commit/68cb5b8d5d156509931cdce5360ede0d954ec1e3))

* fix(sweep_generator): PyQt6 fix of reading checkbox state *by Dominik Kriegner* ([`68cb5b8`](https://github.com/andythomas/matr1x/commit/68cb5b8d5d156509931cdce5360ede0d954ec1e3))

* fix(icons): make icons be used correctly by Gnome-Wayland *by Dominik Kriegner* ([`c2adef4`](https://github.com/andythomas/matr1x/commit/c2adef41f27ffa91e39489076d73bccd27d1775a))

* fix(controlGUI): use QSpinBox for log interval *by Dominik Kriegner* ([`144588c`](https://github.com/andythomas/matr1x/commit/144588cec8eb1124f94173525c9fecd3ed740bf4))

* fix(controlGUI): better collapsibleBox and reset log config button *by Dominik Kriegner* ([`144588c`](https://github.com/andythomas/matr1x/commit/144588cec8eb1124f94173525c9fecd3ed740bf4))

* fix(PyQt6): adjust new code for changes in PyQt6 *by Dominik Kriegner* ([`144588c`](https://github.com/andythomas/matr1x/commit/144588cec8eb1124f94173525c9fecd3ed740bf4))

* fix(controlGUI): use inclusive language variable name *by Dominik Kriegner* ([`144588c`](https://github.com/andythomas/matr1x/commit/144588cec8eb1124f94173525c9fecd3ed740bf4))

* fix(controlGUI): correct deactivation of the GUI upon error *by Dominik Kriegner* ([`144588c`](https://github.com/andythomas/matr1x/commit/144588cec8eb1124f94173525c9fecd3ed740bf4))

* fix(controlwindow): minor bug fixes to the control window, added button for testing errors, still broken *by Dominik Kriegner* ([`144588c`](https://github.com/andythomas/matr1x/commit/144588cec8eb1124f94173525c9fecd3ed740bf4))

* fix(controlwindow): also disable other windows in row *by Dominik Kriegner* ([`144588c`](https://github.com/andythomas/matr1x/commit/144588cec8eb1124f94173525c9fecd3ed740bf4))

* fix(ControlWindow): disable Qt font cache to avoid a segfault *by Dominik Kriegner* ([`144588c`](https://github.com/andythomas/matr1x/commit/144588cec8eb1124f94173525c9fecd3ed740bf4))

* fix(controlGUI): make init of var more flexible #341 (#345) *by Dominik Kriegner* ([`f07b738`](https://github.com/andythomas/matr1x/commit/f07b738be6e0f2a25040e77e0700f13380983fce))

* fix(controlGUI): make init of var objects behave correctly *by Dominik Kriegner* ([`f07b738`](https://github.com/andythomas/matr1x/commit/f07b738be6e0f2a25040e77e0700f13380983fce))

* fix(control_blue15): modernize control GUI and fix inits related to #341 *by Dominik Kriegner* ([`f07b738`](https://github.com/andythomas/matr1x/commit/f07b738be6e0f2a25040e77e0700f13380983fce))

* fix(controlGUI): fix all control GUIs with respect to #341 *by Dominik Kriegner* ([`f07b738`](https://github.com/andythomas/matr1x/commit/f07b738be6e0f2a25040e77e0700f13380983fce))

* fix(dependencies): limit pyvisa-py dependency on Python <3.8 (#343) *by Dominik Kriegner* ([`491425f`](https://github.com/andythomas/matr1x/commit/491425fdcdc5467a81a436d55948d886c8b2a250))

* fix(controlGUI): more error checking and flexibility in GUI creation (#335) *by Dominik Kriegner* ([`de86fb2`](https://github.com/andythomas/matr1x/commit/de86fb2e4929c8272f7f8bd3c989c9ecf3f8fba8))

* fix(matrix_script): fix calling of refactored code *by Dominik Kriegner* ([`9bb1c77`](https://github.com/andythomas/matr1x/commit/9bb1c77f87c95b5752554def7ef4940e92bd0ea9))

* fix(matrix-preview): limit maximum window size *by Dominik Kriegner* ([`748affb`](https://github.com/andythomas/matr1x/commit/748affbbf5eced079f076bb0f2d87bf8b23dae86))

* fix(matrix-preview): opening of matrix-preview from matrix-gui *by Dominik Kriegner* ([`81707c5`](https://github.com/andythomas/matr1x/commit/81707c56204dab01ad9c99f587fa28c3c65a315a))

* fix(matrix_preview): Update all plots in graph on update, fixes issue #297 (#318) *by pheowl* ([`23499cc`](https://github.com/andythomas/matr1x/commit/23499ccab609c2859251e83130827348d4eb8a2e))

* fix(ControlGUI): avoid triggering value casting *by Dominik Kriegner* ([`3578979`](https://github.com/andythomas/matr1x/commit/357897908f33a82ed875dda8235318af3c34cb43))

* fix(INSTALL): set executable bits *by Dominik Kriegner* ([`5319d77`](https://github.com/andythomas/matr1x/commit/5319d77770820669140141338fc0a46069958f5b))

* fix(matrix_preview): fix bug raised by @andythomas on destruction of the thread object *by Dominik Kriegner* ([`5319d77`](https://github.com/andythomas/matr1x/commit/5319d77770820669140141338fc0a46069958f5b))

* fix(matrix_preview): Allow double click loading on a Mac *by Dominik Kriegner* ([`5319d77`](https://github.com/andythomas/matr1x/commit/5319d77770820669140141338fc0a46069958f5b))

* fix(matrix_preview): explain mac specific delay *by Dominik Kriegner* ([`5319d77`](https://github.com/andythomas/matr1x/commit/5319d77770820669140141338fc0a46069958f5b))

* fix(ptarmigan): more informative button label *by Dominik Kriegner* ([`844f83f`](https://github.com/andythomas/matr1x/commit/844f83f8f14928a1751663f169fa69246b74cfd1))

* fix(underscore): replace underscore by dash where possible *by Dominik Kriegner* ([`12d44c4`](https://github.com/andythomas/matr1x/commit/12d44c4f2fa1f881186e2a3ec6d85a087ce2e741))

* fix(INSTALL-GUI): make fallback toml parser work as intended *by Dominik Kriegner* ([`12d44c4`](https://github.com/andythomas/matr1x/commit/12d44c4f2fa1f881186e2a3ec6d85a087ce2e741))

* fix(INSTALL.ps1): remove stray files of Desktop integration in windows installer *by Dominik Kriegner* ([`12d44c4`](https://github.com/andythomas/matr1x/commit/12d44c4f2fa1f881186e2a3ec6d85a087ce2e741))

* fix(INSTALL.ps1): add qt5/qt6 support in Windows installer *by Dominik Kriegner* ([`12d44c4`](https://github.com/andythomas/matr1x/commit/12d44c4f2fa1f881186e2a3ec6d85a087ce2e741))

* fix(underscore): replace more spurious underscores *by Dominik Kriegner* ([`12d44c4`](https://github.com/andythomas/matr1x/commit/12d44c4f2fa1f881186e2a3ec6d85a087ce2e741))

* fix(matrix_GUI): properly catch different exception types *by baduraan* ([`e499fe1`](https://github.com/andythomas/matr1x/commit/e499fe16441b16c64cf520c7e171caa52c53c597))

* fix(Qt): control dummy works with Qt5 and Qt6 *by Andy Thomas* ([`9a47d55`](https://github.com/andythomas/matr1x/commit/9a47d5544133fd690e59678bfb6276675195ef2d))

* fix(matrix_script): fix issues with code highlighting *by pheowl* ([`f1c5866`](https://github.com/andythomas/matr1x/commit/f1c5866161ead3da555f6fb67b39dd69bf639bbd))

* fix(Qt6): Allow installation via INSTALL script *by Andy Thomas* ([`a4010ff`](https://github.com/andythomas/matr1x/commit/a4010ffe711e13e4bcd280a6140648e77f386c84))

* fix(Qt6): fixed sweep_generator *by Andy Thomas* ([`0d505a0`](https://github.com/andythomas/matr1x/commit/0d505a0aa59bdb4110a34071ee4253ef6b61c046))

* fix(icons): Make icons work in Linux/Gnome (#299) *by Dominik Kriegner* ([`9553816`](https://github.com/andythomas/matr1x/commit/9553816757bf687498b51cf6fddc65c7b26acb30))

* fix(icons): install icons for ma7 files correctly in linux/Gnome *by Dominik Kriegner* ([`9553816`](https://github.com/andythomas/matr1x/commit/9553816757bf687498b51cf6fddc65c7b26acb30))

### Build system

* build(INSTALL): change windows scroll functionality in install_dialog *by Dominik Kriegner* ([`b70c507`](https://github.com/andythomas/matr1x/commit/b70c507c021390c2a798737220898a5c3ac4f24c))

* build(INSTALL): clean up trailing comma in install.cfg *by Dominik Kriegner* ([`b70c507`](https://github.com/andythomas/matr1x/commit/b70c507c021390c2a798737220898a5c3ac4f24c))

* build(INSTALL): update windows installer to use GUI *by Dominik Kriegner* ([`b70c507`](https://github.com/andythomas/matr1x/commit/b70c507c021390c2a798737220898a5c3ac4f24c))

* build(UNINSTALL): add uninstaller for windows *by Dominik Kriegner* ([`b70c507`](https://github.com/andythomas/matr1x/commit/b70c507c021390c2a798737220898a5c3ac4f24c))

* build((installGUI)): improve package detection for install_dialog *by Dominik Kriegner* ([`12d44c4`](https://github.com/andythomas/matr1x/commit/12d44c4f2fa1f881186e2a3ec6d85a087ce2e741))

* build(controlGUI): use dash version of the executable if available *by Dominik Kriegner* ([`12d44c4`](https://github.com/andythomas/matr1x/commit/12d44c4f2fa1f881186e2a3ec6d85a087ce2e741))

* build(INSTALL): make install_dialog fetch info about executables from toml file *by Dominik Kriegner* ([`12d44c4`](https://github.com/andythomas/matr1x/commit/12d44c4f2fa1f881186e2a3ec6d85a087ce2e741))

* build(UNINSTALL): speed up uninstall script *by Dominik Kriegner* ([`12d44c4`](https://github.com/andythomas/matr1x/commit/12d44c4f2fa1f881186e2a3ec6d85a087ce2e741))

* build(INSTALL): add pyqt5/pyqt6 switch in the installer *by Dominik Kriegner* ([`7db6a12`](https://github.com/andythomas/matr1x/commit/7db6a12d94ee76e6a3c5e7a56057099b5a432f38))

### Code style

* style: automatically fix linter warnings using Ruff (#681) *by Dominik Kriegner* ([`5220478`](https://github.com/andythomas/matr1x/commit/5220478886f20c1def301158f29c4a8f77a0e2ea))

* style: automatically fix linter warnings using Ruff *by Dominik Kriegner* ([`5220478`](https://github.com/andythomas/matr1x/commit/5220478886f20c1def301158f29c4a8f77a0e2ea))

* style: break long lines of code *by Dominik Kriegner* ([`5220478`](https://github.com/andythomas/matr1x/commit/5220478886f20c1def301158f29c4a8f77a0e2ea))

* style: remove executable flag from file permission *by Dominik Kriegner* ([`5220478`](https://github.com/andythomas/matr1x/commit/5220478886f20c1def301158f29c4a8f77a0e2ea))

* style(copyright): update copyright year *by Luise Siegl* ([`53fb1b8`](https://github.com/andythomas/matr1x/commit/53fb1b87ed4f597d3e6c5f4166d3c6e43b07b6df))

* style(templates): copy for later modification *by Andy Thomas* ([`6c9dff3`](https://github.com/andythomas/matr1x/commit/6c9dff3b3cb63a80dfbffc5884d62ae58dbb08d1))

* style: increase the font size of explanation *by Andy Thomas* ([`6c9dff3`](https://github.com/andythomas/matr1x/commit/6c9dff3b3cb63a80dfbffc5884d62ae58dbb08d1))

* style: reformat the error message *by Andy Thomas* ([`6c9dff3`](https://github.com/andythomas/matr1x/commit/6c9dff3b3cb63a80dfbffc5884d62ae58dbb08d1))

* style: more descriptive step names *by Andy Thomas* ([`6c9dff3`](https://github.com/andythomas/matr1x/commit/6c9dff3b3cb63a80dfbffc5884d62ae58dbb08d1))

* style(control-util-and-window): small cosmetic changes to the code *by Dominik Kriegner* ([`144588c`](https://github.com/andythomas/matr1x/commit/144588cec8eb1124f94173525c9fecd3ed740bf4))

* style(underscores): adress comments from code review in PR *by Dominik Kriegner* ([`12d44c4`](https://github.com/andythomas/matr1x/commit/12d44c4f2fa1f881186e2a3ec6d85a087ce2e741))

### Documentation

* docs: update links to external code sources, add license statements (#646) *by Dominik Kriegner* ([`2aaace5`](https://github.com/andythomas/matr1x/commit/2aaace583287cd8c457ca44ab239f778f09f48ac))

* docs: update links to external code sources, add license statements *by Dominik Kriegner* ([`2aaace5`](https://github.com/andythomas/matr1x/commit/2aaace583287cd8c457ca44ab239f778f09f48ac))

* docs: more precise info about eric7 code *by Dominik Kriegner* ([`2aaace5`](https://github.com/andythomas/matr1x/commit/2aaace583287cd8c457ca44ab239f778f09f48ac))

* docs: add GPL-3-or-later license info *by Dominik Kriegner* ([`2aaace5`](https://github.com/andythomas/matr1x/commit/2aaace583287cd8c457ca44ab239f778f09f48ac))

* docs(constructLayout): update docstring of constructLayout *by Dominik Kriegner* ([`f07b738`](https://github.com/andythomas/matr1x/commit/f07b738be6e0f2a25040e77e0700f13380983fce))

### Features

* feat(matrix-script): graphical user input and yes/no questions (#701) *by Dominik Kriegner* ([`b71a5ce`](https://github.com/andythomas/matr1x/commit/b71a5ceca4eb7d5e9bf2fbc9744dcbdf97268941))

* feat(matrix-script): graphical user input and yes/no questions *by Dominik Kriegner* ([`b71a5ce`](https://github.com/andythomas/matr1x/commit/b71a5ceca4eb7d5e9bf2fbc9744dcbdf97268941))

* feat: major update of FMR setup from UKON (EMMA) (#474) *by Luise Siegl* ([`53fb1b8`](https://github.com/andythomas/matr1x/commit/53fb1b87ed4f597d3e6c5f4166d3c6e43b07b6df))

* feat(gui_util): implement custom scaling for time axis if name is "timeUTC" (#647) *by pheowl* ([`f27c23f`](https://github.com/andythomas/matr1x/commit/f27c23fbfa2cae27638c3ae85710741df4797969))

* feat(gui_util): implement custom scaling for time axis if name is "timeUTC" *by pheowl* ([`f27c23f`](https://github.com/andythomas/matr1x/commit/f27c23fbfa2cae27638c3ae85710741df4797969))

* feat(matrix): add a quiet mode (-q) to matrix CLI (#634) *by Dominik Kriegner* ([`6ae7205`](https://github.com/andythomas/matr1x/commit/6ae720504157b59a62e0f14d46c7b7b928d9388d))

* feat(matrix): add a quiet mode (-q) to matrix CLI *by Dominik Kriegner* ([`6ae7205`](https://github.com/andythomas/matr1x/commit/6ae720504157b59a62e0f14d46c7b7b928d9388d))

* feat(controlGUI): possibility to enable logging on startup (#605) *by Dominik Kriegner* ([`6d4aacd`](https://github.com/andythomas/matr1x/commit/6d4aacd868f846e236a8c2ace37a2e401f16d3b3))

* feat(controlGUI): add possibility to automatically enable logging *by Dominik Kriegner* ([`6d4aacd`](https://github.com/andythomas/matr1x/commit/6d4aacd868f846e236a8c2ace37a2e401f16d3b3))

* feat(cryovac-and-control_ln2cryo): add cryovac TIC500 controller, imp… (#596) *by pheowl* ([`bc668b6`](https://github.com/andythomas/matr1x/commit/bc668b68246c5869e62175f72036520c891b39ad))

* feat(cryovac-and-control_ln2cryo): add cryovac TIC500 controller, implement GUI to control LN2 cryostat by cryovac *by pheowl* ([`bc668b6`](https://github.com/andythomas/matr1x/commit/bc668b68246c5869e62175f72036520c891b39ad))

* feat(sweep_generator): autogenerate system file symlinks for matr1x and ifwlib (#576) *by Dominik Kriegner* ([`ae51676`](https://github.com/andythomas/matr1x/commit/ae5167620349d9bc7b294353df4bb86817a72505))

* feat(system-files): quick access to system files via symlinks *by Dominik Kriegner* ([`ae51676`](https://github.com/andythomas/matr1x/commit/ae5167620349d9bc7b294353df4bb86817a72505))

* feat(matrix-script, System): allow access to Sytem methods and more flexible System parameters (#564) *by Dominik Kriegner* ([`5145e48`](https://github.com/andythomas/matr1x/commit/5145e4848d9f4e00f5e81e4967a72c37c6cd8eb7))

* feat(system.py): make grab_information also return system methods and parameters *by Dominik Kriegner* ([`5145e48`](https://github.com/andythomas/matr1x/commit/5145e4848d9f4e00f5e81e4967a72c37c6cd8eb7))

* feat(matrix_script): implement user query when matrix-script is closed with unsaved content (#570) *by pheowl* ([`1e89d78`](https://github.com/andythomas/matr1x/commit/1e89d78da0599002d7d49038a8ab5a8622c21fe4))

* feat(matrix_script): implement user query when matrix-script is closed with unsaved content *by pheowl* ([`1e89d78`](https://github.com/andythomas/matr1x/commit/1e89d78da0599002d7d49038a8ab5a8622c21fe4))

* feat(devices): add new gitDevice to track code status in datafiles (#579) *by Dominik Kriegner* ([`753eaec`](https://github.com/andythomas/matr1x/commit/753eaeca700d6fb0e0112df6ca21e63afedbffa1))

* feat(keithley.py): add possibility to perform hardware delta method w… (#573) *by pheowl* ([`1c73e17`](https://github.com/andythomas/matr1x/commit/1c73e17096da282186bec06027a21670746bbf68))

* feat(keithley.py): add possibility to perform hardware delta method with K6221/K2182 combo *by pheowl* ([`1c73e17`](https://github.com/andythomas/matr1x/commit/1c73e17096da282186bec06027a21670746bbf68))

* feat(control-GUI): enable hiding of selected items of a GUIDict (#556) *by Dominik Kriegner* ([`7c2d751`](https://github.com/andythomas/matr1x/commit/7c2d751fa5c7da69d5aa73fb58eee2c00bba49af))

* feat(control-GUI): enable hiding of selected items of a GUIDict *by Dominik Kriegner* ([`7c2d751`](https://github.com/andythomas/matr1x/commit/7c2d751fa5c7da69d5aa73fb58eee2c00bba49af))

* feat(util,-system-and-system_dummy_hdf5): implements compression in hdf5 format and makes the dtype the data is stored in transparent *by pheowl* ([`b9b808f`](https://github.com/andythomas/matr1x/commit/b9b808f4f78d3114feb0eb851b3066746289df32))

* feat(matrix_script): highlight currently executing line in editor (#535) *by pheowl* ([`8b956bf`](https://github.com/andythomas/matr1x/commit/8b956bf610cdfc84b5f7ae0616330e6cc19d935c))

* feat(matrix_script-and-util): first working version where currently executing line is highlighted in the editor of matrix-script *by pheowl* ([`8b956bf`](https://github.com/andythomas/matr1x/commit/8b956bf610cdfc84b5f7ae0616330e6cc19d935c))

* feat(matrix_preview,-gui_util): implements a meta data viewer (QDockW… (#522) *by pheowl* ([`f82a2df`](https://github.com/andythomas/matr1x/commit/f82a2dfe46fb5300be5a478607d813f82eee9c57))

* feat(matrix_preview,-gui_util): implements a meta data viewer (QDockWidget) to allow viewing meta data from the preview window *by pheowl* ([`f82a2df`](https://github.com/andythomas/matr1x/commit/f82a2dfe46fb5300be5a478607d813f82eee9c57))

* feat(matrix-script): add python input function and improved wait (#508) *by pheowl* ([`c550d8d`](https://github.com/andythomas/matr1x/commit/c550d8d37f4928ce7f26e29614836402c4877a18))

* feat(matrix_script): allows to use input function of python in matrix_script, closes #504 *by pheowl* ([`c550d8d`](https://github.com/andythomas/matr1x/commit/c550d8d37f4928ce7f26e29614836402c4877a18))

* feat(system_picovna,-pico): added new driver for picovna running with picovna5 software *by pheowl* ([`9731f5c`](https://github.com/andythomas/matr1x/commit/9731f5c8403144b9032cd08e9cd976a025491e00))

* feat(matrix_script): migrate to qscintilla for code editing, allows better indendation and at least basic autocomplete, initial testing looks promising *by pheowl* ([`83f0f17`](https://github.com/andythomas/matr1x/commit/83f0f17421d415ec7ec28b7b40ac49f33ded8a30))

* feat(matrix-script): add custom autocompletion to matrix-script *by pheowl* ([`83f0f17`](https://github.com/andythomas/matr1x/commit/83f0f17421d415ec7ec28b7b40ac49f33ded8a30))

* feat(matrix-script): drastically improve indendation handling by reusing some code from eric7-ide *by pheowl* ([`83f0f17`](https://github.com/andythomas/matr1x/commit/83f0f17421d415ec7ec28b7b40ac49f33ded8a30))

* feat(matrix-script): add block commenting functionality with ctrl+k *by pheowl* ([`83f0f17`](https://github.com/andythomas/matr1x/commit/83f0f17421d415ec7ec28b7b40ac49f33ded8a30))

* feat: include Mac desktop integration from main *by pheowl* ([`83f0f17`](https://github.com/andythomas/matr1x/commit/83f0f17421d415ec7ec28b7b40ac49f33ded8a30))

* feat(matrix_script): generate script offset dynamically to allow easier debugging, make linting possible with ctrl+l (relies on pyflakes), allow auto-formatting of code with autopep8 using ctrl+8 *by pheowl* ([`83f0f17`](https://github.com/andythomas/matr1x/commit/83f0f17421d415ec7ec28b7b40ac49f33ded8a30))

* feat(emails): improve sending emails + documentation (#482) *by Dominik Kriegner* ([`a800009`](https://github.com/andythomas/matr1x/commit/a800009779b308ae5b055788ee3654e47b58cb8f))

* feat(emails): improve sending emails + documentation *by Dominik Kriegner* ([`a800009`](https://github.com/andythomas/matr1x/commit/a800009779b308ae5b055788ee3654e47b58cb8f))

* feat(INSTALL): add *.matrix file to different INSTALL dialogs *by pheowl* ([`19fd0e6`](https://github.com/andythomas/matr1x/commit/19fd0e645388fab7809b4656a32946831dce8c6a))

* feat(matrix_script): adds possibility to load matrix-script with an initial script passed as command line parameter *by pheowl* ([`19fd0e6`](https://github.com/andythomas/matr1x/commit/19fd0e645388fab7809b4656a32946831dce8c6a))

* feat(matrix-script): prepare Mac Desktop integration *by pheowl* ([`19fd0e6`](https://github.com/andythomas/matr1x/commit/19fd0e645388fab7809b4656a32946831dce8c6a))

* feat(matrix-script): link *.matrix on a Mac *by pheowl* ([`19fd0e6`](https://github.com/andythomas/matr1x/commit/19fd0e645388fab7809b4656a32946831dce8c6a))

* feat(INSTALL): improved install dialog with support for virtual environments (#435) *by Dominik Kriegner* ([`549f9e1`](https://github.com/andythomas/matr1x/commit/549f9e1bf205ce2dad22f67c2e0aed04c7ef4cdf))

* feat(INSTALL): improved install dialog *by Dominik Kriegner* ([`549f9e1`](https://github.com/andythomas/matr1x/commit/549f9e1bf205ce2dad22f67c2e0aed04c7ef4cdf))

* feat(controlGUI): new control GUI for FZU sputtering system (#386) *by Dominik Kriegner* ([`b70c507`](https://github.com/andythomas/matr1x/commit/b70c507c021390c2a798737220898a5c3ac4f24c))

* feat(MKSVacuumGauge): a control GUI window for a vacuum gauge controller *by Dominik Kriegner* ([`b70c507`](https://github.com/andythomas/matr1x/commit/b70c507c021390c2a798737220898a5c3ac4f24c))

* feat(AJA): add gauge status to control GUI *by Dominik Kriegner* ([`b70c507`](https://github.com/andythomas/matr1x/commit/b70c507c021390c2a798737220898a5c3ac4f24c))

* feat(controlGUI): implement a ToggleButton for the immediate setting of a bool value *by Dominik Kriegner* ([`b70c507`](https://github.com/andythomas/matr1x/commit/b70c507c021390c2a798737220898a5c3ac4f24c))

* feat(ptarmigan): use toggle button for LHEF *by Dominik Kriegner* ([`b70c507`](https://github.com/andythomas/matr1x/commit/b70c507c021390c2a798737220898a5c3ac4f24c))

* feat(controlGUI): allow saving of Window state by Ctrl+s *by Dominik Kriegner* ([`b70c507`](https://github.com/andythomas/matr1x/commit/b70c507c021390c2a798737220898a5c3ac4f24c))

* feat(thorlabs.py): add thorlabs driver for bsc103 *by pheowl* ([`ec93294`](https://github.com/andythomas/matr1x/commit/ec93294ea356b89abb95a1785484ce04567f4693))

* feat(system_picovna,-pico): added new driver for picovna running with… (#427) *by pheowl* ([`cd466cf`](https://github.com/andythomas/matr1x/commit/cd466cfd6a182ed22bd2a47f4fa9529a5cedce47))

* feat(system_picovna,-pico): added new driver for picovna running with picovna5 software *by pheowl* ([`cd466cf`](https://github.com/andythomas/matr1x/commit/cd466cfd6a182ed22bd2a47f4fa9529a5cedce47))

* feat(system_dummygui): add readout for pressure parameter *by Dominik Kriegner* ([`146239a`](https://github.com/andythomas/matr1x/commit/146239a8408f5628418a482ee0a9ae39080dc51d))

* feat(controlGUI): allow saving of Window state by Ctrl+s *by Dominik Kriegner* ([`0301b76`](https://github.com/andythomas/matr1x/commit/0301b76594e73c6c03a2296532b596bbc00ca679))

* feat(controlGUI): enable disabling only one GuiDict upon an error (#392) *by Dominik Kriegner* ([`745f628`](https://github.com/andythomas/matr1x/commit/745f628f7ecf6c2a2afc82683fa8e5cdd8f5298d))

* feat(linear_trend): new utility function to study time series *by Dominik Kriegner* ([`745f628`](https://github.com/andythomas/matr1x/commit/745f628f7ecf6c2a2afc82683fa8e5cdd8f5298d))

* feat(controlGUI): make GuiDict deactivatable (#377) *by Dominik Kriegner* ([`33c5b88`](https://github.com/andythomas/matr1x/commit/33c5b888691470cd80d0276d5b42f04d5b50f358))

* feat(controlGUI): make GuiDict GUI deactivatable *by Dominik Kriegner* ([`33c5b88`](https://github.com/andythomas/matr1x/commit/33c5b888691470cd80d0276d5b42f04d5b50f358))

* feat(ControlGUI): Modular GUI redesign by a new GuiDict class (#359) *by Dominik Kriegner* ([`9c60b3f`](https://github.com/andythomas/matr1x/commit/9c60b3fa723989d1b05933ee44ad5b0885e015bb))

* feat(devices): add back Keysight B2961A power supply (#339) *by Dominik Kriegner* ([`76244de`](https://github.com/andythomas/matr1x/commit/76244de2775943efc7681e567851c8ba753af0bd))

* feat(devices): add back Keysight B2961A power supply *by Dominik Kriegner* ([`76244de`](https://github.com/andythomas/matr1x/commit/76244de2775943efc7681e567851c8ba753af0bd))

* feat(controlGI): support QDoubleSpinBox in controlGUIs #337) *by Dominik Kriegner* ([`e59da94`](https://github.com/andythomas/matr1x/commit/e59da9421c87dab1a9d6a4a57b124d4254f7e010))

* feat(controlGUI): add QSpinBox as control GUI element (#330) *by Dominik Kriegner* ([`30ee957`](https://github.com/andythomas/matr1x/commit/30ee957ff37edfdbec7f7b4df61f5cebd8b35ca9))

* feat(INSTALL): Make h5py optional *by Andy Thomas* ([`eb2c82a`](https://github.com/andythomas/matr1x/commit/eb2c82a4aea8942c83792b49a452313c60b015ab))

* feat(GUI): matrix-preview improvements to open files outside current folder (#312) *by Dominik Kriegner* ([`5319d77`](https://github.com/andythomas/matr1x/commit/5319d77770820669140141338fc0a46069958f5b))

* feat(matrix_preview): add open button and refactor code to first generate window *by Dominik Kriegner* ([`5319d77`](https://github.com/andythomas/matr1x/commit/5319d77770820669140141338fc0a46069958f5b))

* feat(matrix_preview): delayed file open dialog for macOS *by Dominik Kriegner* ([`5319d77`](https://github.com/andythomas/matr1x/commit/5319d77770820669140141338fc0a46069958f5b))

* feat(controlGUI): implement a ToggleButton for the immediate setting … (#286) *by Dominik Kriegner* ([`844f83f`](https://github.com/andythomas/matr1x/commit/844f83f8f14928a1751663f169fa69246b74cfd1))

* feat(controlGUI): implement a ToggleButton for the immediate setting of a bool value *by Dominik Kriegner* ([`844f83f`](https://github.com/andythomas/matr1x/commit/844f83f8f14928a1751663f169fa69246b74cfd1))

* feat(ptarmigan): use toggle button for LHEF *by Dominik Kriegner* ([`844f83f`](https://github.com/andythomas/matr1x/commit/844f83f8f14928a1751663f169fa69246b74cfd1))

* feat(INSTALL): core GUI scripts use dash instead of underscore (#307) *by Dominik Kriegner* ([`12d44c4`](https://github.com/andythomas/matr1x/commit/12d44c4f2fa1f881186e2a3ec6d85a087ce2e741))

* feat(Qt6): initial Qt6 port *by Andy Thomas* ([`4b082a4`](https://github.com/andythomas/matr1x/commit/4b082a456d354077c4554f3dce7d91c3003a6329))

### Unknown

* fix (matrix-script): use splitlines function (#624) *by Dominik Kriegner* ([`d4df067`](https://github.com/andythomas/matr1x/commit/d4df0677af9175991e0c47b21aea72ea4d9c5609))

* fix (SCPI-device): correct linux timing for dummy and control-GUI (#632) *by Dominik Kriegner* ([`4ddcb1f`](https://github.com/andythomas/matr1x/commit/4ddcb1f0cc0d2e584cec6a8ee36db886d3752806))

* fix (system): default filename now works also on MS Windows (#630) *by Dominik Kriegner* ([`46ddee5`](https://github.com/andythomas/matr1x/commit/46ddee5206cba005bed7eb877bad5eaa3286a908))

* fix (matrix-script): report line number correct for more functions (#626) *by Dominik Kriegner* ([`b1fe74d`](https://github.com/andythomas/matr1x/commit/b1fe74d88715dc351a464127ac84f79ae2da9d0e))

* add printout to what datafile one appends data *by Dominik Kriegner* ([`474abaa`](https://github.com/andythomas/matr1x/commit/474abaaad0fa082293db17ae6197958d6a75f094))

* simplify code and remove unreachable code path *by Dominik Kriegner* ([`dfd400b`](https://github.com/andythomas/matr1x/commit/dfd400b4a0eeb9daafbd024959e51f9178c943bf))

* AJA-growth system: new temperature controller and fixes (#612) *by Dominik Kriegner* ([`0922deb`](https://github.com/andythomas/matr1x/commit/0922deb3ac8e5cb1e0d08afbf7c05fafda116ed8))

* feat (matrix-GUI): add drag and drop of input files (#608) *by Dominik Kriegner* ([`7738bfa`](https://github.com/andythomas/matr1x/commit/7738bfa22d32b714397973bebea542bbb4a230f7))

* fix (system): make input files/scripts more transferable (#601) *by Dominik Kriegner* ([`e3d371b`](https://github.com/andythomas/matr1x/commit/e3d371b0aba5bcb0ed4d062ec35a1fd94850547e))

* fix (controlGUI): remove pyqtSlot where it is not allowed (#599) *by Dominik Kriegner* ([`265e90e`](https://github.com/andythomas/matr1x/commit/265e90ef868e47e274315f9a30a653e6a9a6d8c3))

* feat (GUI): Add drag and drop on Linux/Windows (#603) *by Dominik Kriegner* ([`8836947`](https://github.com/andythomas/matr1x/commit/8836947eccb212542f48f3e740a32e18e270c8f1))

* fix (AJA): convenience functions as system methods (#592) *by Dominik Kriegner* ([`fab3f4c`](https://github.com/andythomas/matr1x/commit/fab3f4c9237b7ea9127f5ddf53f4069a77d337f1))

* fix (control-GUI): by default hide full info entries and store its setting (#591) *by Dominik Kriegner* ([`ac9eee4`](https://github.com/andythomas/matr1x/commit/ac9eee4c02b89af5a2a0175a4337969852c78a66))

* update copyright year to 2024 for next release (#581) *by Dominik Kriegner* ([`f4c6ed5`](https://github.com/andythomas/matr1x/commit/f4c6ed5a2aead8eb3c09ce53e9943f4a7ec1e9a6))

* add new unit test to check matrix-script prefix/suffix (#568) *by Dominik Kriegner* ([`db4889f`](https://github.com/andythomas/matr1x/commit/db4889fa229056d0363e95c6980424c13cd19775))

* feat (control-GUI): allow QLabel instead of QLineEdit (#539) *by Dominik Kriegner* ([`7519ed9`](https://github.com/andythomas/matr1x/commit/7519ed9ce2d6e8c83c89e64f516ba4fabbe12803))

* introduce compression and allow setting dtype (#541) *by pheowl* ([`b9b808f`](https://github.com/andythomas/matr1x/commit/b9b808f4f78d3114feb0eb851b3066746289df32))

* fix (control-GUI): make lockfiles less annoying (#529) *by Dominik Kriegner* ([`67eaefa`](https://github.com/andythomas/matr1x/commit/67eaefa436b03729136af63526973d2f90a62df3))

* avoid double call of clear_ui() *by Andy Thomas* ([`41c6524`](https://github.com/andythomas/matr1x/commit/41c65245915083b600072a85a6f0dcc4c033a749))

* Solves issue #314 *by Andy Thomas* ([`8a7d09c`](https://github.com/andythomas/matr1x/commit/8a7d09ccbf4cb5964909e8024ebad2de78741ac5))

* fix (VisaDevice): close device connection upon exception during open (#531) *by Dominik Kriegner* ([`b12636c`](https://github.com/andythomas/matr1x/commit/b12636c4f8498f7df24186741e5d8a865a0db7e9))

* fix (code-quality): Reduce linter noise by fixing many warnings (#533) *by Dominik Kriegner* ([`535f8c7`](https://github.com/andythomas/matr1x/commit/535f8c7794e3f29717afb2a62fdcffc430e4ac67))

* fix (matrix-script): correct handling of strings in command creation (#530) *by Dominik Kriegner* ([`08b06cc`](https://github.com/andythomas/matr1x/commit/08b06cc07827e82104587753cd5737bd0ede0616))

* implement new devices used in FZU (#510) *by Dominik Kriegner* ([`11056d2`](https://github.com/andythomas/matr1x/commit/11056d29db2e0169feb62ccd6c4f5f4c888e7dbf))

* AJA improvements and matrix-script fix on windows (#517) *by Dominik Kriegner* ([`9d9d15a`](https://github.com/andythomas/matr1x/commit/9d9d15ad50dffb4cbb497046dde71c047e4c9461))

* Revert "add things only to the end of the output window (#515)" (#516) *by Dominik Kriegner* ([`3e4cfcb`](https://github.com/andythomas/matr1x/commit/3e4cfcb4c66930715fff90c130fc06373a0381d0))

* add things only to the end of the output window (#515) *by Dominik Kriegner* ([`bf5a754`](https://github.com/andythomas/matr1x/commit/bf5a754038c7b8e1a1716e76fa24796389a2feae))

* get the currently set mode of the Keithley multimeter (R, 4w R, v, etc.) *by baduraan* ([`abf6e57`](https://github.com/andythomas/matr1x/commit/abf6e57a9a17408599c18215102788f05868108c))

* Update __init__.py *by baduraan* ([`21bae20`](https://github.com/andythomas/matr1x/commit/21bae20c43eedaa30454f6ead31b83e70d33d265))

* new HP device and lock in system *by baduraan* ([`eb6593a`](https://github.com/andythomas/matr1x/commit/eb6593a3069e4327a2dc1c1f7fedfe22ae4ddc29))

* cherry pick changes to fix matrix-script *by baduraan* ([`2cb75dd`](https://github.com/andythomas/matr1x/commit/2cb75ddfa067f81fa85063799acf53fa8140c0f0))

* Elise (#489) *by pheowl* ([`9731f5c`](https://github.com/andythomas/matr1x/commit/9731f5c8403144b9032cd08e9cd976a025491e00))

* Matrix script/qscintilla (#458) *by pheowl* ([`83f0f17`](https://github.com/andythomas/matr1x/commit/83f0f17421d415ec7ec28b7b40ac49f33ded8a30))

* Issue453 (#457) *by pheowl* ([`19fd0e6`](https://github.com/andythomas/matr1x/commit/19fd0e645388fab7809b4656a32946831dce8c6a))

* Owis sms (#470) *by pheowl* ([`ff9a7d5`](https://github.com/andythomas/matr1x/commit/ff9a7d519e7a8f90daec89c1a1dd95ecf049d012))

* control vektorak devel *by baduraan* ([`191e4a7`](https://github.com/andythomas/matr1x/commit/191e4a70971378b9b613c44ec1751e5cc147fda3))

* Reinstate Thorlabs driver for BSC103 (#437) *by pheowl* ([`ec93294`](https://github.com/andythomas/matr1x/commit/ec93294ea356b89abb95a1785484ce04567f4693))

* Issue410 (#425) *by pheowl* ([`3fe2ad9`](https://github.com/andythomas/matr1x/commit/3fe2ad986eb9f3af9bd3c6ea5dbd530a590ca679))

* devel *by baduraan* ([`bebe09a`](https://github.com/andythomas/matr1x/commit/bebe09a2b3438eb8fa57bccc194753937a0f861c))

* further development *by baduraan* ([`0b96a84`](https://github.com/andythomas/matr1x/commit/0b96a845d57728a4a4daf9cbd27929f6cd4f0f34))

* make modular control GUI work (#407) *by Dominik Kriegner* ([`146239a`](https://github.com/andythomas/matr1x/commit/146239a8408f5628418a482ee0a9ae39080dc51d))

* work in progress *by baduraan* ([`20c253d`](https://github.com/andythomas/matr1x/commit/20c253d4165fa4950bace938f3da2b411ee06c36))

* Update system.py *by baduraan* ([`91285ed`](https://github.com/andythomas/matr1x/commit/91285ed687cfd8fdfd68dc54e9da9fb93f485027))

* pep8formatting action fixes (#406) *by github-actions[bot]* ([`f38395b`](https://github.com/andythomas/matr1x/commit/f38395b17603c058441287c254d27ee93f24a006))

* better automatic screen space saving *by Dominik Kriegner* ([`109d0b3`](https://github.com/andythomas/matr1x/commit/109d0b3828b786e5b38e1d8dd34662aa3748c6a8))

* let GuiDicts decide what to do in panic mode *by Dominik Kriegner* ([`02cc5db`](https://github.com/andythomas/matr1x/commit/02cc5db78eaf21853fc6c51614a314d73990b205))

* implement panic button in control_aja *by Dominik Kriegner* ([`e718205`](https://github.com/andythomas/matr1x/commit/e7182054caa4746d8c8d4df518e292b7f46a45e6))

* pep8formatting action fixes *by dkriegner* ([`c283db6`](https://github.com/andythomas/matr1x/commit/c283db64a489acb40e432f6b9ff8752e23e990b5))

* make cmd list be replaced insite *by Dominik Kriegner* ([`7ba428e`](https://github.com/andythomas/matr1x/commit/7ba428ecbdaf8266379f09ca658998f8d7ff58b2))

* fix indicator with to be of type int *by Dominik Kriegner* ([`ce54405`](https://github.com/andythomas/matr1x/commit/ce544058c50d40c3e97c7bc68b4c3fa6ec36ca73))

* better default size for activity indicator *by Dominik Kriegner* ([`74e89db`](https://github.com/andythomas/matr1x/commit/74e89db4f3cd3b265cba3cdf7479c6a97d46c631))

* fix control_dummy's device commands *by Dominik Kriegner* ([`137ab86`](https://github.com/andythomas/matr1x/commit/137ab867b0502485b6ffb8f1133ad22499e263d1))

* pep8formatting action fixes *by dkriegner* ([`2fde78f`](https://github.com/andythomas/matr1x/commit/2fde78f06557f7fa9187c9d1f37cb16aa2521235))

* set minimal width only for non-checkbox entries *by Dominik Kriegner* ([`ad1e238`](https://github.com/andythomas/matr1x/commit/ad1e23857c9bbacf6bd3b9484b5df75e2af9a429))

* minimal code adjustments to improve automatic window changing *by Dominik Kriegner* ([`b97b932`](https://github.com/andythomas/matr1x/commit/b97b932aee84c06d70adef9254848cdcba556885))

* clear read buffer of devices during system reset *by Dominik Kriegner* ([`875da50`](https://github.com/andythomas/matr1x/commit/875da50e6c2078beb0536c07a717d891b645d6dd))

* pep8formatting action fixes (#401) *by github-actions[bot]* ([`8ba135b`](https://github.com/andythomas/matr1x/commit/8ba135bf4b0a5507a06a0e68f0c4275c1da45ae7))

* add clear status-log button and improve window scaling *by Dominik Kriegner* ([`ee2b391`](https://github.com/andythomas/matr1x/commit/ee2b39157d023d62af4d7421c27495806394945a))

* pep8formatting action fixes (#400) *by github-actions[bot]* ([`e5992c7`](https://github.com/andythomas/matr1x/commit/e5992c731408bef9859ad22f51430e31f12e0add))

* save status of status box (collapsed or not) *by Dominik Kriegner* ([`049e0ba`](https://github.com/andythomas/matr1x/commit/049e0ba80d9ec2f8a5d0c411da59c74ff640ff9e))

* set sensible defaults for readjusting sizes *by Dominik Kriegner* ([`84f0d6f`](https://github.com/andythomas/matr1x/commit/84f0d6f57b8fca2cd9b8dfb3b71cca4d0767fca7))

* Fixes by autopep8 action (#398) *by github-actions[bot]* ([`2e21d68`](https://github.com/andythomas/matr1x/commit/2e21d68dcc9a52cb5583de748e51b916d76eb114))

* enable saving the window geometry *by Dominik Kriegner* ([`935934a`](https://github.com/andythomas/matr1x/commit/935934aaf7bbeba6ef996818bdb980ca4cfaa39a))

* pep8formatting action fixes (#395) *by github-actions[bot]* ([`20978fa`](https://github.com/andythomas/matr1x/commit/20978fa31cc6eb565c30cee8d44bee7e61cac2d4))

* pep8formatting action fixes (#387) *by github-actions[bot]* ([`7b99e2d`](https://github.com/andythomas/matr1x/commit/7b99e2d9e5312c3086b375cbed6696dfab06493e))

* rewrite AJA control based on new controlGUI *by Dominik Kriegner* ([`db8fbd1`](https://github.com/andythomas/matr1x/commit/db8fbd1a35536e824479dfca449d9268d26ec8a6))

* Refactor(controlGUI): construct layout and code cleanups (#348) *by Dominik Kriegner* ([`144588c`](https://github.com/andythomas/matr1x/commit/144588cec8eb1124f94173525c9fecd3ed740bf4))

* add QDoubleSpinBox as possible GUI element *by Dominik Kriegner* ([`98875e8`](https://github.com/andythomas/matr1x/commit/98875e8193e594ddad14b567db4bb1d4ecb2c96c))

* more error checking and flexibility in GUI creation *by Dominik Kriegner* ([`1813098`](https://github.com/andythomas/matr1x/commit/181309895d4454dcbdbb3223fe9b7054a10e9e53))

* pep8formatting action fixes *by andythomas* ([`7c00cb8`](https://github.com/andythomas/matr1x/commit/7c00cb81ae7e4cbde2ce619afd8f3ced43dbbf9d))

* Revert "refactor(eval): delete deprecated loadh5matrix" *by Andy Thomas* ([`a125b8b`](https://github.com/andythomas/matr1x/commit/a125b8b76691446586846cda4b443f67196a5927))

* add QSpinBox as GUI element in control GUIs *by Dominik Kriegner* ([`48a35cd`](https://github.com/andythomas/matr1x/commit/48a35cdd6812ca328819d8b45bb06a502d6942fd))

* make control_dummy more representative of real control GUIs *by Dominik Kriegner* ([`2afd2f2`](https://github.com/andythomas/matr1x/commit/2afd2f24faac885d392080a74c5e46e8fe34b4ef))

* pep8formatting action fixes *by andythomas* ([`d01fdd5`](https://github.com/andythomas/matr1x/commit/d01fdd5b20d6854ffe78c55762e0ae952dd055be))

* Feat(Qt): Works with Qt5 and Qt6 *by Andy Thomas* ([`fa8c8ea`](https://github.com/andythomas/matr1x/commit/fa8c8eadb93c684b1bb9f8abe791c6b4ccf21ca3))

* icon image updates *by dkriegner* ([`f452c50`](https://github.com/andythomas/matr1x/commit/f452c506db76f08a536842e9f16c25dfbeeb26f1))

## v7.2.0 (2022-10-10)

### Bug fixes

* fix(GUI): add AppUserModelID for control GUIs *by Dominik Kriegner* ([`af34d6d`](https://github.com/andythomas/matr1x/commit/af34d6d7b44fe8242e96d86b0851c4355136cccf))

* fix(GUI): selected control icon *by Andy Thomas* ([`c2c7b44`](https://github.com/andythomas/matr1x/commit/c2c7b444e59e3664858e4a8f8b3ab93315ceb193))

* fix(GUI): better progressbar as level indicator. (#284) *by Dominik Kriegner* ([`b71a28c`](https://github.com/andythomas/matr1x/commit/b71a28c2529c47243613b7b8bdeab53d25886bc2))

* fix(GUI): better progressbar as level indicator. *by Dominik Kriegner* ([`b71a28c`](https://github.com/andythomas/matr1x/commit/b71a28c2529c47243613b7b8bdeab53d25886bc2))

* fix(visadevice): print out source of the error inside visadevice (#260) *by Dominik Kriegner* ([`3d051e0`](https://github.com/andythomas/matr1x/commit/3d051e0192e74b6d357efe93be572810bfa6d160))

* fix(visadevice): print out source of the error inside visadevice *by Dominik Kriegner* ([`3d051e0`](https://github.com/andythomas/matr1x/commit/3d051e0192e74b6d357efe93be572810bfa6d160))

* fix: print identifier on the system level in case of exceptions during hardware access *by Dominik Kriegner* ([`3d051e0`](https://github.com/andythomas/matr1x/commit/3d051e0192e74b6d357efe93be572810bfa6d160))

* fix(System): better error information in set_/read_/trigger_value *by Dominik Kriegner* ([`3d051e0`](https://github.com/andythomas/matr1x/commit/3d051e0192e74b6d357efe93be572810bfa6d160))

* fix(GUI): update matrix_preview svg file *by Andy Thomas* ([`bfc403a`](https://github.com/andythomas/matr1x/commit/bfc403aa90133c804dea07771569af8a0f4213ce))

* fix: error detected by linter in previous commit *by Dominik Kriegner* ([`6f8195b`](https://github.com/andythomas/matr1x/commit/6f8195b2dc3605830d730f008b95b75ec551f7eb))

* fix(controlGUI): better error prevention in temp_statistics upon non numerical values *by Dominik Kriegner* ([`a6bfa11`](https://github.com/andythomas/matr1x/commit/a6bfa11a27c3de43d2da0af778f3b5d4b65e3009))

### Build system

* build(dependencies): add pyqtgraph version dependencies *by Dominik Kriegner* ([`1bccda8`](https://github.com/andythomas/matr1x/commit/1bccda86141ca1be314bdd0d61a7c6a869c810e0))

* build(INSTALL): mac specific bugfixes *by Andy Thomas* ([`7318ae3`](https://github.com/andythomas/matr1x/commit/7318ae360a77a9a00febb2c7bf967ab97f2589ab))

* build(finish-install-script-for-Linux): The INSTALL script now performs the desktop integration for all selected control GUIs *by Dominik Kriegner* ([`029c394`](https://github.com/andythomas/matr1x/commit/029c394b01c9d70aab2d361f0eb2169d4d5eaee2))

### Code style

* style(controlGUI): improve code readability *by Dominik Kriegner* ([`af135f7`](https://github.com/andythomas/matr1x/commit/af135f74a4bb45df9d4d8198fa0a44712bcab37f))

* style: address comment from code review *by Dominik Kriegner* ([`b71a28c`](https://github.com/andythomas/matr1x/commit/b71a28c2529c47243613b7b8bdeab53d25886bc2))

* style(control_dummy): better variable names (snake_case) and correct run_delay use *by Dominik Kriegner* ([`2d7ba9c`](https://github.com/andythomas/matr1x/commit/2d7ba9c44d96c8f85980d9dc1021461398ed38c9))

### Features

* feat(controlGUI): implement a ToggleButton for the immediate setting of a bool value *by Dominik Kriegner* ([`0a4beaf`](https://github.com/andythomas/matr1x/commit/0a4beafdff66b96014bb6df1ea073d0baa510c76))

* feat(GUI): control icons added *by Andy Thomas* ([`f2c3e9c`](https://github.com/andythomas/matr1x/commit/f2c3e9cd5bb74667bd53f1b11d47f611729b1573))

* feat(matrix_gui): enables queueing of several measurements *by pheowl* ([`1436c37`](https://github.com/andythomas/matr1x/commit/1436c376ef690c853a86047f78ca086aa71f2c4a))

* feat(matrix_gui): only show queue functionality while in use - addresses comments by @dkriegner *by pheowl* ([`1436c37`](https://github.com/andythomas/matr1x/commit/1436c376ef690c853a86047f78ca086aa71f2c4a))

* feat(controlGUI): improved unit handling and comboboxes for control GUIs *by Dominik Kriegner* ([`b47b9b8`](https://github.com/andythomas/matr1x/commit/b47b9b8fc15467dbd26bc5aa60549fa4667b7bad))

### Unknown

* pep8formatting action fixes (#287) *by github-actions[bot]* ([`adf1268`](https://github.com/andythomas/matr1x/commit/adf1268f81068d65ef55b4d028542a6e44d179de))

* icon image updates *by andythomas* ([`4b66f1f`](https://github.com/andythomas/matr1x/commit/4b66f1f2efd71c90fadfddb037fed4612e21f457))

* Fixes by autopep8 action (#290) *by github-actions[bot]* ([`601ed3b`](https://github.com/andythomas/matr1x/commit/601ed3bbeccb3dbc1e541d0d80656eb2ef999e1e))

* Measurement queue (#280) *by pheowl* ([`1436c37`](https://github.com/andythomas/matr1x/commit/1436c376ef690c853a86047f78ca086aa71f2c4a))

* fake change: whitespace edit in svg to trigger github action *by Dominik Kriegner* ([`bcf3e48`](https://github.com/andythomas/matr1x/commit/bcf3e485b5d87b4baaaad061a3354ba5b7a971c3))

* fake update of svg file to test github action *by Dominik Kriegner* ([`3abdccb`](https://github.com/andythomas/matr1x/commit/3abdccbca23a3fffb9f9e8c6bb449b7305a1c22c))

* fake update of svg file to test github action *by Dominik Kriegner* ([`7a797ea`](https://github.com/andythomas/matr1x/commit/7a797ead94d095f75609934766807963666e7107))

* fake update to svg file *by Dominik Kriegner* ([`16d7d39`](https://github.com/andythomas/matr1x/commit/16d7d39733a31fbd2223e7742e0231fbcf6c3870))

* fake update of svg file to test github action *by Dominik Kriegner* ([`2f3a05e`](https://github.com/andythomas/matr1x/commit/2f3a05eb9e0cf4c2f2edc82fef740c769eab5f68))

## v7.1.0 (2022-06-06)

### Bug fixes

* fix(preview): fix behavior of math textedit to trigger recalc on focusOut *by pheowl* ([`7c8e2ef`](https://github.com/andythomas/matr1x/commit/7c8e2ef9057cbb6f0297fe739359e8f552432a11))

* fix(preview): windows icon integration for matrix_preview *by Dominik Kriegner* ([`01b0036`](https://github.com/andythomas/matr1x/commit/01b0036943026d0abca732a9e34411deb9cfdfba))

* fix(GUI): polish icons, better Mac integration *by Andy Thomas* ([`2d21ee5`](https://github.com/andythomas/matr1x/commit/2d21ee53b1e8920ab385cd20c3f733cbc58183d7))

* fix(linux): more solid desktop integration in linux *by Dominik Kriegner* ([`7a7a234`](https://github.com/andythomas/matr1x/commit/7a7a234eb649d7100dc4c7e68d78ef9eedd3fc40))

* fix(GUI): final(?) icons selected *by Andy Thomas* ([`65f332b`](https://github.com/andythomas/matr1x/commit/65f332bc45eeeb1829f54c81d6cfa881cf530cd2))

* fix(GUI): another suggested icon set added *by Andy Thomas* ([`07e6b46`](https://github.com/andythomas/matr1x/commit/07e6b4640d3d2b84351c267aea07f5fde46a4ae7))

* fix(GUI): chose matrix GUI icon *by Andy Thomas* ([`3e6bf19`](https://github.com/andythomas/matr1x/commit/3e6bf1985617fddd048e8b888dbaf726227130f0))

* fix: another icon design added *by Andy Thomas* ([`7b12a2c`](https://github.com/andythomas/matr1x/commit/7b12a2cb01b76c2658688d4b7a09a1897911bafe))

* fix: another new icon design *by Andy Thomas* ([`f2c9012`](https://github.com/andythomas/matr1x/commit/f2c9012e0f0213163e8820d360932d63187252ea))

* fix: new icon design added *by Andy Thomas* ([`63429dc`](https://github.com/andythomas/matr1x/commit/63429dc5c36347e6f840049833bb11809b328503))

* fix: addresses issue #254, properly handle the stop button after major rewrite of matrix_script code. (#256) *by pheowl* ([`a521e46`](https://github.com/andythomas/matr1x/commit/a521e4678d5540351840b95f0d6e3d685acd2596))

* fix(system_dummy_feature): implement meaningful example of device (de-)initialization *by pheowl* ([`a521e46`](https://github.com/andythomas/matr1x/commit/a521e4678d5540351840b95f0d6e3d685acd2596))

* fix(eval): break retry loop after 10 iterations and raise error *by pheowl* ([`c0966d7`](https://github.com/andythomas/matr1x/commit/c0966d77d58e505f964f37ccab58f8707f1c02c5))

* fix(gui_util): fix errors in SimplePlotWidget *by pheowl* ([`e7b9c39`](https://github.com/andythomas/matr1x/commit/e7b9c39cdba7ace529434cb2c783b40d995f4e1d))

* fix(preview): usability fixes, refactoring, minor changes to layout *by pheowl* ([`dc5615d`](https://github.com/andythomas/matr1x/commit/dc5615dd2c08dd9bcf8cbad193b1061b5d596b19))

* fix(preview): plain disabling of index indicator without resetting index to empty can lead to errors *by pheowl* ([`0660c18`](https://github.com/andythomas/matr1x/commit/0660c185f8cef98e31955a8f9ef1593e2dfe8a0b))

* fix(preview): fix matrix_preview with new loadmatrix *by Dominik Kriegner* ([`012b0e7`](https://github.com/andythomas/matr1x/commit/012b0e776cf07a6a0c1b39dababf92f2f69ca5f7))

* fix(eval): correct (hopefully) use of hdf5 SWMR mode *by Dominik Kriegner* ([`4e938a9`](https://github.com/andythomas/matr1x/commit/4e938a9dce9783ab973d800812066854cd2310a6))

### Build system

* build(linux): install script cleanup and addition of mime type installation on Linux *by Dominik Kriegner* ([`7ce2532`](https://github.com/andythomas/matr1x/commit/7ce253228ff26722c8652da182607c9a763bd9e2))

### Documentation

* docs(gui_util): add documentation for SimplePlotWidget *by pheowl* ([`f758db8`](https://github.com/andythomas/matr1x/commit/f758db8f239101ef818e8f95036b4ebda2a4ed5f))

* docs(gui_util): documentation for PlotObject added *by pheowl* ([`0a418af`](https://github.com/andythomas/matr1x/commit/0a418af310e9ef22cca4c7d1a175f22a28b0315c))

### Features

* feat(matrix_gui): user decided setting for automatic file name generation *by Dominik Kriegner* ([`15c544d`](https://github.com/andythomas/matr1x/commit/15c544dad53dbbecefd9a40cd31271dfffe7c942))

* feat(Mac): add application bundles *by Andy Thomas* ([`de141ba`](https://github.com/andythomas/matr1x/commit/de141ba9d855673e4d002ec9eac4842912d0ef19))

* feat(GUI): script ison added *by Andy Thomas* ([`8c1fdaa`](https://github.com/andythomas/matr1x/commit/8c1fdaac37f2fe90b225377f88c769a684d16f21))

* feat(GUI): sweep generator icon added *by Andy Thomas* ([`0ef70bd`](https://github.com/andythomas/matr1x/commit/0ef70bdfbaf09fdcf1d609dd89f579d68cbf446e))

* feat(GUI): preview icon *by Andy Thomas* ([`a85f702`](https://github.com/andythomas/matr1x/commit/a85f70269b024c5a2ec75891ea76172a5b20ee86))

* feat(GUI): add icon files *by Andy Thomas* ([`af30f14`](https://github.com/andythomas/matr1x/commit/af30f1432dc091b835f4700455dacefdb2708ec2))

* feat(GUI): add desktop files for matrix_gui and sweep_generator *by Dominik Kriegner* ([`0e7453a`](https://github.com/andythomas/matr1x/commit/0e7453a16c71a90302267dafd178208fb5d3a9a5))

* feat(preview): implement file change functionality, address comments by @dkriegner *by pheowl* ([`dd00372`](https://github.com/andythomas/matr1x/commit/dd003720464fe2622cb538d8bd5e35351ec7c21d))

* feat(preview): add possibility to switch file, still needs improvement *by pheowl* ([`e3d65e8`](https://github.com/andythomas/matr1x/commit/e3d65e8228fe61e8edb48a66c6f2129267c2349e))

* feat(matrix_preview): further improvements on 2d plot handling *by pheowl* ([`c4b5659`](https://github.com/andythomas/matr1x/commit/c4b56590d98008b447f217cc14bd99335d3815e8))

* feat(eval): merge loadmatrix with loadh5matrix and fix hdf5 data format (#257) *by Dominik Kriegner* ([`c294a38`](https://github.com/andythomas/matr1x/commit/c294a38dcb11461df079c15841cc6f5f503df0a6))

* feat(eval): merge loadmatrix and loadh5matrix *by Dominik Kriegner* ([`c294a38`](https://github.com/andythomas/matr1x/commit/c294a38dcb11461df079c15841cc6f5f503df0a6))

* feat(hdf5): change hdf5 files metadata to attributes, adapt parser accordingly *by Dominik Kriegner* ([`c294a38`](https://github.com/andythomas/matr1x/commit/c294a38dcb11461df079c15841cc6f5f503df0a6))

* feat(matrix_preview): add mime specification and desktop file *by Dominik Kriegner* ([`377ff96`](https://github.com/andythomas/matr1x/commit/377ff965b3053a6b619a580c318a6875c10b3522))

### Performance improvements

* perf(SimplePlotWidget): shrink the functional elements of layout to single line to improve use of space *by pheowl* ([`a0041d7`](https://github.com/andythomas/matr1x/commit/a0041d7bcfc47835d00bc2a009235f90f7a1225b))

### Unknown

* pep8formatting action fixes *by dkriegner* ([`f413fb8`](https://github.com/andythomas/matr1x/commit/f413fb80436c16ad7a19a6720b9af95e0a837be0))

* pep8formatting action fixes *by andythomas* ([`570bdf0`](https://github.com/andythomas/matr1x/commit/570bdf0824a3d82351100c8a59a6842a5a4f052b))

* pep8formatting action fixes (#270) *by github-actions[bot]* ([`bb6dcfd`](https://github.com/andythomas/matr1x/commit/bb6dcfd31425dceebb7bdfdb6bf2117bc4c88f82))

* use installed icon files for window icons *by Dominik Kriegner* ([`00b8e8f`](https://github.com/andythomas/matr1x/commit/00b8e8ff81e3a0d7cc7c29d5342386d494a3b3ea))

* move icons to be installed with the python sources *by Dominik Kriegner* ([`39a2212`](https://github.com/andythomas/matr1x/commit/39a2212c0f22d46d2834905e9083f58519359860))

* pep8formatting action fixes (#263) *by github-actions[bot]* ([`0822282`](https://github.com/andythomas/matr1x/commit/08222821182a9d3af85fc09be25ebfcf9ff09699))

* assign ma7 files to matrix_preview on Windows *by Dominik Kriegner* ([`b1aa274`](https://github.com/andythomas/matr1x/commit/b1aa274985878e072d22338155a2ff0676ffa74e))

* pep8formatting action fixes (#251) *by github-actions[bot]* ([`74f8dbf`](https://github.com/andythomas/matr1x/commit/74f8dbf6ec3b15b6523840c154f7e51ce8756f4d))

* add 2d plotting functionality, first working version *by pheowl* ([`713132f`](https://github.com/andythomas/matr1x/commit/713132fc672f3a87b8e9781952ad0f36d281992e))

* intermediate storage of progress *by pheowl* ([`164ec12`](https://github.com/andythomas/matr1x/commit/164ec12fb17332a0544485b028e20337f703babc))

* pep8formatting action fixes (#250) *by github-actions[bot]* ([`e0fd277`](https://github.com/andythomas/matr1x/commit/e0fd27715e5c578152d7ad76fdde6b3b2bf877de))

* address comments by @dkriegner *by pheowl* ([`eee38c3`](https://github.com/andythomas/matr1x/commit/eee38c3cb89b0064ad346b89a3f3ea52324b6caf))

* modernize build system of core_library/matr1x *by Dominik Kriegner* ([`e3f251c`](https://github.com/andythomas/matr1x/commit/e3f251c599d15ffd78d9da41c90f7c5192ba7d0d))

* pep8formatting action fixes (#247) *by github-actions[bot]* ([`eaade0c`](https://github.com/andythomas/matr1x/commit/eaade0c6b27951660980d1bd7d79e19f47eec0dc))

* add possibility for custom math by simple eval *by pheowl* ([`3ac9b8e`](https://github.com/andythomas/matr1x/commit/3ac9b8e82bef72e876b986f44bbc55ebebeba1c1))

* pep8formatting action fixes (#246) *by github-actions[bot]* ([`ae9b99d`](https://github.com/andythomas/matr1x/commit/ae9b99ddfe3a1c4bc69c53ddf8b2548f1ba2078a))

* add capabilities to show multiple plots, improve dimension handling *by pheowl* ([`36f64f4`](https://github.com/andythomas/matr1x/commit/36f64f4169f66b8bafe699b57154329ad7f742c0))

* minor refactoring, properly address issue with changing names in structured numpy array *by pheowl* ([`384d311`](https://github.com/andythomas/matr1x/commit/384d3113e48ce07fd8d77278c5c153c68fc66ad1))

## v7.0.0 (2022-04-05)

## v6.0.1 (2022-04-05)

### Bug fixes

* fix: remove pip dependency in pyproject.toml which is ignored anyways *by Dominik Kriegner* ([`4aec604`](https://github.com/andythomas/matr1x/commit/4aec60409654b495cfe336f1067f2df25b69df34))

* fix: use lower case extra-options dependency in entry-points *by Dominik Kriegner* ([`f2b35e0`](https://github.com/andythomas/matr1x/commit/f2b35e01dad6d69c0660cfecb0d2b9e8901bb74f))

### Build system

* build: add semantic release settings and workflow (#243) *by Dominik Kriegner* ([`f2576d3`](https://github.com/andythomas/matr1x/commit/f2576d3af455d42da5b41f8ac716469ed009b588))

### Unknown

* fix error preventing non-h5 files from being opened *by pheowl* ([`0f226da`](https://github.com/andythomas/matr1x/commit/0f226da4880455ed176d27650015ed89d584a523))

* fix linter error *by pheowl* ([`27ecfc7`](https://github.com/andythomas/matr1x/commit/27ecfc7cbd8ff2f96821e31c161882a7180955d6))

* pep8formatting action fixes (#244) *by github-actions[bot]* ([`c72ced3`](https://github.com/andythomas/matr1x/commit/c72ced3f1662798d61881d560c1161a6de7cc145))

* add handling of hdf5 multidimensional data slicing *by pheowl* ([`e488661`](https://github.com/andythomas/matr1x/commit/e488661523be23ff6317e9a2f64e39f9d2798f59))

* use the new names/units *by pheowl* ([`f850c63`](https://github.com/andythomas/matr1x/commit/f850c631cb3e5b91d274cbf232f6c6fb5c2b7d3f))

* create branch with separate matrix_preview gui script *by pheowl* ([`4e33168`](https://github.com/andythomas/matr1x/commit/4e33168a676273c13b660a6032c4fd6d3a4e2bdc))

* use exclusively Pyproject.toml and switch to flit build system (#237) *by Dominik Kriegner* ([`9047827`](https://github.com/andythomas/matr1x/commit/9047827ebe8c72bcb8b3693c7fbf825d40853c06))

* pep8formatting action fixes (#239) *by github-actions[bot]* ([`db113bf`](https://github.com/andythomas/matr1x/commit/db113bf11392452412250992aea740bb97142bf7))

* automatically set hdf5 flag if needed *by Dominik Kriegner* ([`0fa7d5b`](https://github.com/andythomas/matr1x/commit/0fa7d5bac3d19571531a0afaa14a8bd27c8c7379))

* attempt to make multidimensional data work with text data files *by Dominik Kriegner* ([`a061d8b`](https://github.com/andythomas/matr1x/commit/a061d8b6d7b6cf5804fd76e75877f628d2ea27d7))

* add unit test for higher dimensional data *by Dominik Kriegner* ([`798d74a`](https://github.com/andythomas/matr1x/commit/798d74aa3b206dc0bbc3ba64cddf9f9ebb5b1ee2))

* enable loading of higher dimensional data in hdf5-format *by Dominik Kriegner* ([`d8af096`](https://github.com/andythomas/matr1x/commit/d8af0961193c7aba7bd5acb7e2c4bd9da5807a53))

* enable higher dimensional data in matrix *by Dominik Kriegner* ([`19ec1bc`](https://github.com/andythomas/matr1x/commit/19ec1bc408d855b4f1876663a30273f6dcfc5781))

* make optional dependencies user lower case to work *by Dominik Kriegner* ([`40bad91`](https://github.com/andythomas/matr1x/commit/40bad915c5bf5b66abc09772f3c083002ad704df))

* require pip >=21.3 for the build to support PEP660 *by Dominik Kriegner* ([`425c7a1`](https://github.com/andythomas/matr1x/commit/425c7a18094d417897b795bf7975cc92858a71da))

* modernize build system of core_library/matr1x *by Dominik Kriegner* ([`1078a05`](https://github.com/andythomas/matr1x/commit/1078a05691a05313f72fe8f788d4b29b3697341b))

* try to automatically find matrix executable in common directories (#235) *by Dominik Kriegner* ([`a969237`](https://github.com/andythomas/matr1x/commit/a96923774a7a40e4e2a88069c70449fd9c1a6d7c))

* move print statement to show up also for hdf5 data files *by Dominik Kriegner* ([`08cb7d8`](https://github.com/andythomas/matr1x/commit/08cb7d8607ddb6c7db88686e6f3947ba872bf04a))

* hand over input and output file to system.reset *by Dominik Kriegner* ([`c1b44d7`](https://github.com/andythomas/matr1x/commit/c1b44d71f6f9c7cf8d959e2168d1ac8d4a1b0fae))

* fix windows path problem in matrix_script *by Dominik Kriegner* ([`1ccec36`](https://github.com/andythomas/matr1x/commit/1ccec36a41c9bda0f153b4b2bf4afe0196ee6f08))

* visually indicate read only fields in control GUIs (#232) *by Dominik Kriegner* ([`8f2fb69`](https://github.com/andythomas/matr1x/commit/8f2fb698959c32a2a224b7482c5a0c2b8b50e76e))

* update to BOSS power supply *by sebastianbeckert* ([`4514b46`](https://github.com/andythomas/matr1x/commit/4514b46c4fcebb9a33cf9484219bc439863221cd))

* remove debug log statement, hide logging checkboxes when status is colla[sed *by pheowl* ([`8afa931`](https://github.com/andythomas/matr1x/commit/8afa931594e5416b5d73bed61a9d94fb5c966558))

* fix issue #226: gracefully return from an error in control gui *by Dominik Kriegner* ([`0b817cf`](https://github.com/andythomas/matr1x/commit/0b817cfa1d84de3470faae5e349bdb2593a05291))

* working on #226, better disabling and cleanup after Exception *by Dominik Kriegner* ([`43102ed`](https://github.com/andythomas/matr1x/commit/43102ed5df8162c596428e76dda94894561d1064))

* flush input on start of matrix (#229) *by Dominik Kriegner* ([`81a9f6e`](https://github.com/andythomas/matr1x/commit/81a9f6e9624554fcf7e6be755d55da2ac7fda05d))

* fix var.copy_values for single column fields *by Dominik Kriegner* ([`6091d7c`](https://github.com/andythomas/matr1x/commit/6091d7cda794c1f6dede4ec91eadccbbcfa2542a))

* remove unneeded distinction in loop *by Dominik Kriegner* ([`ea7a4b7`](https://github.com/andythomas/matr1x/commit/ea7a4b714b25934f3d4ecaf34678155fc365cf18))

* more readable control GUI definition and usage (#223) *by Dominik Kriegner* ([`ece93b2`](https://github.com/andythomas/matr1x/commit/ece93b25d81b76f9b8be9940fa01bb6d0d8ea143))

* fix remaining time calculation in matrix_script *by Dominik Kriegner* ([`3cba3f0`](https://github.com/andythomas/matr1x/commit/3cba3f0f630e18796e8f1b75f901e356b7c6f105))

* Revert "fix remaining time calculation in matrix_script" *by Dominik Kriegner* ([`6db0de9`](https://github.com/andythomas/matr1x/commit/6db0de9b4602b8ffc19491b357d61373574138f0))

* fix remaining time calculation in matrix_script *by Dominik Kriegner* ([`9baf706`](https://github.com/andythomas/matr1x/commit/9baf70618f781f2afb2d5bfbd18ff6ebce4fde02))

* new system from IFW: Oxford "Blue15" (#220) *by Dominik Kriegner* ([`d43bc8b`](https://github.com/andythomas/matr1x/commit/d43bc8bd5572314787c136779258afa8827d21ed))

* higher default timeout for NVM *by Dominik Kriegner* ([`8040202`](https://github.com/andythomas/matr1x/commit/80402025df772826e0c915fa168e16d4289f18f8))

* sweep_generator - improve error handling on system import *by pheowl* ([`1cc3752`](https://github.com/andythomas/matr1x/commit/1cc375237ca76465e2c97e2450fe7d4a70201c4e))

* fix python < 3.9 *by Dominik Kriegner* ([`52f0817`](https://github.com/andythomas/matr1x/commit/52f08173f980a183b6d20a7f1d65651db0f1f295))

* remove useless systemfile argument, closes #217 *by Dominik Kriegner* ([`4de3371`](https://github.com/andythomas/matr1x/commit/4de3371c044fe33ddadc3af4a0c46cde54166aed))

* Issue82 (#210) *by pheowl* ([`14ff8d9`](https://github.com/andythomas/matr1x/commit/14ff8d9199690916bd50593ec0f25ad92b16c239))

* Control generalization (#207) *by pheowl* ([`a78b2c6`](https://github.com/andythomas/matr1x/commit/a78b2c63046a929870d40c9f5e2dd8941c48e5d2))

* log to tmp folder and stdout, fix issue #206 *by Dominik Kriegner* ([`bb23817`](https://github.com/andythomas/matr1x/commit/bb238176490be152bd78eb0807a110e70da7eefe))

* reimplementation of matrix_script commands (#203) *by Dominik Kriegner* ([`ae2d90a`](https://github.com/andythomas/matr1x/commit/ae2d90aad87ad3240f5ab9f1417adcb65e1b18eb))

* convert sweep generator to using QListWidget (#198) *by Dominik Kriegner* ([`c7bb466`](https://github.com/andythomas/matr1x/commit/c7bb466ea434a11569e23032ed8fde9ba3d20d8e))

* Qt update (#209) *by pheowl* ([`10683e8`](https://github.com/andythomas/matr1x/commit/10683e8c0a9d791fe9c70b9345a1a12b3bec11b7))

* keep v3 as float and only show its integer value in the progress bar *by Dominik Kriegner* ([`90ef250`](https://github.com/andythomas/matr1x/commit/90ef250f9896e6c5c536932cfc14b51a5aa26528))

* add QProgressBar to control_dummy.py for testing *by pheowl* ([`53c14ae`](https://github.com/andythomas/matr1x/commit/53c14aef9fdc01aab1ebb1e2c80aa702c568508b))

* set default range for qprogress bar *by pheowl* ([`6dd33c2`](https://github.com/andythomas/matr1x/commit/6dd33c226450650b69159b327b830174bf539ca2))

* since pyqt5 version something, qprogressbar accepts only int type, @dkriegner please acknowledge *by pheowl* ([`1ce1238`](https://github.com/andythomas/matr1x/commit/1ce1238c48310e94341a41aa7a04080f6b5b5d3a))

* fix warning in unittests *by Dominik Kriegner* ([`07991b5`](https://github.com/andythomas/matr1x/commit/07991b59269734c45dffae57096824c57876dc7c))

* matrix_script: better system file handling (#200) *by Dominik Kriegner* ([`7d9fccc`](https://github.com/andythomas/matr1x/commit/7d9fccccbcf5182fbea3144e5a764371439be9c3))

* fix matrix_script error occuring on Python <3.10 *by Dominik Kriegner* ([`735c1f7`](https://github.com/andythomas/matr1x/commit/735c1f76e82aeb06488f69865740c129f5a8e0a5))

* matrix_script: allow tilde in path of data file *by Dominik Kriegner* ([`64dcc62`](https://github.com/andythomas/matr1x/commit/64dcc62a974c53107c71a9d02617772789faf1e0))

* fix typo in system files: *by Dominik Kriegner* ([`a6cd517`](https://github.com/andythomas/matr1x/commit/a6cd5175164838ddb0e1731489bdeee6e2f4008d))

* make Keithley 2400, 2450 outputState work as intended *by Dominik Kriegner* ([`01b9f5b`](https://github.com/andythomas/matr1x/commit/01b9f5bcd60ea275e8e362c26c249cd8258ae740))

* update level meter card name in mercury power supply for ptarmigan *by Dominik Kriegner* ([`292a39d`](https://github.com/andythomas/matr1x/commit/292a39d189386febbda651a5426698495ab23e14))

* Revert "make ptarmigan system "cryo" only." *by Dominik Kriegner* ([`2cd8fcf`](https://github.com/andythomas/matr1x/commit/2cd8fcf80035e389d41959217b7f810309650565))

* make ptarmigan system "cryo" only. *by Dominik Kriegner* ([`3d9fcd2`](https://github.com/andythomas/matr1x/commit/3d9fcd2e2144a617e84a061fd2474658e7604a46))

* fixes issue 192 (#193) *by pheowl* ([`39ae1a9`](https://github.com/andythomas/matr1x/commit/39ae1a9375e0ff4bb98f8f08340d660233de0742))

* fix issue #155, implement get_latest_datafile (#188) *by Dominik Kriegner* ([`4919901`](https://github.com/andythomas/matr1x/commit/4919901c9fbfb510bfc6fdb05aac10568ecf4700))

* fix stretch so that full filename is visible *by pheowl* ([`81dccda`](https://github.com/andythomas/matr1x/commit/81dccdae4b14b2398eb64257061abac64e7e6800))

* Matrix script improvements (#186) *by pheowl* ([`0397051`](https://github.com/andythomas/matr1x/commit/039705135c36044563dd413832bbae1e5e09020a))

* clean up interface of sweep_generator upon removal of last system *by Dominik Kriegner* ([`a318de1`](https://github.com/andythomas/matr1x/commit/a318de18aa59468662be5fe7a15e43c48c169149))

* fix missing typecast to match overloaded definition of QIntValidator *by pheowl* ([`8ca1b4d`](https://github.com/andythomas/matr1x/commit/8ca1b4d803d86d60cf43911c60d5431603fb435f))

* do not ignore systems_directory in import_system (issue #180) (#183) *by Dominik Kriegner* ([`df141d4`](https://github.com/andythomas/matr1x/commit/df141d4cb8cde13869aba6c5cff05da364a9671d))

* make loaddat by default use an unstructured array *by Dominik Kriegner* ([`efbe8db`](https://github.com/andythomas/matr1x/commit/efbe8db3abeed0abe1cd4bf71ac73b1ac52353b4))

* better error handling in control GUis (#168) *by Dominik Kriegner* ([`5c0ba18`](https://github.com/andythomas/matr1x/commit/5c0ba189711a6ea3137eee5626634e308e77a17f))

* Eth pulses (#159) *by pheowl* ([`6707ef4`](https://github.com/andythomas/matr1x/commit/6707ef44a9860e9fccbf935ed93429b5cfed24a5))

* make usersfolder configurable (#161) *by Dominik Kriegner* ([`ac4b7b0`](https://github.com/andythomas/matr1x/commit/ac4b7b06255a79ec0c214c0c276ca9eb6cb925cd))

* make timestamp format in log and data file configurable *by Dominik Kriegner* ([`639960a`](https://github.com/andythomas/matr1x/commit/639960ab8c41626e531aa65e431674a2cc211a8c))

* better error message in control_dummy (#163) *by Dominik Kriegner* ([`1b47664`](https://github.com/andythomas/matr1x/commit/1b47664890d42b487402a9ba32949ae95fb145ff))

* use bool instead of boolean in docstrings *by Dominik Kriegner* ([`2331536`](https://github.com/andythomas/matr1x/commit/2331536f11fdfa4c376f2c2084744638abb31032))

* fix issue #158, reset units of Keithley2450 in configure *by Dominik Kriegner* ([`721fd99`](https://github.com/andythomas/matr1x/commit/721fd99cd87a326a168869b09922525d37696ffd))

* fix matrix_gui outputfilename issues *by Dominik Kriegner* ([`1ebcf3d`](https://github.com/andythomas/matr1x/commit/1ebcf3dd303e31ce809d9cb63cdc1b0c9d11c488))

* let matrix report back the used filename to matrix_gui (#148) *by Dominik Kriegner* ([`0fea98c`](https://github.com/andythomas/matr1x/commit/0fea98ce2a338ddd861c20f4f00e9f540dad95bf))

* add level meter to IFW mercury power supply *by Dominik Kriegner* ([`d5b46b2`](https://github.com/andythomas/matr1x/commit/d5b46b247c1a3fe4dec28ab4c7ad6a5fee9c538a))

* control_ptarmigan: add lakeshore input curve selection *by Dominik Kriegner* ([`ce0dec2`](https://github.com/andythomas/matr1x/commit/ce0dec2688bfd7cd23fbab8aeef8379855e461b1))

* move sweep_generator to scripts subfolder (#146) *by Dominik Kriegner* ([`15bd5db`](https://github.com/andythomas/matr1x/commit/15bd5dbc9411ec3ec21b6d6b3c7d6999176710e1))

* add nvmSerg to CFMS via GPIB *by Dominik Kriegner* ([`3606d41`](https://github.com/andythomas/matr1x/commit/3606d41af9494cb9c52b20ec5a99d8af3e423d91))

* mutex locking of IsobusDevice and IPS120 improvements *by Dominik Kriegner* ([`92e60cf`](https://github.com/andythomas/matr1x/commit/92e60cffd8879f6cd92825cc62467d2f5d90e86e))

* mutex locking for VisaDevice with shared connection *by Dominik Kriegner* ([`4024da8`](https://github.com/andythomas/matr1x/commit/4024da81a93371dc72b90d3e24317ba30d810ee0))

* reusable GUI dialogs for the Lakeshore controllers (#150) *by Dominik Kriegner* ([`55d20e7`](https://github.com/andythomas/matr1x/commit/55d20e752d4279d3dde0d80ecb8110c84ea208f1))

* correct printed line in matrix (remove one space) *by Dominik Kriegner* ([`ea7bc72`](https://github.com/andythomas/matr1x/commit/ea7bc7277aa5a32928d6619fe56c0c784ed30081))

* simplify control_dummy code *by Dominik Kriegner* ([`24ac3e9`](https://github.com/andythomas/matr1x/commit/24ac3e9ca18743a20b1e4038aa0f10f87def9fdc))

* make sweep_generator killable by ctrl+C *by Dominik Kriegner* ([`863f0b4`](https://github.com/andythomas/matr1x/commit/863f0b4a661578039cab68e0b6b01c5a56469e37))

* make mercury single axis device work again *by Dominik Kriegner* ([`d36505e`](https://github.com/andythomas/matr1x/commit/d36505e23002aa5c5e99cfe34de241c150df86b5))

* old changes from ptarmigan *by Dominik Kriegner* ([`f9919d4`](https://github.com/andythomas/matr1x/commit/f9919d4ed880d576906e558ba4c3bcc5c8487ba9))

* add back single axis mercury power supply for Ptarmigan *by Dominik Kriegner* ([`0138c9d`](https://github.com/andythomas/matr1x/commit/0138c9d076f5c3cfd09541b5c8a7fdbae795e4c4))

* cleanup control_dummy code *by Dominik Kriegner* ([`5edc029`](https://github.com/andythomas/matr1x/commit/5edc0293d191823911b54d2472013c141e20a52b))

* Scpi pickling in ASCII compatible way (#143) *by Dominik Kriegner* ([`9735fde`](https://github.com/andythomas/matr1x/commit/9735fdec4933d57a4416ccb851a11bd317e235be))

* make control_dummy a gui_script (#136) *by Dominik Kriegner* ([`53e47b3`](https://github.com/andythomas/matr1x/commit/53e47b3c90fbbda147bc91b41adfe8746c623cdc))

* fix a comment and simplify preview popup GUI code *by Dominik Kriegner* ([`e027c7c`](https://github.com/andythomas/matr1x/commit/e027c7caf614e2dd758948cfa5e9cc66cfaa8ae4))

* fix issue #134 *by pheowl* ([`787d4fa`](https://github.com/andythomas/matr1x/commit/787d4fa95dd8104ca3dae66a948ef50ad5dae9c1))

* fix issue #138 (#139) *by pheowl* ([`f7710e3`](https://github.com/andythomas/matr1x/commit/f7710e30f956a4b3ca8f8a2ba2f5b91b794db2ef))

* make matrix_gui window properly rescale *by Dominik Kriegner* ([`a313cfd`](https://github.com/andythomas/matr1x/commit/a313cfdef18fcce872772edb8a0f02c46b6eccdf))

* increase timeout of nvm for nplc=10 to work *by Dominik Kriegner* ([`a38d48e`](https://github.com/andythomas/matr1x/commit/a38d48ee459dff56ff0ffa01ecd94ce53204eb74))

* fix getLatestOutput of matrix_gui *by Dominik Kriegner* ([`60a9bd2`](https://github.com/andythomas/matr1x/commit/60a9bd29a6ce606048f7c9dd3ef8d13460bc91f8))

* separate core library out of ifwlib (#129) *by Dominik Kriegner* ([`89d85b0`](https://github.com/andythomas/matr1x/commit/89d85b08e60249365b34e5f8324f21a55204991a))
