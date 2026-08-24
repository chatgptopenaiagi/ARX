 


You are working on the ARX repository.


Your task is to improve ARX Desktop so that it behaves like a complete, professional, user-friendly Windows 64-bit application, while preserving the existing ARX scanning engine, evidence model, project-awareness logic, safety model, and deterministic behavior.


Primary objective


ARX already focuses strongly on internal correctness, scanning logic, compatibility reasoning, evidence, schemas, and project analysis.


Now perform a dedicated Windows UX completeness pass.


Treat ordinary desktop behaviors as required software functionality, not optional polish.


The application must feel natural to an average Windows programmer who expects normal mouse, keyboard, clipboard, file-navigation, selection, context-menu, dialog, and installer behavior.


---


1. First inspect before changing


Before editing code:


1. Inspect the repository structure.

2. Identify:

   - desktop GUI framework

   - widgets displaying JSON

   - result tables

   - colored scan-result lines

   - text areas

   - path fields

   - error/output panels

   - dialogs

   - report viewers

   - installer/build scripts

3. Determine which UI components currently lack:

   - text selection

   - copy

   - select all

   - context menus

   - keyboard shortcuts

   - file/folder actions

4. Preserve existing ARX architecture unless a change is necessary.


Do not rewrite the ARX engine simply to perform this task.


---


2. Global Windows UX rule


Wherever a user sees meaningful information, ask:


«"What would a normal Windows user reasonably expect to be able to do with this information?"»


Implement those expected actions where technically appropriate.


Examples:


- select

- copy

- copy all

- open

- inspect

- save

- search

- navigate

- reveal location

- view details


Avoid visually dead information surfaces.


---


3. Right-click context menus


Implement representative, context-sensitive right-click menus throughout ARX Desktop.


Do not use the same generic menu everywhere if the object has richer actions available.


Plain text / report text


Provide appropriate actions such as:


- Copy

- Select All

- Copy All

- Find, if practical

- Save As, where useful


JSON report viewer


Provide:


- Copy

- Select All

- Copy All JSON

- Save JSON As...

- Find

- Pretty-print / format only if formatting is not already canonical

- Collapse/expand features only if the current widget supports them cleanly


The user must never be forced to manually drag-select a very large JSON document merely to copy it.


Scan-result lines


For a selected or right-clicked scan result, provide useful actions where applicable:


- Copy line

- Copy details

- Copy value

- Copy path

- Open containing folder

- Open file

- Inspect target in ARX

- View details


Only show actions that make sense for that result.


Paths


For file-system paths, provide as applicable:


- Copy path

- Open

- Open containing folder

- Reveal in File Explorer

- Inspect with ARX


Do not attempt to open paths that do not exist.


Handle missing paths gracefully.


Errors and diagnostics


Provide:


- Copy error

- Copy diagnostic details

- Copy full context

- Select All


If stack traces are visible, allow easy copying.


---


4. Keyboard behavior


Implement standard Windows keyboard behaviors where appropriate.


At minimum review support for:


- Ctrl+C = Copy

- Ctrl+A = Select All

- Ctrl+F = Find, where meaningful

- Ctrl+S = Save current report, where meaningful

- Enter = activate expected default action

- Esc = close dialogs where appropriate

- Tab / Shift+Tab = sensible keyboard navigation


Do not hijack standard shortcuts with surprising behavior.


---


5. Text selection


Review all text-oriented widgets.


Meaningful user-visible text should generally be selectable unless there is a good technical reason not to allow it.


This includes:


- scan output

- status details

- error messages

- diagnostic reports

- JSON

- paths

- compatibility explanations

- project requirement information


Labels used purely as interface decoration do not need selection.


---


6. Double-click behavior


Where natural, implement useful double-click actions.


Examples:


- file path → open or reveal

- directory → open in File Explorer

- scan finding → open detail view

- JSON/result entry → expand details


Avoid surprising destructive actions.


---


7. Colored scan-result rows


ARX uses colored result/status information.


Do not treat these merely as colored visual labels.


Make them interactive information objects where appropriate.


A result row should support:


- selection

- keyboard focus if practical

- copy

- copy details

- context actions

- detail inspection


Color must not be the only carrier of meaning.


Retain textual status such as:


- GREEN

- YELLOW

- RED

- READY

- PARTIAL

- MISSING


as appropriate to the existing ARX model.


---


8. Status bar and user feedback


Review operations that may take noticeable time.


