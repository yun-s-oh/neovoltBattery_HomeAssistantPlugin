---
description: Steps to consistently update the changelog and relevant documentation files after making codebase changes
---

# Update Documentation and Changelog Workflow

Consistent documentation is crucial for maintaining project context and history. Follow this workflow whenever you make meaningful changes to the codebase, fix bugs, or add new features.

## Step 1: Identify Changed Components

Before writing documentation, briefly summarize the work that was done:
- What new features were added?
- What bugs were fixed?
- Were there any breaking changes or architecture modifications?

## Step 2: Update the Changelog

The changelog tracks all notable changes to the project.

1. Open `.antigravity/logs/changelog.md`.
2. Locate the current date section (e.g., `## YYYY-MM-DD`). If it doesn't exist, create it at the top of the file just below the header.
3. Add a concise bullet point describing the change.
   - Use clear, action-oriented language (e.g., "Added...", "Fixed...", "Refactored...").
   - Mention specific components or file names if applicable.

## Step 3: Update Project Context

If the changes affected the architecture, the domain models, or added new major capabilities, you must update the core project documentation.

1. Open `.antigravity/context.md`.
2. Find the relevant section (e.g., "Architecture", "Supported Services").
3. Update the text to reflect the current state of the codebase. Do not leave outdated information.

## Step 4: Update Instructions (If Applicable)

If the change introduced new commands, tools, or development processes:

1. Open `.antigravity/instructions.md`.
2. Add or modify the instructions so future developers (or agents) know how to use the new processes.

## Step 5: Verify Documentation Integrity

- Read through your additions to ensure clarity and correct formatting.
- Check that all markdown links within the documents are still valid.
