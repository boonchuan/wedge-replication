# Publishing the replication package

Three steps: (1) push to GitHub, (2) connect Zenodo for a DOI, (3) update the
paper to cite the DOI.

## 1. Push to GitHub

From your laptop, after extracting this repo into a folder:

```powershell
cd C:\path\to\wedge-replication

git init
git add .
git commit -m "Initial commit: replication package for v0.3"
git branch -M main
```

Then create a new public repository on GitHub (e.g. `wedge-replication`) under
your account at https://github.com/new. Don't initialize with README/license/
gitignore — those are already in place.

```powershell
git remote add origin https://github.com/<your-handle>/wedge-replication.git
git push -u origin main
```

If you've never set up GitHub auth on this machine, the first push will prompt
for credentials. Use a Personal Access Token (Settings → Developer settings →
Personal access tokens → Generate new token, with `repo` scope) rather than
your password.

## 2. Add the data CSVs

The `data/polymarket/` and `data/kalshi/` directories ship empty (only
`.gitkeep`). Run the pull scripts on the VPS, then scp the resulting CSVs back
to the local repo:

```powershell
cd C:\path\to\wedge-replication\data\polymarket
scp delta-dev@103.195.191.139:/home/delta-dev/research/settlement_wedge/data/polymarket/*.csv .
scp delta-dev@103.195.191.139:/home/delta-dev/research/settlement_wedge/data/polymarket/*.json .

cd ..\kalshi
scp delta-dev@103.195.191.139:/home/delta-dev/research/settlement_wedge/data/kalshi/*.csv .
scp delta-dev@103.195.191.139:/home/delta-dev/research/settlement_wedge/data/kalshi/*.json .

cd ..\..\figures
scp delta-dev@103.195.191.139:/home/delta-dev/research/settlement_wedge/figures/*.png .
scp delta-dev@103.195.191.139:/home/delta-dev/research/settlement_wedge/figures/*.csv .
```

Then commit:

```powershell
cd C:\path\to\wedge-replication
git add data figures
git commit -m "Add pulled CSVs and generated figures"
git push
```

Total repo size after data: ~50-100 MB. Well within GitHub's free-tier limits.
If any single CSV exceeds 100 MB, GitHub will reject it; in that case use
[Git LFS](https://git-lfs.github.com/) for that one file.

## 3. Get a Zenodo DOI

Zenodo gives every GitHub release a citable DOI. This is what the fact-check
report flagged as the highest-priority missing item.

1. Go to https://zenodo.org and log in with your GitHub account.
2. Navigate to your account settings → "GitHub" tab.
3. Find `<your-handle>/wedge-replication` in the list and flip its toggle ON.
4. Back on GitHub, create a release: Releases → "Draft a new release"
   - Tag: `v0.3.0`
   - Title: `Replication package v0.3`
   - Description: brief notes (or paste from `docs/changelog.md`)
   - Click "Publish release"
5. Within ~30 seconds, Zenodo will create a DOI. Find it at
   https://zenodo.org → "Upload" → Find your published deposit. The DOI looks like
   `10.5281/zenodo.<numeric>`.

## 4. Cite the DOI in the paper

In the manuscript Appendix A, replace:

> Replication scripts and pulled CSVs are available on request.

with:

> Replication scripts and pulled CSVs are publicly available at
> https://github.com/<your-handle>/wedge-replication, archived at
> https://doi.org/10.5281/zenodo.<numeric>.

Also update the bibliography to add a self-citation entry:

```
Lim, Boon Chuan (2026b). "Replication Package for Kalshi's Ceiling."
Zenodo. https://doi.org/10.5281/zenodo.<numeric>.
```

## 5. Optional: protect the repo from future breakage

After the paper is submitted, consider:

- **Branch protection** on `main` (Settings → Branches → Add rule) so future
  pushes don't accidentally break the version reviewers cite.
- **Pin the Python version** in `requirements.txt` more strictly if you ever
  hit reproducibility issues.
- **Add a citation reminder** to the README if you publish updates: "Cite v0.3
  for results matching the SSRN paper; later versions may include extensions."

## 6. Cite the GitHub repo in the SSRN abstract

Once the DOI is live, edit the SSRN abstract page to include the GitHub URL in
the comment field. SSRN allows post-submission edits to the abstract page.
