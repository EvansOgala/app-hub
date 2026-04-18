# app-hub-git AUR Staging Folder

This folder mirrors the package files intended for the AUR repository.

Files to publish:

- `PKGBUILD`
- `.SRCINFO`

Typical workflow:

```bash
git clone ssh://aur@aur.archlinux.org/app-hub-git.git
cd app-hub-git
cp /path/to/your/source/repo/aur/app-hub-git/PKGBUILD .
cp /path/to/your/source/repo/aur/app-hub-git/.SRCINFO .
git add PKGBUILD .SRCINFO
git commit -m "Initial import"
git push
```
