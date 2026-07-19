 DamageScope AI Demo Instructions

 OpenAI Build Week 2026 Contest Build

These instructions explain how to launch and evaluate the DamageScope AI contest demonstration.

DamageScope AI is an AI-assisted forensic building inspection and documentation platform designed to convert inspection photographs and structured property information into an organized, reviewable evidence record and professional report.

The contest demonstration focuses on one stable end-to-end workflow:

```text
Open Inspection
      ↓
Import Photos
      ↓
Organize Evidence
      ↓
Run AI-Assisted Analysis
      ↓
Review Structured Finding
      ↓
Apply Expert Correction or Approval
      ↓
Generate Final Report
```



 1. Demonstration Objective

The objective of this demonstration is to show how DamageScope AI can take a prepared property-inspection photo set and convert it into:

* An organized inspection record
* Structured building-component findings
* Evidence-linked observations
* Expert-reviewed conclusions
* A professional final report

The demonstration is not intended to show every planned DamageScope AI capability.

Only stable, tested contest-build functions should be used.



 2. Contest Build Information

Update this section before final submission.

Application version: `[INSERT CONTEST BUILD VERSION]`

Build date: `[INSERT BUILD DATE]`

Tested operating system: `[INSERT VERIFIED WINDOWS VERSION]`

Python version: `[INSERT VERIFIED PYTHON VERSION]`

Primary launch file: `[INSERT VERIFIED ENTRY FILE]`

Sample inspection location:

```text
sample_data/demo_inspection/
```

Sample photographs location:

```text
sample_data/demo_photos/
```

Expected sample report location:

```text
reports/sample-report.pdf
```



 3. System Requirements

The following requirements must be verified before publication.

* Windows `[INSERT VERSION]`
* Python `[INSERT VERSION]`
* Git
* Internet connection for live OpenAI analysis
* Valid OpenAI API credentials when live AI analysis is enabled
* PDF viewer
* At least `[INSERT MEMORY REQUIREMENT]` RAM
* At least `[INSERT DISK SPACE REQUIREMENT]` available storage



 4. Repository Setup

 Clone the Repository

Open Visual Studio Code.

Go to Visual Studio Code → CMD PowerShell.

Run:

```powershell
git clone [INSERT REPOSITORY URL]
```

Then run:

```powershell
cd DamageScope-AI
```



 Create a Python Virtual Environment

In Visual Studio Code → CMD PowerShell, run:

```powershell
python -m venv .venv
```

Activate the environment:

```powershell
.\.venv\Scripts\Activate.ps1
```



 Install Required Packages

Run:

```powershell
python -m pip install --upgrade pip
```

Then run:

```powershell
pip install -r requirements.txt
```

The `requirements.txt` file must be updated with the exact verified dependencies before the final contest submission.



 5. OpenAI Configuration

DamageScope AI may require an OpenAI API key for live AI-assisted analysis.

Never add a real API key directly to the repository.

Create a local file named:

```text
.env
```

Add:

```text
OPENAI_API_KEY=your_api_key_here
```

The `.env` file should remain excluded by `.gitignore`.

If the contest build uses another configuration method, replace this section with the actual verified steps.



 6. Launch the Application

Go to Visual Studio Code → CMD PowerShell.

Run the verified launch command:

```powershell
python [INSERT VERIFIED ENTRY FILE]
```

Example only:

```powershell
python main.py
```

Do not leave the example command in the final document unless `main.py` is the actual contest-build entry point.

A successful launch should display the DamageScope AI main interface without errors.



 7. Prepared Demo Inspection

The demonstration should use fictional, synthetic, creator-owned, publicly licensed, or permission-cleared data.

The prepared inspection should contain:

* Fictional claim number
* Fictional customer name
* Fictional property address
* Prepared exterior photographs
* At least one clearly identifiable building component
* At least one structured damage finding
* At least one expert correction or approval
* A completed sample report

