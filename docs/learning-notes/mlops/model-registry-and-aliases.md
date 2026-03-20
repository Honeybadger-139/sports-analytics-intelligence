# Model Registry And Aliases

## What Is A Model Registry?

A model registry is a catalog for trained models. It stores version history,
metadata, and promotion state so teams can manage models like software
releases instead of opaque files.

## Why It Matters

Without a registry, teams usually know only the latest artifact path. That
creates problems when you need to:

- compare versions
- audit a training run
- promote a challenger
- roll back a bad release

## Model Version Vs Alias

- A version is the concrete numbered snapshot.
- An alias is a human-friendly pointer to a version.

Examples:

- `version 7`
- `production`
- `staging`
- `champion`

Aliases make operations safer because deployment code can target a stable name
instead of a moving version number.

## Zero-Downtime Rollback

Alias-based serving makes rollback cheap:

1. keep the previous good version in the registry
2. reassign `production` to that version
3. leave the application image untouched

That is safer than rebuilding or redeploying the whole service because the
serving contract does not change.

## Interview Questions

1. What problem does a model registry solve?
2. Why are aliases better than hard-coding version numbers?
3. How do aliases make rollback safer?
4. What metadata belongs in a registry entry?
5. How does a registry help with model governance?
6. When would you still keep local or GCS artifacts?