Provide clear state such as:


- Ready

- Scanning...

- Inspecting...

- Export complete

- Copy complete

- Failed

- Cancelled


Where appropriate:


- disable controls temporarily during conflicting operations

- restore them afterward

- keep the GUI responsive

- never freeze the main UI unnecessarily


Preserve ARX's existing worker-thread/background-scan design if already present.


---


9. File dialogs


Use normal Windows-friendly dialogs for actions such as:


- Open project

- Inspect file

- Export report

- Save JSON

- Save text report


Remember the last useful directory during the session if practical.


Use appropriate file filters.


Examples:


- JSON (\*.json)

- Text (\*.txt)

- Executables (\*.exe)

- All files (.)


Do not unnecessarily restrict users.


---


10. Error dialogs


Errors must be understandable.


Avoid dialogs that expose only raw exceptions.


Where possible show:


1. human-readable summary

2. relevant technical details

3. copy-details action


Example:


"ARX could not open this path."


Then optionally:


"Details"


with the underlying exception or diagnostic information.


Do not hide important technical information from advanced users.


---


11. Tooltips and discoverability


Add concise tooltips where buttons or icons may not be obvious.


Avoid excessive tooltip noise.


Prioritize:


- export buttons

- scan modes

- inspect actions

- project selection

- status meanings

- report controls


---


12. Window behavior


Review standard Windows window behavior.


Verify:


- resizable windows

- sensible minimum size

- content does not disappear when resized

- scrollbars appear when needed

- maximized mode works

- high-DPI scaling is acceptable

- text is not clipped

- dialogs stay usable on smaller displays


If practical, persist useful UI state such as:


- window size

- window position

- last selected tab

- splitter positions


Do not persist sensitive information.


---


13. Accessibility basics


Perform a basic accessibility review.


Ensure:


- keyboard navigation works

- focus indication is visible

- color is not the only meaning carrier

- controls have understandable names

- text has sufficient contrast

- important status messages are textual


Do not attempt a huge accessibility-framework rewrite unless needed.


Focus on high-value improvements.


---


14. Clipboard behavior


Create a consistent clipboard strategy.


Clipboard operations must:


- copy exactly what the user expects

- not include hidden secrets

- preserve ARX redaction rules

- avoid copying huge unrelated UI state

- work with Unicode paths and text


When copying structured report information, preserve readable formatting.


---


15. Explorer integration


Where ARX displays real local paths, support Windows Explorer navigation where appropriate.


Examples:


- Open file

- Open directory

- Open containing folder

- Reveal selected file


Use safe OS APIs.


Do not construct unsafe shell command strings from untrusted text.


Preserve ARX's security principles.


---


16. Installer and Windows application completeness


Inspect the current Windows packaging and release process.


If ARX already has an installer system, improve it.


If it currently produces only a portable executable, document what is present and implement installer improvements only where they fit the existing packaging architecture cleanly.


A professional Windows installer should consider:


- application name

- version

- publisher information

- license display where appropriate

- installation directory

- Start Menu entry

- optional desktop shortcut

- upgrade behavior

- uninstall support

- clean removal

- launch ARX option at finish

- architecture indication

- application icon

- executable metadata


Do not add a fake legal agreement.


If the project uses the MIT license, present the actual project license where appropriate instead of inventing terms.


---


17. About dialog


If ARX lacks one, add a simple professional About dialog containing appropriate information such as:


- ARX

- version

- concise description

- license

- project/repository reference where already defined by the project

- copyright information if available


Do not invent ownership or legal claims.


---


18. Menu structure


Review whether ARX Desktop needs a conventional menu structure.


If appropriate, use something similar to:


File


- Open Project

- Inspect File

- Export Report

- Exit


Edit


- Copy

- Select All

- Find


View


- relevant existing view actions only


Help


- About


Do not add empty or useless menus merely to imitate old Windows applications.


---


19. UX consistency


Create common reusable helpers for repeated UI behavior where sensible.


Examples:


- context-menu helper

- clipboard helper

- path action helper

- save-dialog helper

- error-detail dialog

- standard text-widget bindings


Avoid duplicating context-menu logic across many widgets.


Keep the implementation maintainable.


---


20. Security constraints


These UX improvements must not weaken ARX security.


Preserve:


- read-only observation principles

- no execution of unknown scanned targets

- no unsafe shell interpretation

- redaction rules

- credential exclusion

- path safety

