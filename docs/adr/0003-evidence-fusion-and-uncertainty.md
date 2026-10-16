# ADR 0003: Evidence Fusion, Uncertainty, and Multimodal Provenance

## Status
Accepted

## Date
2026-10-16

## Context
A major pitfall in automated video highlight platforms is relying on an end-to-end "black-box" deep learning model to classify whether a video segment is a highlight. 

Such approaches suffer from critical flaws in production:
1. **Uncertainty & Hallucinations:** When a black-box model misclassifies a mundane respawn as an epic clutch, developers cannot diagnose why the decision was made.
2. **Brittle Calibration:** A minor game update (e.g., UI color palette changes or new character skins in Brawl Stars) degrades the entire model's predictions.
3. **High Compute Costs:** Running heavy end-to-end video transformers over hours of high-resolution gameplay is economically prohibitive and slow.
4. **Lack of Provenance:** Content creators reject automated suggestions if they cannot see the justification or adjust the sensitivity of individual signals.

## Decision
We reject end-to-end black-box video classification in favor of a **Modular, Calibrated Bayesian Evidence Fusion Architecture**:

1. **Independent Multimodal Detectors:** Specialized, lightweight detectors extract signals independently:
   - *Audio Modality:* RMS energy spikes, spectral flux, game stinger audio matches.
   - *Visual Modality:* Scene cuts, color histograms, HUD template matching (Showdown skull, overtime banner).
   - *OCR Modality:* Text recognition on elimination feeds and score counters.
2. **Calibrated Confidence Scoring:** Each detector outputs a normalized confidence score $c \in [0.0, 1.0]$ with empirical probability calibration (Platt scaling / isotonic regression).
3. **Bayesian Evidence Combination:** Observations overlapping within a temporal window are aggregated using log-odds additive evidence fusion. No highlight is declared from a single weak signal.
4. **Immutable Evidence Provenance:** Every detected candidate retains an explicit `evidence_payload` capturing the contributing detectors, feature values, raw text, and timestamps.
5. **Explainability in Studio UI:** The creator UI displays confidence breakdowns and contributing signals for every candidate, enabling creators to tune detector thresholds.

```
[ Audio RMS Spike ] ────┐
(conf: 0.82)            │
                        ▼
[ HUD Kill Banner ] ──► [ Calibrated Bayesian Fusion ] ──► [ Event: TRIPLE_KILL ]
(conf: 0.94)            │ (Log-odds aggregation)           (Confidence: 0.96)
                        ▲                                  (Provenance: Full Audit Trail)
[ OCR Player Text ] ────┘
(conf: 0.90)
```

## Consequences

### Positive
- **High Explainability:** Clear, interpretable root cause for every highlight proposal.
- **Robust Fallback:** If OCR fails due to unusual resolution, audio energy spikes and visual motion still identify exciting moments.
- **Extensible to Other Games:** Adding a new game requires defining UI bounding boxes and sound profiles rather than retraining an entire deep neural network.
- **Tunable by Creators:** Creators can set preferences (e.g., "prioritize clutch voice excitement over objective gem count").

### Negative / Trade-offs
- Requires maintaining heuristic detector rules and bounding box definitions per game profile.
- Initial calibration requires establishing ground-truth validation datasets.
