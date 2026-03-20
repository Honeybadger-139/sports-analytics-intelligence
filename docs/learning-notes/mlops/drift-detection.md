# Drift Detection With KL Divergence

## What Is Prediction Drift?

Prediction drift happens when the distribution of model outputs changes over
time. In this project we monitor the model's predicted win probabilities and
compare a recent live window with an earlier baseline window.

That is useful because the model can start behaving differently before the
final accuracy score visibly drops.

## Why Use KL Divergence?

KL divergence measures how far one probability distribution is from another.
For drift monitoring, it gives us a compact way to compare:

- baseline prediction probabilities
- live prediction probabilities

We use the symmetric form so the score is easier to interpret and does not
depend on which window is treated as the reference.

## Why A 10-Bin Histogram?

Raw probabilities are continuous, so we bucket them into 10 bins from 0.0 to
1.0. That keeps the comparison stable and simple enough for production
monitoring.

## Why The 0.1 Threshold?

The threshold is a practical guardrail rather than a universal law. A score
above 0.1 means the live prediction shape has shifted enough to justify a
closer look.

In practice, the threshold should be tuned against historical behavior and
business tolerance for false alarms.

## Drift vs Accuracy

- Accuracy tells us whether predictions were right after games finish.
- Drift tells us whether the model's output distribution is changing now.

That makes drift an early warning signal, while accuracy is the outcome check.

## What To Do When Drift Is Detected

Typical follow-up actions include:

- inspect recent prediction examples
- compare live and baseline probability histograms
- check whether raw features also drifted
- decide whether a retrain or manual review is needed

## Interview Questions

1. What is prediction drift?
2. Why compare distributions instead of raw accuracy?
3. What does KL divergence measure in plain English?
4. Why do we use histograms for probability drift?
5. What is the difference between drift detection and performance monitoring?
6. When would you choose PSI, KL divergence, or another drift metric?
