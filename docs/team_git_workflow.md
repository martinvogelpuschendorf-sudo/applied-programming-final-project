```markdown
# Team Git Workflow Guide

This document explains how our team should work with Git branches, Pull Requests, and code reviews.

## Main Rules

- Do not write code directly on `main`.
- Do not commit directly to the team `main` branch.
- Create one `feature branch` for each task.
- Open a Pull Request after finishing the task.
- At least one teammate should review the Pull Request before merging.
- Merge into `main` only after review.

## Fork vs Branch

A `fork` means copying a repository into your own GitHub account.

Forks are useful when someone does not have write access to the original repository, for example external contributors in open source projects.

For our internal team project, all three members have access to the same repository. Therefore, it is simpler and clearer to create branches directly inside the shared team repository.

Recommended structure:

```text
Luolan-AI/applied-programming-final-project
├── main
├── feature/tcp-backend
├── feature/gui-live-plot
└── feature/signal-processing
```

## Branch Workflow

### 1. Start From The Latest Main

```bash
git checkout main
git pull
git checkout -b feature/gui-live-plot
```

Replace `feature/gui-live-plot` with your own branch name.

Examples:

```bash
git checkout -b feature/tcp-backend
git checkout -b feature/signal-processing
git checkout -b feature/offline-plot
```

### 2. Commit Your Work

After writing code:

```bash
git status
git add .
git commit -m "Add GUI live plot"
```

Use a clear commit message that describes what you changed.

### 3. Push Your Branch To GitHub

```bash
git push -u origin feature/gui-live-plot
```

Replace `feature/gui-live-plot` with your own branch name.

### 4. Open A Pull Request

On GitHub, open a Pull Request from your feature branch into `main`.

Example:

```text
Luolan-AI:feature/gui-live-plot
→ Luolan-AI:main
```

The Pull Request should include:

- a short summary of what was changed
- which issue it relates to
- how the change was tested
- any known limitations

## Pull Request Review Workflow

When a teammate opens a Pull Request, we should review it before merging.

### 1. Go To Your Local Repository

```bash
cd "your-local-repository-path"
```

Example:

```bash
cd "/Users/luolan/Documents/applied programming/work/applied-programming-final-project"
```

### 2. Check Your Local Changes

```bash
git status
```

If you see:

```text
nothing to commit, working tree clean
```

you can continue.

If you have uncommitted changes, do not switch branches yet. First, either commit them or stash them.

Commit example:

```bash
git add .
git commit -m "Save current work"
```

Stash example:

```bash
git stash
```

### 3. Update Team Main

This makes sure your local `main` branch is up to date.

```bash
git checkout main
git pull
```

### 4. Fetch The Teammate's PR Branch

If the teammate's branch is inside our shared team repository, use:

```bash
git fetch origin feature/gui-live-plot:review/gui-live-plot
git checkout review/gui-live-plot
```

Here, `review/gui-live-plot` is a temporary local review branch on your computer.

Replace `feature/gui-live-plot` with the teammate's branch name.

### 5. Test The Teammate's Code Together With Main

Merge the current team `main` into the review branch:

```bash
git merge origin/main
```

This checks whether the teammate's code works together with the latest team code.

If there is no conflict, continue testing.

If there is a conflict, do not merge the Pull Request yet. Leave a comment on the Pull Request, for example:

```text
This PR has merge conflicts with the current main branch. Please update your branch and resolve the conflicts before merging.
```

### 6. Install Dependencies

We use `uv`.

If the project uses `requirements.txt`:

```bash
uv pip install -r requirements.txt
```

If the project later uses `pyproject.toml`:

```bash
uv sync
```

### 7. Run The Application

```bash
uv run python final_project/main.py
```

If the feature requires the TCP server, start the provided TCP server first and then test the application.

### 8. Review Checklist

Check the Pull Request depending on the type of work.

For TCP/backend changes:

```text
- Does the app start?
- Does the TCP connection work?
- Is the packet format correct?
- Are packets reconstructed as 32 channels x 18 samples?
- Is the data type float64?
- Is the packet size 4608 bytes?
- Does the code handle incomplete TCP packets?
- Does the code handle server disconnects?
- Is there a rolling buffer for live plotting?
- Is there a full recording buffer for offline plotting?
- Is backend logic separated from GUI code?
```

For GUI/live plot changes:

```text
- Does the app start?
- Is there a TCP port input field?
- Are there Connect and Disconnect buttons?
- Is there a visible connection status?
- Is there a channel selector?
- Is there a signal mode selector?
- Does the VisPy live plot update?
- Can the user switch channels?
- Is there a Plot All Channels button?
- Does the GUI remain responsive?
- Is UI code separated from model/backend logic?
```

For signal processing/offline plot/documentation changes:

```text
- Does original signal mode work?
- Does RMS mode work?
- Does filtered mode work?
- Are filter parameters validated?
- Are short signals handled safely?
- Does offline Matplotlib plotting work?
- Does the README explain setup and usage?
- Are team responsibilities documented?
```

### 9. Give Feedback

If everything works:

```text
Approve the Pull Request.
```

You can write:

```text
Tested locally with uv. The application starts successfully and the changes look good to me.
```

If something is wrong:

```text
Comment
```

or:

```text
Request changes
```

Example:

```text
I tested this branch locally, but the application does not start because of an import error in `final_project/views/main_view.py`.
Please fix this before merging.
```

### 10. Return To Main After Review

After reviewing, switch back to `main`:

```bash
git checkout main
git pull
```

You can delete the temporary local review branch:

```bash
git branch -D review/gui-live-plot
```

This only deletes the local review branch on your computer. It does not delete your teammate's GitHub branch.

## Reviewing A Forked Branch

If a teammate worked in their own fork, fetch their branch like this:

```bash
git fetch https://github.com/USERNAME/applied-programming-final-project.git BRANCH_NAME:review/teammate-branch
git checkout review/teammate-branch
git merge origin/main
```

Example:

```bash
git fetch https://github.com/martinvogelpuschendorf-sudo/applied-programming-final-project.git first-draft-gui-plots:review/martin-gui-plots
git checkout review/martin-gui-plots
git merge origin/main
```

Then run the project:

```bash
uv run python final_project/main.py
```

## Important Notes

`main` is the stable team version.

A `feature branch` is used for one task or feature.

A `Pull Request` is a request to merge a branch into `main`.

A `review` means that teammates check the code before it enters `main`.

A `merge` means the code officially becomes part of `main`.

## Summary

```text
main = stable team version
feature branch = task-specific development branch
Pull Request = request to merge into main
review = teammate checks the code
merge = code enters main
```
```
