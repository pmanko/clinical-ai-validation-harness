# Dataset Sources

Track source pointers and checksums for large source datasets.

The OpenMRS 2.7 demo corpus (`large-demo-data-2-7-0.sql`) is not stored in this repository. It is distributed separately and is expected as a sibling checkout:

```
../openmrs-module-chartsearchai/data/large-demo-data-2-7-0.sql
```

Or set `CHARTSEARCHAI_REPO=/path/to/openmrs-module-chartsearchai` and reference it from there.

Store checksum manifests here if legal and practical for your environment.

`evaluation-baseline.json` records the reviewed portable corpus identity used by
the [environment setup workflow](../../docs/environment-setup.md). Its download
source is not configured yet; setup accepts an explicit reviewed local or HTTPS
source and verifies the package plus its provenance before use.