- bounded inspection behavior

- existing project safety policies


Opening a file or directory because the user explicitly requests it through the GUI is a user interaction feature.


It must still be implemented safely.


---


21. Testing requirements


Do not consider the task complete merely because the application starts.


Add or extend automated tests where technically practical.


Test UX helper logic and behavior that can be tested without brittle GUI automation.


Examples:


- clipboard formatting helpers

- path validation

- context-action enable/disable logic

- safe Explorer-opening helpers

- export functions

- report-save behavior

- shortcut bindings where practical

- menu creation

- state persistence

- Unicode path handling


Do not write meaningless tests that only verify mocked functions were called.


---


22. Manual Windows UX acceptance checklist


Create a documented manual acceptance checklist for ARX Desktop.


The checklist should include at least:


- right-click JSON

- copy selected JSON

- copy all JSON

- Ctrl+A

- Ctrl+C

- Ctrl+F where implemented

- save report

- right-click result row

- copy result

- copy path

- open containing folder

- inspect file

- resize window

- maximize

- scroll long output

- keyboard navigation

- Unicode path

- nonexistent path

- error copy/details

- DPI scaling

- installer

- uninstall

- upgrade behavior if installer supports it


Put this checklist in an appropriate development/testing document.


---


23. UX regression principle


Add the following engineering principle to the project documentation in an appropriate location:


«ARX correctness includes both analytical correctness and human usability. A result that is technically correct but unnecessarily difficult to inspect, copy, navigate, export, or understand is an incomplete desktop result.»


Use wording consistent with the project's documentation style.


---


24. Definition of Done


This task is complete only when:


1. Core ARX behavior still works.

2. Existing tests pass.

3. New relevant tests pass.

4. JSON output is easy to copy and save.

5. Important text can be selected.

6. Standard clipboard shortcuts work.

7. Context menus exist where users naturally expect them.

8. Paths expose useful safe actions.

9. Colored result rows provide meaningful interaction.

10. Error details can be copied.

11. File dialogs behave naturally.

12. Window resizing and scrolling work correctly.

13. Installer/release behavior has been reviewed and improved where appropriate.

14. Manual UX acceptance documentation exists.

15. Security and redaction behavior remain intact.


---


25. Implementation strategy


Work incrementally.


Prefer:


- small reusable changes

- focused commits

- minimal architectural disruption

- preserving current APIs

- preserving ARX semantic behavior


Do not replace major working systems solely for visual modernization.


Do not introduce large dependencies unless clearly justified.


---


26. Final report


At the end, provide a concise engineering report containing:


UX problems found


List the missing or inconsistent Windows behaviors discovered.


Changes implemented


List the implemented UX improvements.


Files changed


List important files modified.


Tests


Report:


- tests added

- tests changed

- test results


Manual verification


Describe which Windows interactions were manually or structurally verified.


Remaining limitations


Clearly state anything that could not be reliably implemented or tested.


Security review


Confirm that clipboard, path-opening, Explorer integration, export, and context-menu additions do not bypass ARX safety/redaction policies.


---


The guiding idea is:


Do not only make ARX internally intelligent. Make the intelligence comfortable to touch.


A programmer should be able to scan, inspect, select, copy, search, export, navigate, and understand ARX results using familiar Windows behavior without fighting the interface.


27. ARX AI Assistance Bridge, Context-Aware Right-Click Intelligence, Web Research, and Continuous Repository Verification


ARX must evolve from a scanner that only reports findings into a scanner that also lets the user immediately investigate those findings using familiar human actions.


The central interaction model is:


ARX detects something

        ↓

Human sees the result

        ↓

Human right-clicks it

        ↓

ARX offers meaningful actions

        ↓

Copy / Inspect / Ask AI / Ask Codex / Search Web / Open Location


The user should not need to manually copy an obscure error, leave ARX, open another application, reconstruct the machine context, explain the project, and paste everything into an AI system.


ARX already possesses the context.


The new objective is to allow the user to deliberately transmit a safe, relevant, redacted subset of that context to an AI assistant or external research tool.


---


27.1 Human-visible intelligent context menu


For applicable ARX findings, status rows, errors, paths, compatibility conflicts, project requirements, provider-resolution results, JSON objects, and diagnostic messages, extend the right-click context menu.


Where appropriate, expose actions such as:


Copy

Copy Details

Copy Path

Open

Open Containing Folder

Inspect with ARX

────────────────────

Ask AI About This...

