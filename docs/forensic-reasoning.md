 DamageScope AI Forensic Reasoning Framework

 Overview

DamageScope AI is designed around a simple but critical principle:

> A conclusion is only as strong as the evidence supporting it.

Many image-analysis systems focus primarily on classification. They attempt to answer:

> “What does this image show?”

DamageScope AI is designed to go further by asking:

> “What evidence supports each possible conclusion, what alternative explanations exist, and what limitations prevent a stronger finding?”

This evidence-first approach is intended to help property professionals create more consistent, transparent, reviewable, and defensible inspection findings.

The system is not intended to replace a qualified inspector, adjuster, engineer, contractor, consultant, or other professional. It is designed to preserve and strengthen professional judgment through structured reasoning, evidence traceability, expert review, and permanent correction records.



 1. Purpose of the Forensic Reasoning Engine

The DamageScope AI Forensic Reasoning Engine is intended to:

* Identify the building component shown in the evidence
* Determine the component’s location and material
* Separate observable conditions from interpretations
* Generate multiple plausible candidate findings
* Compare each candidate against the available evidence
* Identify missing or conflicting evidence
* Reject unsupported conclusions
* Preserve confidence and limitations
* Request clarification when the evidence is insufficient
* Present the most defensible finding for expert review
* Store corrections so repeated mistakes can be tested and prevented

The goal is not merely to memorize thousands of labeled images.

The goal is to apply a repeatable reasoning strategy to both familiar and unfamiliar inspection conditions.



 2. Core Reasoning Principle

The forensic reasoning process follows this sequence:

```text
Identify the component
        ↓
Confirm the location and material
        ↓
Record observable conditions
        ↓
Evaluate evidence quality
        ↓
Generate candidate explanations
        ↓
Test each candidate
        ↓
Identify supporting and conflicting evidence
        ↓
Reject unsupported candidates
        ↓
Record confidence and limitations
        ↓
Present finding for expert review
        ↓
Preserve correction or approval
```

This structure helps prevent the system from jumping directly from an image to an unsupported conclusion.



 3. Observation Versus Conclusion

DamageScope AI separates what is directly observable from what is inferred.

 Observation

An observation describes what can be seen, measured, or documented.

Examples:

* A localized circular depression is visible.
* Granules are displaced from the shingle surface.
* A linear crease crosses the shingle tab.
* Moisture staining is present on the ceiling.
* Corrosion is visible around the fastener.
* The siding panel is displaced from the wall.
* A fracture extends through the material.
* Four isolated depressions are visible on the downspout.

 Interpretation

An interpretation explains what the observation may mean.

Examples:

* The depression may be consistent with impact deformation.
* The crease may be consistent with wind uplift.
* The staining may be consistent with prior moisture intrusion.
* The fracture may be consistent with mechanical loading.
* The displacement may indicate installation failure or external force.

 Conclusion

A conclusion is the expert-reviewed finding supported by the evidence.

Example:

> Four localized depressions are visible on the aluminum downspout. Their isolated shape and repeated appearance from multiple viewing angles are consistent with impact-related deformation. The precise cause cannot be conclusively established from the photographs alone.

This structure allows the report to remain accurate without overstating certainty.



 4. Component Identification

Damage cannot be evaluated reliably until the building component has been identified.

The reasoning engine first attempts to determine:

* Component type
* Material
* Location
* Orientation
* Relationship to adjacent components
* Condition of the overall assembly

Examples of components include:

 Roofing

* Asphalt shingles
* Ridge caps
* Starter shingles
* Underlayment
* Drip edge
* Flashing
* Valleys
* Pipe jacks
* Roof vents
* Chimney caps
* Coping
* Scuppers
* Parapet walls
* Rolled roofing
* TPO roofing
* Tile roofing
* Wood or cedar roofing

 Exterior

* Gutters
* Downspouts
* Siding
* Fascia
* Soffit
* Window screens
* Window frames
* Exterior doors
* Trim
* HVAC equipment
* Fencing
* Decks
* Exterior lighting

 Interior

* Drywall
* Ceilings
* Flooring
* Carpet
* Trim
* Cabinets
* Countertops
* Doors
* Windows
* Insulation
* Framing
* Electrical components
* Plumbing components
* HVAC components

A component misclassification can create an incorrect damage classification, so expert review remains required.



 5. Observable Condition Categories

The engine records visible conditions before evaluating cause.

Examples include:

* Depression
* Dent
* Fracture
* Crack
* Split
* Tear
* Crease
* Granule displacement
* Granule loss
* Surface abrasion
* Discoloration
* Moisture staining
* Corrosion
* Separation
* Displacement
* Missing material
* Puncture
* Deformation
* Spatter
* Delamination
* Biological growth
* Prior repair
* Manufacturing characteristic
* Installation condition
* Normal wear
* Age-related deterioration

