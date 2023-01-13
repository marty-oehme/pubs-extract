# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project tries to adhere to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!--
## [Unreleased]

### Added

### Changed

### Fixed
-->

## [0.2.0] - 2023-01-13

### Added

* Added pypi release publication
* Try not to duplicate extracted annotations in existing notes
* Map annotation colors to custom tags in notes
* Add querying for publications to command (like list command)

### Fixed

* Grab annotations even if their content is empty or contains custom text

## [0.1.0] - 2022-12-25

* Extract highlights and annotations from a pubs doc file
* Optionally run automatically whenever file is added to pubs
* Optionally write annotations to pubs note file
