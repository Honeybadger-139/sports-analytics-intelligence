# ONNX and Library Versioning

## What Is ONNX?

ONNX stands for Open Neural Network Exchange. It is a portable model format that lets you move trained models across runtimes without being locked into the original training library.

For this project, the main value is portability:

- train in Python with scikit-learn, XGBoost, or LightGBM
- export a stable inference artifact
- serve or inspect that artifact in a different environment later

## Why ONNX Matters in Production

ONNX helps when you want:

- a more portable inference path
- less dependency coupling between training and serving
- the ability to benchmark or swap runtimes later
- a clearer artifact boundary for deployment and rollback

Even when the export is best-effort, it is useful because it gives the team another serving format besides the original Python object.

## Why Library Versioning Matters

Model artifacts are not just weights. They are also shaped by the libraries that created them.

Examples:

- scikit-learn pipeline internals can change across major releases
- XGBoost serialization behavior can drift across versions
- LightGBM wrappers can depend on runtime-specific object structure

If the serving runtime upgrades a major version unexpectedly, a model may still load but behave differently, or it may fail outright.

## Why `fillna(0)` and Missing Versions Are Both Risky

The same production principle applies in both cases:

- missing data should be imputed with a meaningful value
- missing version metadata should be treated as operational risk

If we do not record library versions, we lose the ability to explain why a model works in training but fails in serving.

## What We Store

The training pipeline writes a `version_info_{timestamp}.json` file containing:

- Python version
- scikit-learn version
- XGBoost version
- LightGBM version
- NumPy version
- pandas version
- training timestamp
- feature column list

That metadata is also embedded in training metadata so it travels with the model run.

## Version Compatibility Strategy

At inference startup, we compare the loaded artifact's versions against the current runtime versions.

Rules:

- warn when sklearn major versions differ
- warn when XGBoost major versions differ
- raise only when the major gap is larger than 1

This keeps minor drift visible without being overly strict, while still protecting us from large compatibility jumps.

## Interview Questions

1. What problem does ONNX solve?
2. Why would you export a model to ONNX if you already have joblib?
3. Why is version metadata part of the model artifact?
4. What can go wrong when training and serving environments drift?
5. When would you warn versus fail on a dependency mismatch?
6. How does version pinning improve rollback confidence?

## Short Interview Answer

"I export models to ONNX as a portable inference format and I store library versions with the artifact so serving can detect compatibility drift early. That way the model file is not just a blob of weights — it is a reproducible, auditable deployment unit."