Recording conditions separately from cause helps preserve neutrality.



 6. Candidate Finding Generation

After documenting observable conditions, the system generates multiple plausible explanations.

Example:

```text
Component:
Asphalt shingle

Observable condition:
Localized granule displacement and surface depression

Candidate findings:
1. Hail-related impact
2. Mechanical abrasion
3. Foot traffic
4. Manufacturing variation
5. Age-related granule loss
6. Installation-related damage
```

The system should not select the first plausible answer automatically.

Each candidate must be tested against the available evidence.



 7. Evidence Classification

Evidence associated with a candidate finding may be classified as:

* Supporting
* Conflicting
* Missing
* Inconclusive
* Duplicate
* Irrelevant
* Low quality
* Unverified

 Supporting Evidence

Evidence that strengthens a candidate explanation.

Example:

* Multiple isolated depressions
* Similar conditions visible from two angles
* Material response consistent with impact
* Pattern inconsistent with a continuous installation fold

 Conflicting Evidence

Evidence that weakens a candidate explanation.

Example:

* Condition follows a manufacturing line
* Damage exists only at fastener locations
* Surface wear is uniform rather than localized
* The pattern continues across multiple components
* The photograph does not show deformation from another angle

 Missing Evidence

Evidence that would normally be needed to support the conclusion.

Example:

* No wide-angle context photograph
* No second viewing angle
* No measurement
* Material not confirmed
* Location not documented
* No comparison with an undamaged area
* No weather or event history



 8. Candidate Evaluation

Each candidate is evaluated against structured questions.

 Component Match

* Is the component correctly identified?
* Is the material confirmed?
* Is the observed response plausible for this material?

 Pattern Match

* Does the shape match the proposed mechanism?
* Is the condition localized or continuous?
* Is the pattern random, directional, repeated, or uniform?
* Is the condition visible from more than one angle?

 Location Match

* Is the condition located where the proposed cause would reasonably occur?
* Is the location associated with installation stress, wear, impact exposure, or water movement?

 Context Match

* Are nearby components affected?
* Does the surrounding area support or contradict the proposed finding?
* Is there evidence of previous repairs?
* Is there evidence of normal wear or manufacturing variation?

 Evidence Quality

* Is the photograph clear?
* Is the relevant area in focus?
* Is scale or measurement available?
* Is the lighting sufficient?
* Is the viewing angle adequate?
* Is the component partially blocked?

 Causation Limits

* Can the cause be established from the photograph alone?
* Is additional inspection required?
* Is an engineer, manufacturer, or specialist needed?
* Is the evidence sufficient only for a condition statement?



 9. Rejection of Unsupported Conclusions

A candidate should be rejected when:

* The visible pattern does not match the proposed mechanism
* The component is incorrectly identified
* The image quality is insufficient
* Required context is missing
* Conflicting evidence is stronger than supporting evidence
* The conclusion depends on facts not present in the record
* The proposed wording overstates certainty
* The finding cannot be distinguished from normal wear
* The condition is more consistent with installation or manufacturing characteristics
* The system lacks enough information to reach a reliable conclusion

Rejected candidates should remain traceable in the internal evidence record.

This allows reviewers to understand what was considered and why it was rejected.



 10. Clarification and Additional Evidence

When the available evidence is insufficient, DamageScope AI should request clarification instead of manufacturing certainty.

Possible requests include:

* Closer photograph
* Wider context photograph
* Second angle
* Opposite-side photograph
* Measurement
* Material confirmation
* Component location
* Date of installation
* Repair history
* Weather history
* Moisture reading
* Interior correlation
* Attic photograph
* Roof slope or pitch
* Manufacturer information
* Specialist review

Example:

> The current photograph shows a localized surface condition, but the image does not provide enough context to distinguish impact damage from mechanical abrasion. Please provide a closer image, a wider context image, and an alternate angle.



 11. Confidence and Limitations

Confidence represents the strength of the evidence supporting a proposed finding.

Confidence should not be treated as proof.

Factors affecting confidence include:

* Image clarity
* Number of supporting photographs
* Component identification certainty
* Material identification certainty
* Presence of measurements
* Pattern consistency
* Availability of comparison evidence
* Strength of alternative explanations
* Expert confirmation
* Completeness of inspection context

 Example Confidence Language

 Higher Confidence

> The condition is visible from multiple angles, the component and material are confirmed, and the observed pattern is strongly consistent with localized impact deformation.

 Moderate Confidence

> The observed condition may be consistent with impact deformation, but additional context and comparison photographs would strengthen the finding.

 Low Confidence

