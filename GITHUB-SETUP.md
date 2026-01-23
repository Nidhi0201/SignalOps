# Steps to Push SignalOps to GitHub

Follow these steps to push your project to GitHub:

## Prerequisites

- GitHub account (create one at https://github.com if you don't have one)
- Git installed on your machine (check with `git --version`)

## Step 1: Initialize Git Repository

Open your terminal and navigate to the project directory:

```bash
cd /Users/nidhiprajapati/Desktop/SignalOps
```

Initialize Git:

```bash
git init
```

## Step 2: Add All Files

Add all files to staging:

```bash
git add .
```

Verify what will be committed:

```bash
git status
```

You should see all your files listed. Make sure `venv/` and `node_modules/` are NOT listed (they should be ignored by `.gitignore`).

## Step 3: Create Initial Commit

Create your first commit:

```bash
git commit -m "Initial commit: SignalOps observability platform

- Log ingestion and search (Phase 1)
- Alert rules and incident management (Phase 2)
- AI-powered incident summarization (Phase 3)
- Ask My Logs RAG chat interface (Phase 4)
- Full-stack application with FastAPI backend and Next.js frontend"
```

## Step 4: Create GitHub Repository

1. Go to https://github.com and sign in
2. Click the **"+"** icon in the top right corner
3. Select **"New repository"**
4. Fill in the details:
   - **Repository name**: `SignalOps` (or your preferred name)
   - **Description**: "Mini Datadog/ELK - Observability platform with log ingestion, search, alerts, and AI-powered analysis"
   - **Visibility**: Choose **Public** or **Private**
   - **DO NOT** initialize with README, .gitignore, or license (we already have these)
5. Click **"Create repository"**

## Step 5: Add Remote and Push

After creating the repository, GitHub will show you commands. Use these:

**If your repository is named `SignalOps` and your GitHub username is `YOUR_USERNAME`:**

```bash
# Add the remote repository
git remote add origin https://github.com/YOUR_USERNAME/SignalOps.git

# Rename default branch to main (if needed)
git branch -M main

# Push to GitHub
git push -u origin main
```

**Replace `YOUR_USERNAME` with your actual GitHub username!**

## Step 6: Verify

1. Go to your GitHub repository page
2. You should see all your files there
3. Check that `venv/` and `node_modules/` are NOT visible (they should be ignored)

## Alternative: Using SSH (if you have SSH keys set up)

If you prefer SSH instead of HTTPS:

```bash
git remote add origin git@github.com:YOUR_USERNAME/SignalOps.git
git branch -M main
git push -u origin main
```

## Troubleshooting

### If you get "authentication failed":
- For HTTPS: You may need to use a Personal Access Token instead of password
  - Go to GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)
  - Generate a new token with `repo` permissions
  - Use this token as your password when pushing

### If you get "remote origin already exists":
```bash
git remote remove origin
git remote add origin https://github.com/YOUR_USERNAME/SignalOps.git
```

### If you need to update the remote URL:
```bash
git remote set-url origin https://github.com/YOUR_USERNAME/SignalOps.git
```

## Next Steps After Pushing

1. **Add a repository description** on GitHub
2. **Add topics/tags** like: `observability`, `logging`, `fastapi`, `nextjs`, `opensearch`, `ai`, `rag`
3. **Consider adding a LICENSE file** (MIT, Apache 2.0, etc.)
4. **Update README.md** if needed with badges, screenshots, or additional info

## Quick Reference Commands

```bash
# Check status
git status

# See what files are tracked
git ls-files

# See commit history
git log --oneline

# Push future changes
git add .
git commit -m "Your commit message"
git push
```

---

**That's it!** Your SignalOps project is now on GitHub! 🎉
