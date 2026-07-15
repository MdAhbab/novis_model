"""Training and validation loops: AMP, cosine schedule, CSV logs, checkpoints."""

import csv
import json
import math
import time
from pathlib import Path

import torch
from torch.utils.data import DataLoader

from .losses import total_loss
from .metrics import evaluate_batch


def make_loader(dataset, batch_size, shuffle, workers=0):
    from .data import collate_batch
    return DataLoader(dataset, batch_size=batch_size, shuffle=shuffle,
                      num_workers=workers, collate_fn=collate_batch,
                      pin_memory=torch.cuda.is_available(), drop_last=shuffle)


def to_device(batch: dict, device) -> dict:
    return {k: v.to(device, non_blocking=True) for k, v in batch.items()}


class Trainer:
    def __init__(self, model, cfg, run_dir: str, device: str = None):
        self.cfg = cfg
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model = model.to(self.device)
        t = cfg.train
        self.opt = torch.optim.AdamW(model.parameters(), lr=t.lr,
                                     weight_decay=t.weight_decay)
        self.epochs = t.epochs
        self.lambda_d = t.lambda_depth
        self.lambda_c = t.lambda_color
        self.use_amp = (self.device == "cuda" and t.amp)
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.run_dir / "log.csv"
        self.best_val = math.inf
        self._log_header_written = self.log_path.exists()

    def _autocast(self):
        if self.use_amp:
            return torch.autocast("cuda", dtype=torch.bfloat16)
        return torch.autocast("cpu", enabled=False)

    def _log(self, row: dict):
        write_header = not self._log_header_written
        with open(self.log_path, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(row.keys()))
            if write_header:
                w.writeheader()
                self._log_header_written = True
            w.writerow(row)

    def _set_lr(self, epoch, step, steps_per_epoch):
        t = self.cfg.train
        total = self.epochs * steps_per_epoch
        cur = epoch * steps_per_epoch + step
        warm = t.warmup_steps
        if cur < warm:
            lr = t.lr * (cur + 1) / warm
        else:
            p = (cur - warm) / max(1, total - warm)
            lr = t.lr * 0.5 * (1.0 + math.cos(math.pi * p))
        for g in self.opt.param_groups:
            g["lr"] = lr
        return lr

    def train_epoch(self, loader, epoch):
        self.model.train()
        n = len(loader)
        running = 0.0
        for i, batch in enumerate(loader):
            batch = to_device(batch, self.device)
            lr = self._set_lr(epoch, i, n)
            with self._autocast():
                out = self.model(batch["thermal"], batch["echo"],
                                 batch["sonar"], batch["mask"])
                losses = total_loss(out, batch, self.lambda_d, self.lambda_c)
            self.opt.zero_grad(set_to_none=True)
            losses["total"].backward()
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
            self.opt.step()
            running += float(losses["total"].detach())
        return running / max(1, n)

    @torch.no_grad()
    def validate(self, loader):
        self.model.eval()
        agg, n = {}, 0
        for batch in loader:
            batch = to_device(batch, self.device)
            with self._autocast():
                out = self.model(batch["thermal"], batch["echo"],
                                 batch["sonar"], batch["mask"])
                losses = total_loss(out, batch, self.lambda_d, self.lambda_c)
            m = evaluate_batch({k: v.float() for k, v in out.items()}, batch)
            m["val_loss"] = float(losses["total"])
            for k, v in m.items():
                agg[k] = agg.get(k, 0.0) + v
            n += 1
        return {k: v / max(1, n) for k, v in agg.items()}

    def fit(self, train_ds, val_ds):
        t = self.cfg.train
        train_loader = make_loader(train_ds, t.batch_size, True, t.workers)
        val_loader = make_loader(val_ds, t.batch_size, False, t.workers)
        history = []
        for epoch in range(self.epochs):
            t0 = time.time()
            train_loss = self.train_epoch(train_loader, epoch)
            val = self.validate(val_loader)
            row = {"epoch": epoch, "train_loss": round(train_loss, 5),
                   **{k: round(v, 5) for k, v in val.items()},
                   "secs": round(time.time() - t0, 1)}
            history.append(row)
            self._log(row)
            print(f"[epoch {epoch:03d}] train {train_loss:.4f} "
                  f"val {val['val_loss']:.4f} psnr {val['psnr']:.2f} "
                  f"ssim {val['ssim']:.3f} ({row['secs']}s)")
            torch.save({"model": self.model.state_dict(), "epoch": epoch,
                        "val": val}, self.run_dir / "latest.pt")
            if val["val_loss"] < self.best_val:
                self.best_val = val["val_loss"]
                torch.save({"model": self.model.state_dict(), "epoch": epoch,
                            "val": val}, self.run_dir / "best.pt")
        with open(self.run_dir / "history.json", "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)
        return history