> The photograph shows a possible surface irregularity, but image quality and limited context prevent a reliable classification.

 Limitation Language

Examples:

* Cause cannot be conclusively established from the photograph alone.
* Additional field inspection is recommended.
* The area is partially obstructed.
* No measurement was available.
* Material type has not been verified.
* The condition may have multiple plausible causes.
* Weather history was not evaluated.
* The photograph does not establish when the condition occurred.



 12. Expert Review

Every AI-assisted finding should be subject to professional review.

The reviewer may:

* Approve the finding
* Approve with revised wording
* Correct the component
* Correct the location
* Correct the damage classification
* Correct the cause assessment
* Add limitations
* Reject the finding
* Request additional evidence
* Escalate to an engineer or specialist

 Expert Review Flow

```text
AI-Assisted Finding
        ↓
Professional Review
        ├── Approve
        ├── Revise
        ├── Correct
        ├── Reject
        ├── Request Evidence
        └── Escalate
```

The expert-approved result becomes the controlling finding.



 13. Learning From Corrections

DamageScope AI is designed to preserve every meaningful correction.

A correction record may include:

* Original AI prediction
* Original confidence
* Original component classification
* Original damage classification
* Expert correction
* Approved wording
* Reason for correction
* Supporting evidence
* Conflicting evidence
* Reviewer
* Date
* Failure category
* Regression-test status

 Example

```text
Original prediction:
Installation crease

Expert correction:
Localized impact-related deformation

Reason:
The condition consists of multiple isolated circular depressions rather than one continuous fold.

Approved wording:
Multiple localized depressions are visible on the aluminum downspout and are consistent with impact-related deformation.
```

This record can later become a targeted evaluation.



 14. Regression Testing

A corrected mistake should become a permanent test case whenever practical.

 Regression Test Structure

```text
Test ID
Component
Evidence files
Original failure
Expected component
Expected observation
Expected candidate findings
Rejected candidate
Required limitation
Approved wording
Pass or fail status
```

 Example Regression Test

```text
Test ID:
DSAI-DOWNSPOUT-001

Original failure:
Localized downspout depressions classified as installation creases

Expected component:
Aluminum downspout

Expected observation:
Multiple localized circular depressions

Expected candidate:
Impact-related deformation

Rejected candidate:
Continuous installation crease

Required limitation:
Precise cause cannot be established from photographs alone
```

The test passes only when the corrected behavior remains intact.



 15. Evidence Graph Integration

Each reasoning result should remain connected to its source evidence.

```text
Claim
  ↓
Property
  ↓
Location
  ↓
Component
  ↓
Photograph
  ↓
Observation
  ↓
Candidate Finding
  ↓
Evidence Evaluation
  ↓
Expert Decision
  ↓
Approved Finding
  ↓
Report Language
  ↓
Learning Record
```

This allows the system to answer:

* Which photograph supports this finding?
* Who approved the finding?
* What was the original AI prediction?
* What evidence was missing?
* Which alternatives were rejected?
* Where does the finding appear in the report?
* Has the same failure occurred before?



 16. Example Forensic Analysis: Downspout

 Component

Aluminum downspout

 Location

Rear elevation

 Observable Condition

Four localized circular depressions are visible.

 Candidate Findings

1. Impact-related deformation
2. Installation crease
3. Handling damage
4. Manufacturing variation

 Supporting Evidence

* Depressions are isolated rather than continuous
* Similar deformation is visible from more than one angle
* Shape is consistent across multiple locations
* No continuous fold is visible

 Conflicting Evidence

* No impact event is directly documented
* No measurement is available

 Rejected Candidate

Installation crease

 Reason for Rejection

Installation creases are typically linear or continuous. The observed conditions are separate localized depressions.

 Proposed Finding

> Multiple localized depressions are visible on the aluminum downspout and are consistent with impact-related deformation.

 Limitation

> The precise cause and date of occurrence cannot be conclusively established from the photographs alone.



 17. Example Forensic Analysis: Asphalt Shingle

 Component

Asphalt composition shingle

 Observable Condition

Localized granule displacement with a central surface depression

 Candidate Findings

1. Hail-related impact
2. Mechanical abrasion
3. Foot traffic
4. Manufacturing variation
5. Age-related granule loss

 Supporting Evidence for Impact

* Localized rather than uniform pattern
* Central depression
* Granule displacement concentrated around one location
* Similar conditions on adjacent shingles

 Conflicting Evidence

* No scale or measurement
* Mat fracture not confirmed
* Single image angle

 Required Clarification

* Close-up photograph
* Wider roof context
* Alternate angle
* Comparison photograph
* Material flexibility inspection when appropriate

 Proposed Finding