Do not use:

* Real customer information
* Real insurance-policy numbers
* Confidential claim files
* Private addresses
* API keys
* Passwords
* Restricted photographs



 8. Recommended Demo Photo Set

Use a small, reliable set of photographs rather than a large inspection.

Recommended set:

1. Address-verification or mailbox photograph
2. Front-elevation photograph
3. Right-elevation photograph
4. Rear-elevation photograph
5. Left-elevation photograph
6. Close-up of a damaged component
7. Alternate view of the same component
8. Context photograph
9. Additional evidence photograph
10. Optional undamaged comparison photograph

The photo set should support a clear evidence-based finding.



 9. End-to-End Demo Procedure

 Step 1 — Launch DamageScope AI

Start the application using the verified contest-build command.

Confirm:

* The application opens
* No error message appears
* The main interface is readable
* The contest build version is visible when applicable



 Step 2 — Open the Prepared Inspection

Open the prepared fictional inspection.

Confirm that the inspection contains:

* Claim information
* Property information
* Inspection date
* Inspector or reviewer information
* Existing or empty evidence areas
* Report status

Do not spend excessive demo time entering information manually.

The contest demonstration should use a prepared inspection whenever possible.



 Step 3 — Import the Demo Photographs

Open the photo-import function.

Select the prepared photo set from:

```text
sample_data/demo_photos/
```

Import the photographs.

Confirm:

* Every selected photo appears
* Images are readable
* Original aspect ratios are preserved
* No duplicate or corrupted files appear
* The application records the imported photo count



 Step 4 — Show Evidence Organization

Display the organized photo grid or evidence list.

Show how photographs are associated with:

* Inspection step
* Elevation
* Room
* Location
* Building component
* Review status
* AI-analysis status

The purpose of this step is to prove that DamageScope AI creates an organized evidence record rather than leaving the user with an unnamed folder of photographs.



 Step 5 — Select the Demonstration Photograph

Choose one clear photograph for AI-assisted analysis.

The selected image should show a component and condition that the contest build can evaluate reliably.

Recommended demonstration examples include:

* Downspout deformation
* Gutter impact deformation
* Asphalt-shingle condition
* Roof-component damage
* Window-screen damage
* Siding condition
* Interior moisture staining

Use only a finding that has been tested successfully before recording.



 Step 6 — Run AI-Assisted Analysis

Start the AI-assisted analysis.

Confirm that the system returns structured information such as:

* Building component
* Material
* Location
* Observable condition
* Candidate damage type
* Supporting evidence
* Confidence
* Limitations
* Recommended review action

The analysis should not simply provide a generic paragraph.

The demonstration should show that the output is organized into fields or evidence objects.



 Step 7 — Show Evidence-First Reasoning

Show how the system connects the proposed finding to visible evidence.

The reasoning should address:

1. What component is shown?
2. Where is it located?
3. What condition is directly visible?
4. What candidate explanations were considered?
5. Which evidence supports the proposed finding?
6. Is there conflicting or missing evidence?
7. What limitations apply?
8. Why is the final candidate more defensible than the alternatives?

Example:

```text
Component:
Aluminum downspout

Observed condition:
Multiple localized circular depressions

Candidate finding:
Impact-related deformation

Supporting evidence:
- Isolated depressions rather than a continuous crease
- Similar deformation visible from more than one angle
- No obvious installation fold at the affected locations

Limitation:
Cause cannot be conclusively established from one photograph alone
```



 10. Expert Review Demonstration

The professional user must remain in control.

Show one of the following actions:

* Approve the AI-assisted finding
* Correct the component
* Correct the damage classification
* Revise the wording
* Reject the finding
* Request additional evidence

The best demonstration includes one correction.

Example:

```text
Original AI wording:
Hail damage to aluminum downspout

Expert-approved wording:
Localized depressions are consistent with impact-related deformation.
```