Ask ChatGPT About This...

Ask Codex About This...

Explain This Finding

Suggest Safe Fix

Compare With Project Requirements

────────────────────

Search Web About This...

Search Google About This...

Search Exact Error Message...

Search Official Documentation...

────────────────────

View Evidence

View Raw Data


Only display commands that make sense for the selected object.


Do not create enormous context menus containing irrelevant disabled commands.


---


27.2 "Ask ChatGPT About This" concept


ARX should provide an optional AI assistant panel that can receive contextual questions about selected ARX findings.


Examples:


Why is this RED?


Explain this CUDA conflict.


Why did ARX choose this Python interpreter?


Is this PATH resolution dangerous?


What is missing from this project?


Explain this JSON section.


What would be the safest fix?


Why is Visual Studio detected but CMake missing?


What does this compatibility conflict mean?


The user should be able to right-click a finding and visibly select:


Ask ChatGPT About This


ARX should then construct a useful context packet automatically.


Example conceptual packet:


ARX CONTEXT


Selected finding:

Python provider conflict


ARX status:

RED


Project requirement:

Python \>=3.10,\<3.12


Resolved interpreter:

Python 3.13


Other detected interpreter:

Python 3.11


Relevant execution context:

...


Relevant evidence:

...


User question:

Explain why this blocks the project and suggest the safest solution.


Do not dump the entire machine scan unless genuinely necessary.


Use the minimum relevant context.


---


27.3 Supported OpenAI integration architecture


Do not automate, scrape, reverse engineer, or depend on undocumented internal behavior of the ChatGPT web interface or ChatGPT desktop application.


Implement supported integration boundaries.


Prefer an adapter architecture such as:


ARX AI Bridge

│

├── OpenAI API Adapter

│

├── Codex CLI Adapter

│

├── Future AI Provider Adapter

│

└── Browser/Web Search Adapter


Keep the ARX core independent from any one AI provider.


AI integration must remain optional.


ARX itself must continue working without an internet connection, OpenAI account, API key, or Codex installation.


---


27.4 OpenAI API adapter


Provide an optional direct programmatic OpenAI integration using the currently supported OpenAI API.


When configured by the user, ARX may send a redacted diagnostic context and question to the OpenAI API and display the response inside ARX.


The experience may look conceptually like:


┌─────────────────────────────────────────────┐

│ ARX AI Assistant                            │

├─────────────────────────────────────────────┤

│ Finding: Python interpreter conflict        │

│                                             │

│ You: Explain this issue.                    │

│                                             │

│ AI: Your project requires Python ...        │

│                                             │

│ \[Ask follow-up\]                             │

│                                             │

│ Copy   Save   Clear                         │

└─────────────────────────────────────────────┘


Support conversational follow-up where practical.


The user should be able to continue asking questions about the same ARX finding without reconstructing the context manually.


---


27.5 OpenAI credential security


Never hard-code API keys.


Never store OpenAI API keys in:


- source code

- Git

- JSON scan reports

- debug logs

- plaintext configuration committed to the repository

- exported ARX reports


Use an appropriate secure mechanism such as:


- environment configuration

- Windows Credential Manager

- another established operating-system credential facility


Never display the complete secret after configuration.


Never include authentication credentials in diagnostic exports.


Remember that OpenAI API usage and a ChatGPT subscription may have different authentication/billing mechanisms.


Do not falsely treat a ChatGPT subscription as an API key.


---


27.6 Codex CLI integration


ARX should also detect whether the official Codex CLI is installed.


Conceptually:


ARX

 │

 ├── Detect codex executable

 │

 ├── Detect availability

 │

 └── Enable:

        Ask Codex About This


Where a supported non-interactive Codex CLI interface exists, integrate through that documented interface rather than simulating keyboard input into a terminal window.


The implementation may use a supported non-interactive command such as the appropriate current equivalent of:


codex exec


but Codex must first inspect the installed Codex CLI version and current supported command syntax.


Do not blindly assume that historical CLI flags remain valid forever.


---


27.7 Codex execution safety


An ARX question such as:


Ask Codex About This


must default to analysis, not uncontrolled machine modification.


For diagnostic questions, prefer:


- read-only operation

- ephemeral sessions where appropriate

- bounded execution

- explicit working directory

- no arbitrary shell interpolation

- timeout/cancellation support


Do not automatically grant:


danger-full-access


or equivalent unrestricted execution merely because the user clicked "Ask Codex".


