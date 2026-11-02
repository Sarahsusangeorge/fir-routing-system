# fir_lab: lab runbook (shared Linux lab, Google Drive, logout-safe)

## A. At home, before you go (5 minutes)
Open your `fir_lab` folder on Google Drive and upload these three files into it, choosing
**Replace existing file** when Drive asks (do not choose "Keep both"):
- `fir_pipeline_lab.ipynb`  (now saves every finished run, so a logout loses at most one run)
- `run_lab.sh`              (new: start / resume / status in one command)
- `README_LAB.md`           (this file)

## B. At the lab: get the folder
1. Open a **private/incognito** browser window (shared machine), sign in to drive.google.com.
2. Right-click the `fir_lab` folder -> Download. Drive makes one or more zip files.
3. Unzip into your home folder:
   ```
   cd ~/Downloads
   for z in fir_lab*.zip; do unzip -o "$z" -d ~/; done
   cd ~/fir_lab
   ```
4. Check nothing got damaged in the download:
   ```
   ls -lh data/ILSI data/ACI models/distilbert-base-uncased
   ```
   Expect train.jsonl ~305M, dev.jsonl ~81M, test.jsonl ~101M, model.safetensors ~256M.
5. Delete the zips from Downloads, then **sign out of Google and close the private window**.

## C. Check the machine
```
nvidia-smi          # GPU visible? is anyone else using it?
df -h ~             # need roughly 8 GB free in your home folder (PyTorch with CUDA is big)
python3 --version
which tmux          # if empty, run_lab.sh falls back to nohup
```

## D. One-time setup
```
cd ~/fir_lab
bash setup_lab.sh
```
It must end with `cuda available: True`. (If nvidia-smi showed CUDA 11.x, change `cu121` to `cu118`
inside setup_lab.sh first.)

## E. Find out what this lab does at logout (1 minute, do it once)
```
tmux new-session -d -s killtest "sleep 900"
```
Log out, log back in, then run `tmux ls`.
- `killtest` is listed: background jobs survive logout here. 
- Not listed: this lab kills your processes at logout. The experiment is still safe to run, because
  finished runs are checkpointed, but after every logout you must run `bash run_lab.sh` again to resume.
Either way, clean up with `tmux kill-session -t killtest`.

## F. Smoke test (catches path/install problems before hours are spent)
```
source fir_env/bin/activate
jupyter lab
```
Open `fir_pipeline_lab.ipynb`. Temporarily set:
- RUN SETTINGS cell: `N_RUNS = 2`, `RF_N_RUNS = 2`, `DISTILBERT_EPOCHS = 1`, `BILSTM_EPOCHS = 1`
- ACI cell: `ACI_N_RUNS = 2`

Run -> Run All Cells. It must reach the end (comparison tables, predict(), t-test verdicts) with no red errors.
The test results are saved under different names from the real run, so they cannot mix into it.

## G. The real run
1. Set everything back: `N_RUNS = 10`, `RF_N_RUNS = 10`, `DISTILBERT_EPOCHS = 2`, `BILSTM_EPOCHS = 6`, `ACI_N_RUNS = 10`.
2. **Save the notebook** (Ctrl+S), then stop Jupyter (Ctrl+C in its terminal).
3. Start:
   ```
   cd ~/fir_lab
   bash run_lab.sh
   ```
   It converts the notebook, runs it in a tmux session called `fir`, keeps the machine from idle-sleeping
   when the system allows it, and restarts itself up to 6 times if the script crashes.

Useful commands:
- `bash run_lab.sh --status`   progress per model, last log lines, running or not
- `tmux attach -t fir`         watch live (leave with Ctrl+B then D, NOT Ctrl+C)
- `tail -f run_log.txt`        the full log

## H. If you got logged out, or the machine rebooted
Log in and run:
```
cd ~/fir_lab
bash run_lab.sh
```
It skips every run already saved in `checkpoints/` and continues. At most the one run that was in
progress is redone. Never delete `checkpoints/` while the experiment is unfinished.

## I. When it finishes (`--status` says NOT RUNNING and the log ends with FINISHED OK)
Upload these to Drive (private window again), then sign out:
- `ilsi_comparison_table.csv`, `aci_comparison_table.csv`
- `fir_distilbert_model/`, `label_set.json`
- `checkpoints/` (the raw per-run numbers: useful to show your faculty all 10 runs)
- `run_log.txt`

Then remove your files from the lab machine (`rm -rf ~/fir_lab ~/Downloads/fir_lab*`) and close your session.

## If something stalls
- RF prints nothing for 10+ minutes: set `RF_N_JOBS = 1` in RUN SETTINGS, save, `bash run_lab.sh`.
- CUDA out of memory: another user may be on the GPU (`nvidia-smi`). The launcher retries automatically;
  if it keeps failing, change `per_device_train_batch_size=16` to `8` in `run_distilbert`.
- `bash run_lab.sh` says "A run is already going": that's fine, use `--status`.