This demonstrates responsible professional control and defensible language.



 11. Learning Record Demonstration

After the expert correction or approval, show that the system preserves:

* Original AI prediction
* Original confidence
* Expert correction
* Approved finding
* Reason for correction
* Evidence reference
* Date or record identifier
* Review status

The contest build does not need to retrain a large model live.

It should prove that the correction is stored as a durable learning record rather than being lost.

The intended future cycle is:

```text
Prediction
   ↓
Correction
   ↓
Learning Record
   ↓
Evaluation
   ↓
Regression Test
```



 12. Quality-Control Demonstration

Run or display the quality-control review.

Show at least one check such as:

* Missing required photo
* Missing finding evidence
* Unresolved correction
* Incomplete inspection step
* Unsupported conclusion
* Inaccessible area
* Missing report field

The quality-control screen should demonstrate that the platform does not allow an inspection to be finalized without review.



 13. Generate the Final Report

Select the report-generation function.

Generate the demonstration report.

Confirm:

* The report is created successfully
* The PDF opens
* Photographs appear clearly
* Findings are connected to the correct photos
* Approved wording is used
* Internal technical fields are not exposed unnecessarily
* Private or fictional demonstration data is handled correctly

The final report is the primary visual payoff of the demonstration.



 14. Report Review Checklist

Verify that the report includes the contest-build items that are actually supported:

* [ ] Project or inspection title
* [ ] Property or claim information
* [ ] Address-verification photograph
* [ ] Exterior-elevation sequence
* [ ] Building-component identification
* [ ] Observable conditions
* [ ] Structured findings
* [ ] Approved annotations
* [ ] Supporting evidence
* [ ] Inspection limitations
* [ ] Inaccessible areas
* [ ] Quality-control status
* [ ] Reviewer approval

Do not claim unsupported sections are included.



 15. Persistence Test

Close the application.

Restart DamageScope AI.

Reopen the prepared inspection.

Confirm that the following remain saved:

* Imported photographs
* Inspection information
* Structured findings
* Expert corrections
* Review status
* Learning records
* Report reference

Failure to preserve inspection information after closing and reopening should be treated as a contest-blocking defect.



 16. Expected Demo Result

A successful demonstration should prove that DamageScope AI can:

* Open a structured inspection
* Import inspection photographs
* Organize evidence
* Identify a building component
* Record an observable condition
* Generate a structured candidate finding
* Connect the finding to supporting evidence
* Preserve uncertainty and limitations
* Allow expert correction or approval
* Store a learning record
* Generate a professional report
* Reopen the saved inspection successfully



 17. Demo Video Sequence

The public contest video must remain under three minutes.

Recommended sequence:

| Time      | Demonstration                              |
|  |  |
| 0:00–0:20 | Creator introduction and industry problem  |
| 0:20–0:40 | Open prepared inspection                   |
| 0:40–1:05 | Import and organize photographs            |
| 1:05–1:35 | Run AI-assisted analysis                   |
| 1:35–1:55 | Show expert correction and learning record |
| 1:55–2:25 | Run quality control and generate report    |
| 2:25–2:45 | Explain GPT-5.6 and Codex use              |
| 2:45–2:55 | Closing impact statement                   |

The demonstration should tell one clear story instead of touring every available button.



 18. Recommended Narration

 Opening

> My name is Danny Hill. I am an insurance adjuster and property-damage professional, not a software engineer. I built DamageScope AI with OpenAI because inspectors need a faster and more consistent way to capture evidence and turn it into a defensible report.

 Inspection Workflow

> DamageScope AI begins with a structured claim and property record. Inspection photographs are imported and organized by location, elevation, and building component so the user is not starting with an unorganized folder of pictures.

 AI-Assisted Finding

> GPT-5.6 assists with identifying the component and observable condition. DamageScope AI then creates a structured finding that connects the conclusion to its supporting evidence, confidence, and limitations.

 Expert Review