Any later feature allowing Codex to modify a project must be explicitly separated from simple diagnostic questioning.


---


27.8 Never invoke Codex through unsafe shell-string construction


Do not build commands such as:


shell("codex exec " + user\_controlled\_text)


Use subprocess APIs with explicit argument arrays.


Treat:


- project names

- paths

- error messages

- package names

- compiler output

- JSON values


as untrusted data.


Do not allow an ARX scan result to become command injection.


---


27.9 ARX → Codex contextual intelligence


When the user selects:


Ask Codex About This


ARX should intelligently provide relevant information such as:


- selected finding

- ARX status

- project requirements

- provider-resolution result

- relevant evidence

- architecture

- tool versions

- execution context

- relevant project path after redaction/approval

- relevant ARX explanation


Do not send thousands of unrelated scan lines.


Implement contextual selection.


Think:


Entire Machine DNA

        ↓

Context Filter

        ↓

Relevant Evidence

        ↓

Redaction

        ↓

AI Prompt


---


27.10 Prompt preview


For external AI communication, provide an optional:


Preview What Will Be Sent


action.


A user should be able to inspect the context packet before transmission.


Example:


Ask ChatGPT About This

        ↓

Preview Context

        ↓

Send


This is especially important because ARX analyzes local development environments.


---


27.11 Privacy boundary


No ARX information should silently leave the computer.


External communication must be initiated by an explicit user action.


Never automatically transmit:


- complete Machine DNA

- usernames

- home-directory names

- private repository contents

- API keys

- authentication tokens

- browser state

- Wi-Fi credentials

- private keys

- environment secrets

- unrelated file contents


Preserve existing ARX redaction conventions such as:


%USERPROFILE%

%PROJECT\_ROOT%


where appropriate.


---


27.12 AI results are advisory, not ARX evidence


This distinction is critical.


ARX deterministic evidence and AI-generated interpretation must remain separate.


Never allow an AI response to silently become:


DECLARED, OBSERVED, INFERRED, or UNKNOWN fact provenance

a semantically or schema-validated ARX relation or decision

GREEN

RED


inside the ARX evidence model.


Present AI responses with an explicit semantic identity such as:


AI ADVISORY

AI EXPLANATION

AI SUGGESTION

UNVERIFIED AI ANALYSIS


ARX evidence remains ARX evidence.


AI interpretation remains AI interpretation.


Conceptually:


ARX fact evidence

    │

    ├── DECLARED

    ├── OBSERVED

    ├── INFERRED

    └── UNKNOWN


ARX relations and decisions

    │

    └── semantic invariants and schema/composed-state validation


AI

    │

    └── ADVISORY


Do not collapse these layers.


---


27.13 Suggest Fix with AI


Provide a context action where appropriate:


Suggest Safe Fix with AI


The AI should receive ARX's actual evidence and constraints.


The requested answer should prioritize:


1. explain the cause

2. identify the shortest remediation

3. preserve working software

4. avoid unnecessary reinstallations

5. avoid destructive commands

6. explain risks

7. distinguish certainty from assumptions


ARX should initially display the recommendation.


It must not automatically execute the recommendation.


---


27.14 Compare with project requirements


For a machine finding, allow:


Compare With Project Requirements


and optionally:


Ask AI to Explain Difference


Example:


Detected:

CUDA 13.x


Project:

Requires CUDA 12.x-compatible stack


ARX:

YELLOW


AI:

Explain whether this matters for this specific project.


This should strengthen ARX's project-aware philosophy rather than turning it into generic chatbot software.


---


27.15 Search Web About This


Provide:


Search Web About This...


for appropriate findings.


Construct a concise search query from relevant information.


Example:


Instead of searching:


RED


search:


Python 3.13 package compatibility error Windows 10 \<package\>


or:


NVIDIA driver \<version\> CUDA \<version\> compatibility


Use the user's default browser.


---


27.16 Search Google About This


Because many programmers naturally use Google during debugging, optionally expose:


Search Google About This


ARX should:


1. generate a concise search string

2. redact private/local information

3. URL-encode the query safely

4. open the user's default browser


Do not scrape Google search-result pages.


Do not embed undocumented automated Google scraping.


Opening a normal user-initiated search in the browser is sufficient.


---


27.17 Search exact error


For errors, provide:


Search Exact Error Message


When appropriate, preserve the meaningful error fragment while removing:


- local usernames

