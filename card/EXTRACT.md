# Moving this folder into its own repository

The card lives here only until `ivan1mihaylov/HomeBasket-card` exists. It is a
complete repository root: `dist/`, `docs/`, `hacs.json`, `README.md`, `LICENSE`
and `.gitignore` are all in place.

Create an **empty** repository named `HomeBasket-card` on GitHub (no README, no
license, no .gitignore), then either ask Claude to push it, or do it yourself:

```bash
git clone https://github.com/ivan1mihaylov/HomeBasket.git /tmp/hb
cd /tmp/hb/card
rm EXTRACT.md
git init -b main
git add .
git commit -m "Add HomeBasket card"
git remote add origin https://github.com/ivan1mihaylov/HomeBasket-card.git
git push -u origin main
```

Afterwards delete `card/` from this repository.