> The professional remains in control. The reviewer can correct, approve, or reject the proposed result. The original prediction and approved correction are preserved as a learning record.

 Report

> The system generates a professional report that connects the property, photographs, observations, findings, annotations, limitations, and quality-control review.

 OpenAI Role

> I supplied the field knowledge, inspection standards, and product decisions. GPT-5.6 and Codex helped translate those requirements into working software, debug the workflow, and iterate quickly.

 Closing

> DamageScope AI shows what happens when real industry experience meets modern AI: better evidence, clearer reports, and a more consistent inspection process.



 19. Do Not Demonstrate

Do not show:

* Unstable experimental features
* Screens that frequently crash
* Functions requiring secret manual repairs
* Real customer information
* API keys
* Passwords
* Private email or chat notifications
* Unsupported claims of causation
* Planned functions represented as complete
* Large datasets that slow the demo
* Features unrelated to the core inspection story

Reliability is more important than feature quantity.



 20. Backup Demo Materials

Prepare the following before recording:

* Completed sample report
* Backup screenshots
* Backup annotated photographs
* Backup AI finding
* Backup learning record
* Copy of the narration script
* Screen-by-screen click list
* Full project backup
* Repository snapshot
* Second recording device when practical

If a live function fails during recording, use only backup material that accurately represents tested contest-build behavior.



 21. Troubleshooting

 Application Does Not Launch

Confirm:

* The virtual environment is active
* Dependencies were installed
* The correct Python version is installed
* The launch command is correct
* The working directory is the repository root

Run:

```powershell
python --version
```

Then:

```powershell
pip list
```



 OpenAI Analysis Does Not Run

Confirm:

* Internet connection is available
* The OpenAI API key is valid
* The `.env` file exists
* The API key has not been committed to GitHub
* The selected model is available
* Error handling displays a readable message



 Photos Do Not Import

Confirm:

* The photo format is supported
* Files are not corrupted
* The selected folder is accessible
* The application has permission to read the files
* The images are not larger than supported limits



 Report Does Not Generate

Confirm:

* The inspection has been saved
* Required fields are complete
* At least one approved finding exists
* The report output folder is writable
* Required PDF packages are installed



 Saved Inspection Does Not Reopen

Do not continue to the final contest recording until this issue is resolved.

Verify:

* The correct inspection folder is being used
* The save operation completed
* Stored file paths remain valid
* The saved data file is not corrupted
* The application is not opening a new blank claim instead of the saved inspection



 22. Final Contest Smoke Test

Complete this checklist before recording:

* [ ] Exact contest build launches
* [ ] Prepared inspection opens
* [ ] Demo photographs import
* [ ] Evidence organization works
* [ ] AI-assisted analysis works
* [ ] Structured findings populate
* [ ] Expert correction saves
* [ ] Learning record is preserved
* [ ] Quality-control review works
* [ ] Report generates
* [ ] PDF opens
* [ ] Inspection persists after restart
* [ ] No customer data is visible
* [ ] No API keys are exposed
* [ ] README installation steps are accurate
* [ ] Repository links work
* [ ] Demo finishes in under three minutes
* [ ] Public YouTube link works in incognito mode



 23. Judge Evaluation Summary

Judges should be able to identify four central strengths:

 Technological Implementation

A functioning AI-assisted inspection workflow built with GPT-5.6 and Codex.

 Design

A structured, professional path from inspection evidence to report.

 Potential Impact

Reduced missed evidence, improved consistency, faster organization, and clearer documentation.

 Quality of the Idea

Evidence-first forensic reasoning, expert-controlled AI, an evidence graph, and durable learning from corrections.



 24. Final Demonstration Principle

The DamageScope AI contest demonstration should prove one central claim:

> DamageScope AI turns scattered inspection evidence into a structured, reviewable, professional forensic record while keeping the qualified professional in control.