- absolute private paths

- tokens

- machine-specific secrets

- irrelevant random identifiers


Example:


"CMake could not find CUDA compiler"


may be more useful than transmitting an entire 500-line diagnostic dump.


---


27.18 Official documentation search


When ARX recognizes a known technology, optionally expose targeted actions such as:


Search Python Documentation

Search Microsoft Documentation

Search NVIDIA Documentation

Search OpenAI Documentation

Search GitHub Documentation

Search Package Documentation


Use official documentation sources where practical.


Do not pretend to know an official documentation URL if the mapping is uncertain.


Fall back to a web search.


---


27.19 AI panel source context


Inside the ARX AI assistant panel, visibly show what object the conversation concerns.


Example:


Context:

Project → BetBoy-X

Finding → Python provider resolution

Status → RED


Allow:


View Context

Copy Context

Change Context

Clear Conversation


The human should never wonder what machine data the AI is currently reasoning about.


---


27.20 Multiple analysis modes


Where useful, provide predefined AI question templates:


Explain Simply

Explain Technically

Why Is This Important?

Suggest Fix

Security Interpretation

Compatibility Interpretation

Compare Alternatives

What Should I Check Next?


These should merely construct prompts.


Do not create separate hidden reasoning engines for each option.


---


27.21 No fake certainty


AI output must not be presented as fact merely because it sounds confident.


Where an AI recommendation conflicts with ARX evidence, visibly preserve the conflict.


Example:


ARX observed through a bounded detector:

Python 3.11.9 exists.


AI response:

"Python may not be installed."


ARX must not rewrite the provenance of its observed evidence.


Instead indicate that the AI interpretation conflicts with observed ARX evidence.


Deterministic machine observation takes precedence over unsupported model assumptions.


---


27.22 Optional external-provider architecture


Design the AI bridge behind a provider interface.


For example:


AIProvider

│

├── OpenAIProvider

├── CodexCLIProvider

└── FutureProvider


Do not entangle ARX's scanner with provider-specific GUI code.


The scanner should produce structured context.


Providers should consume that context.


The UI should display provider results.


---


27.23 Offline behavior


When no network exists:


Ask ChatGPT


may become unavailable with an understandable explanation.


But core ARX must continue working.


Likewise, if Codex CLI is unavailable, do not produce an application failure.


Show something such as:


Codex CLI is not currently available.


The rest of ARX should remain fully functional.


---


27.24 Cancellation and timeout


External AI calls and Codex processes must be cancellable.


The ARX GUI must not freeze while waiting.


Provide visible states such as:


Preparing context...

Contacting AI...

Waiting for response...

Running Codex analysis...

Cancelled.

Timed out.

Completed.


Use background workers/async processing consistent with the existing ARX desktop architecture.


---


27.25 AI conversation export


Allow the user where appropriate to:


Copy response

Copy conversation

Save conversation

Copy diagnostic prompt


Ensure saved AI discussions do not accidentally bypass ARX's redaction rules.


---


27.26 GitHub Actions: make ARX continuously verify itself


Add a custom ARX GitHub Actions continuous-integration workflow rather than blindly selecting every generic GitHub template.


The desired architecture is conceptually:


               PUSH / PULL REQUEST

                       │

                       ▼

                  ARX CI

                       │

          ┌────────────┼────────────┐

          ▼            ▼            ▼

       Windows        Linux       CodeQL

          │            │            │

       Python        Python      Security

          │            │        Analysis

          ▼            ▼

        pytest       pytest

          │            │

          └──────┬─────┘

                 ▼

             CI RESULT

                 │

          GREEN / FAILED


Because ARX is Windows-first, Windows CI is important.


Do not rely exclusively on Linux.


---


27.27 Python CI


Inspect the repository's currently supported Python versions and create an appropriate test matrix.


At minimum the workflow should perform the repository-equivalent of:


checkout

setup Python

upgrade packaging tools

install ARX development dependencies

run pytest


For the current ARX packaging structure, preserve the equivalent intent of:


python -m pip install -e .\[dev\]

pytest


Do not introduce Conda merely because GitHub suggests the Anaconda template.


ARX currently uses a normal Python/setuptools packaging model, so ordinary Python CI should remain the default unless the repository requirements change.


---


27.28 CodeQL


Add GitHub CodeQL analysis for supported ARX languages.


At minimum inspect Python and the GitHub Actions workflows themselves where supported by the current CodeQL configuration.