> The shingle exhibits a localized area of granule displacement and surface depression that may be consistent with impact. Additional inspection is required to distinguish impact damage from mechanical abrasion or age-related wear.



 18. Example Forensic Analysis: Wind-Uplift Crease

 Component

Asphalt shingle tab

 Observable Condition

Linear crease extending across the shingle tab

 Candidate Findings

1. Wind-uplift deformation
2. Installation handling damage
3. Foot traffic
4. Thermal movement

 Supporting Evidence

* Crease is located near the shingle seal area
* Tab appears lifted or displaced
* Crease orientation is consistent with bending
* Adjacent tabs may show similar uplift

 Conflicting Evidence

* No documentation of seal failure
* No weather data
* No underside inspection

 Proposed Finding

> A linear crease is visible across the shingle tab and is consistent with bending or uplift deformation. Additional field inspection is recommended to evaluate seal condition and determine whether the condition is consistent with wind-related movement.



 19. Example Forensic Analysis: Interior Moisture Staining

 Component

Interior ceiling drywall

 Observable Condition

Irregular brown discoloration and staining

 Candidate Findings

1. Prior roof leak
2. Plumbing leak
3. HVAC condensation
4. Historical moisture event
5. Surface contamination

 Supporting Evidence

* Staining pattern
* Location below roof or plumbing assembly
* Possible moisture-related discoloration

 Missing Evidence

* Moisture reading
* Attic inspection
* Plumbing inspection
* Roof inspection correlation
* Date of occurrence

 Proposed Finding

> Irregular moisture-related staining is visible on the ceiling surface. The photograph documents evidence of a prior or active moisture condition but does not establish the source. Further inspection of the roof, attic, plumbing, and HVAC systems is recommended.



 20. Safety and Red Alerts

Some findings require immediate escalation.

Examples include:

* Structural instability
* Active electrical hazard
* Severe displacement
* Potential collapse
* Active water intrusion near electrical systems
* Gas-related concern
* Significant foundation movement
* Unsafe roof access
* Unsupported heavy materials
* Dangerous biological contamination
* Missing critical evidence in a high-risk inspection

When a red alert condition is identified, the system should:

1. Stop the normal workflow when appropriate.
2. Display a clear warning.
3. Identify the supporting evidence.
4. Recommend professional or emergency review.
5. Record the alert in the inspection file.
6. Prevent unsupported finalization.



 21. Customer-Facing Language

Customer-facing reports should avoid exposing internal technical fields unnecessarily.

The report should focus on:

* Component
* Location
* Observable condition
* Damage type
* Evidence summary
* Detailed finding
* Approved annotation
* Limitation
* Recommended action

Internal fields such as raw model confidence, internal candidate scores, failure IDs, and regression-test identifiers should remain in the internal record unless disclosure is required.



 22. Responsible AI Use

DamageScope AI is an assistive platform.

It should not:

* Automatically determine insurance coverage
* Automatically approve or deny claims
* Replace engineering analysis
* Replace professional inspection
* Make unsupported causal conclusions
* Conceal uncertainty
* Present planned features as completed
* Remove expert responsibility

It should:

* Preserve evidence
* Identify uncertainty
* Explain reasoning
* Support professional review
* Record corrections
* Improve documentation
* Maintain traceability
* Request clarification when needed



 23. Contest Demonstration

The contest build should demonstrate this simplified reasoning flow:

```text
Select Photograph
        ↓
Identify Component
        ↓
Record Observable Condition
        ↓
Generate Candidate Finding
        ↓
Show Supporting Evidence
        ↓
Display Limitation
        ↓
Expert Corrects or Approves
        ↓
Learning Record Saved
        ↓
Approved Finding Added to Report
```

The demonstration does not need to prove large-scale autonomous learning.

It should prove that the system:

* Structures evidence
* Generates reviewable findings
* Preserves expert control
* Stores corrections
* Connects findings to reports



 24. Success Criteria

The forensic reasoning engine is successful when:

* The component is identified correctly
* Observable facts are recorded separately from conclusions
* Multiple plausible explanations are considered
* Unsupported candidates are rejected
* Limitations are stated clearly
* Expert correction is available
* The correction is stored permanently
* The final report uses approved wording
* The result can be traced back to the source evidence
* Previously corrected mistakes can be retested



 25. Final Principle

DamageScope AI is not designed to make the professional unnecessary.

It is designed to make professional reasoning:

* More consistent
* More visible
* More defensible
* More traceable
* More repeatable
* More teachable

> The system does not simply try to identify the answer. It preserves the evidence, tests the alternatives, explains the limitations, and keeps the professional in control of the final finding.