CodeQL complements ARX tests:


pytest

    ↓

Does ARX behave correctly?


CodeQL

    ↓

Does ARX source contain detectable security problems?


The two systems serve different purposes.


Use the current supported GitHub CodeQL Actions syntax rather than copying an obsolete workflow example.


---


27.29 AI bridge security tests


The CI suite should specifically test the new integration boundary.


Add tests where practical for:


- redaction before AI transmission

- no credential inclusion

- safe context construction

- safe URL encoding

- safe search-query construction

- safe subprocess argument creation

- no shell injection

- provider-unavailable behavior

- timeout behavior

- cancellation behavior

- Unicode paths

- very large diagnostic messages

- malformed AI responses

- network failure

- Codex executable missing

- invalid API configuration


These are security-sensitive boundaries.


---


27.30 CodeQL and subprocess scrutiny


Pay particular attention to code that:


- launches Codex

- opens URLs

- handles user-controlled paths

- generates search queries

- constructs AI requests

- manages credentials

- processes model responses


Do not suppress CodeQL findings merely to obtain a green badge.


Investigate them.


---


27.31 Pylint/static style analysis


GitHub may suggest Pylint.


Do not immediately make a large historical codebase fail CI because of hundreds of style-only warnings.


First inspect the existing coding standards.


If Pylint or another linter is adopted:


1. configure it intentionally

2. establish a reasonable baseline

3. prioritize correctness/security issues

4. avoid massive unrelated formatting churn


It may be added after core CI is stable.


---


27.32 Python package workflow


GitHub may suggest a generic Python Package workflow.


Use package-build verification where useful, but avoid duplicating identical CI work unnecessarily.


If package validation is added, verify that ARX can build cleanly from source.


Do not automatically publish it.


---


27.33 PyPI publication


Do not enable automatic PyPI publishing solely because GitHub recommends:


Publish Python Package


Only implement PyPI release automation if ARX's release policy explicitly decides to distribute:


arx-prescanner


through PyPI.


Until then, keep publishing separate from testing.


---


27.34 Windows release artifacts


After CI becomes stable, inspect ARX's existing packaging scripts and consider automated Windows build artifacts.


Desired future path:


Git tag/release

      ↓

Windows runner

      ↓

Build ARX

      ↓

Run validation

      ↓

Generate artifact

      ↓

GitHub Release


Do not publish untested executables.


---


27.35 SLSA provenance


GitHub suggests SLSA provenance generation.


Treat this as a valuable later hardening stage after the basic build/release process is stable.


Potential future chain:


Source commit

    ↓

CI

    ↓

Tests

    ↓

CodeQL

    ↓

Windows build

    ↓

Artifact

    ↓

Provenance

    ↓

Release


Do not add complex supply-chain infrastructure before the underlying release pipeline works reliably.


---


27.36 Do not deploy ARX unnecessarily to cloud application platforms


Ignore generic deployment suggestions such as:


- Azure Functions

- Azure Web App

- Amazon ECS

- GKE

- Alibaba Kubernetes

- IBM Kubernetes


unless ARX later gains an explicit server/cloud architecture requiring them.


ARX Desktop is not automatically a cloud application simply because GitHub offers cloud templates.


---


27.37 Do not add Django


Do not use GitHub's Django workflow unless ARX actually becomes a Django project.


Repository-template recommendations are suggestions, not architectural requirements.


---


27.38 No unnecessary Anaconda CI


Do not adopt the GitHub Anaconda workflow by default.


Conda detection may remain part of ARX's machine-analysis capabilities, but ARX's own CI does not need to run inside Conda merely because ARX can detect Conda installations.


Keep those concepts separate.


---


27.39 CI must test normal Windows interaction logic where possible


Extend automated tests around the Windows UX additions from the previous requirements.


Particularly test reusable logic for:


- context menus

- clipboard

- path opening

- report export

- AI context construction

- safe browser search

- provider selection

- Codex detection

- error handling


Avoid fragile pixel-based GUI automation where a stable unit/integration test can verify the same behavior.


---


27.40 Explicit AI consent


On the first use of external AI functionality, explain clearly that selected diagnostic information may be sent to an external provider.


Provide an understandable choice.


Do not use frightening legal language.


Do not create an invented legal agreement.


Explain exactly what the feature does.


---


27.41 Separate three trust domains


Architecturally recognize three different trust domains:


DOMAIN 1

ARX deterministic local evidence


DOMAIN 2

External AI reasoning/advice


DOMAIN 3

Public Internet/web search


Information must cross these boundaries deliberately.


Never treat them as one undifferentiated system.


---


27.42 The desired user experience


A programmer should eventually be able to experience this:


ARX SCAN


Python Toolchain                      RED

    Python 3.13 resolved

    Project requires \<3.12


        Right Click

            │

            ├── Copy

            ├── View Evidence

            ├── Open Python Location

            │

            ├── Ask ChatGPT About This

            ├── Ask Codex About This

            ├── Suggest Safe Fix

            │

            ├── Search Web

            └── Search Exact Error


The important idea is that ARX remains the observer and evidence authority, while AI and the web become investigation instruments available to the human.


---


27.43 Do not turn ARX into an autonomous repair bot


This phase is about:


Observe

Explain

Investigate

Suggest

Navigate

Research


not:


Observe

Silently modify machine


The user remains in control.


A future remediation subsystem may be designed separately with its own security policy.


---


27.44 Architecture principle


Implement the system conceptually as:


                        HUMAN

                          │

                          ▼

                    ARX DESKTOP

                          │

             ┌────────────┼────────────┐

             ▼            ▼            ▼

         ARX CORE      AI BRIDGE     WEB BRIDGE

             │            │            │

             │       ┌────┴────┐       │

             │       ▼         ▼       │

             │    OpenAI     Codex     │

             │      API       CLI      │

             │                         │

             └───────────┬─────────────┘

                         ▼

                  HUMAN DECISION


ARX must remain functional even when the AI Bridge and Web Bridge are disabled.


---


27.45 Final implementation report


At the end of this Point 27 implementation, report:


AI integration discovered


- existing relevant ARX components

- Codex CLI detection method

- supported OpenAI integration selected

- provider architecture


Context-menu additions


List every new context-aware action.


Privacy


Explain exactly what information may leave the machine and what is redacted.


Security


Explain:


- subprocess safety

- credential handling

- URL/search safety

- network boundary

- AI output trust classification


GitHub Actions


Report:


- CI workflows added

- operating systems tested

- Python versions tested

- pytest results

- CodeQL configuration

- artifact/release changes, if any


Tests


Report new tests for:


- AI bridge

- Codex integration

- context construction

- redaction

- browser search

- failure modes

- GUI helper behavior


Limitations


Clearly document functionality that depends on:


- network availability

- API configuration

- Codex installation

- authentication

- operating system capabilities


---


Point 27 Definition of Done


Point 27 is complete only when the following design goals have been addressed:


1. ARX findings can expose context-sensitive AI actions.

2. The user can visibly choose Ask ChatGPT About This where appropriate.

3. The user can visibly choose Ask Codex About This where appropriate.

4. The user can visibly choose Search Web About This.

5. The user can visibly choose Search Google About This where implemented.

6. Exact errors can be searched safely.

7. AI context is automatically relevant rather than an uncontrolled complete scan dump.

8. Redaction occurs before external transmission.

9. No machine information is silently transmitted.

10. OpenAI credentials are handled securely.

11. Codex is invoked through supported programmatic interfaces.

12. Codex subprocess execution does not use unsafe shell interpolation.

13. AI output remains separate from deterministic ARX evidence.

14. AI recommendations do not automatically modify the workstation.

15. ARX remains fully functional without AI.

16. Network and AI operations remain cancellable and do not freeze the GUI.

17. GitHub CI automatically executes ARX tests.

18. Windows is represented in CI because ARX is Windows-first.

19. CodeQL performs repository security analysis.

20. Anaconda is not introduced unnecessarily.

21. PyPI publishing is not enabled without an explicit release decision.

22. Cloud-deployment templates are not added without an architectural need.

23. New external-boundary code has dedicated security tests.

24. Existing ARX tests continue to pass.

25. External AI, public web research, and ARX evidence remain clearly separated.


The guiding principle of Point 27 is:


«ARX should not merely tell the programmer that something is wrong. It should place the evidence under the programmer's mouse and allow them to immediately inspect it, ask intelligence about it, research it, understand it, and decide what to do next.»


ARX remains the eyes and evidence.


ChatGPT or another OpenAI model can become an advisor.


Codex can become the code-aware technical investigator.


The web becomes the external library.


GitHub Actions and CodeQL become the continuous quality guardians.


And the human remains the decision-maker at the center of the system.
