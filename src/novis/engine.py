"""Training and validation loops.

Workstation-class recipe for the RTX 5070 Ti: bfloat16 autocast, TF32
matmuls, channels-last memory format, fused AdamW, cosine schedule with
warmup, gradient accumulation, an exponential moving average (EMA) of the
weights for evaluation and release checkpoints, and an optional PatchGAN
critic when train.lambda_adv > 0. Runs unchanged (slower) on CPU.
"""

import csv
import json
import math
import time
from pathlib import Path

import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader

from .losses import PerceptualLoss, total_loss
from .metrics import evaluate_batch
from .models import PatchDiscriminator, d_hinge_loss, g_hinge_loss


def make_loader(dataset, batch_size, shuffle, workers=0):
    from .data import collate_batch
    return DataLoader(dataset, batch_size=batch_size, shuffle=shuffle,
                      num_workers=workers, collate_fn=collate_batch,
                      pin_memory=torch.cuda.is_available(), drop_last=shuffle,
                      persistent_workers=workers > 0)


def to_device(batch: dict, device) -> dict:
    out = {}
    for k, v in batch.items():
        v = v.to(device, non_blocking=True)
        if v.ndim == 4:
            v = v.contiguous(memory_format=torch.channels_last)
        out[k] = v
    return out


class EMA:
    """Exponential moving average of model weights (buffers copied through).

    The effective decay warms up as min(decay, (1+n)/(10+n)) so short runs
    and early validation are not stuck at the initialization.
    """

    def __init__(self, model, decay: float = 0.999):
        self.decay = decay
        self.updates = 0
        self.shadow = {k: v.detach().clone().float()
                       for k, v in model.state_dict().items()}

    @torch.no_grad()
    def update(self, model):
        self.updates += 1
        d = min(self.decay, (1.0 + self.updates) / (10.0 + self.updates))
        for k, v in model.state_dict().items():
            s = self.shadow[k]
            if torch.is_floating_point(v):
                s.mul_(d).add_(v.detach().float(), alpha=1.0 - d)
            else:
                s.copy_(v)

    def state_dict(self):
        return self.shadow

    def load_state_dict(self, state):
        self.shadow = {k: v.clone().float() if torch.is_floating_point(v)
                       else v.clone() for k, v in state.items()}


class Trainer:
    def __init__(self, model, cfg, run_dir: str, device: str = None):
        self.cfg = cfg
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        t = cfg.train
        if self.device == "cuda":
            torch.set_float32_matmul_precision("high")   # enable TF32
        self.model = model.to(self.device)
        if self.device == "cuda":
            self.model = self.model.to(memory_format=torch.channels_last)
        if getattr(t, "compile", False):
            self.model = torch.compile(self.model)

        fused = self.device == "cuda"
        self.opt = torch.optim.AdamW(self.model.parameters(), lr=t.lr,
                                     weight_decay=t.weight_decay, fused=fused)
        self.epochs = t.epochs
        self.accum = max(1, int(getattr(t, "accum_steps", 1)))
        self.lambda_d = t.lambda_depth
        self.lambda_c = getattr(t, "lambda_color", 0.0)
        self.lambda_p = getattr(t, "lambda_perc", 0.0)
        self.lambda_a = getattr(t, "lambda_adv", 0.0)
        self.use_amp = (self.device == "cuda" and t.amp)

        self.perceptual = None
        if self.lambda_p > 0.0:
            self.perceptual = PerceptualLoss().to(self.device)

        self.disc = None
        if self.lambda_a > 0.0:
            self.disc = PatchDiscriminator().to(self.device)
            if self.device == "cuda":
                self.disc = self.disc.to(memory_format=torch.channels_last)
            self.opt_d = torch.optim.AdamW(self.disc.parameters(),
                                           lr=t.lr * 0.5, betas=(0.5, 0.999),
                                           weight_decay=0.0, fused=fused)

        self.ema = EMA(self.model, getattr(t, "ema_decay", 0.999))
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.run_dir / "log.csv"
        self.best_val = math.inf
        self.start_epoch = 0
        self._log_header_written = self.log_path.exists()

    # ------------------------------------------------------------- utils

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

    def _disc_inputs(self, out, batch):
        thermal_up = F.interpolate(batch["thermal"],
                                   size=out["gray"].shape[-2:],
                                   mode="nearest")
        return out["gray"], batch["gray"], thermal_up

    # ------------------------------------------------------- checkpoints

    def save_checkpoint(self, epoch, val):
        state = {"model": self.model.state_dict(),
                 "ema": self.ema.state_dict(),
                 "opt": self.opt.state_dict(),
                 "epoch": epoch, "val": val, "best_val": self.best_val}
        if self.disc is not None:
            state["disc"] = self.disc.state_dict()
            state["opt_d"] = self.opt_d.state_dict()
        torch.save(state, self.run_dir / "latest.pt")
        if val["val_loss"] < self.best_val:
            self.best_val = val["val_loss"]
            # Release checkpoint: EMA weights under the standard "model" key
            # so eval.py / export.py / the server load it directly.
            torch.save({"model": self.ema.state_dict(), "epoch": epoch,
                        "val": val}, self.run_dir / "best.pt")

    def load_checkpoint(self, path):
        state = torch.load(path, map_location=self.device, weights_only=True)
        self.model.load_state_dict(state["model"])
        if "ema" in state:
            self.ema.load_state_dict(state["ema"])
        if "opt" in state:
            self.opt.load_state_dict(state["opt"])
        if self.disc is not None and "disc" in state:
            self.disc.load_state_dict(state["disc"])
            self.opt_d.load_state_dict(state["opt_d"])
        self.best_val = state.get("best_val", math.inf)
        self.start_epoch = state.get("epoch", -1) + 1
        print(f"resumed from {path} at epoch {self.start_epoch}")

    # ------------------------------------------------------------- loops

    def train_epoch(self, loader, epoch):
        self.model.train()
        n = len(loader)
        running, running_d = 0.0, 0.0
        self.opt.zero_grad(set_to_none=True)
        for i, batch in enumerate(loader):
            batch = to_device(batch, self.device)
            self._set_lr(epoch, i, n)

            with self._autocast():
                out = self.model(batch["thermal"], batch["echo"],
                                 batch["sonar"], batch["mask"])
                losses = total_loss(out, batch, self.lambda_d, self.lambda_c,
                                    self.lambda_p, self.perceptual)
                g_total = losses["total"]
                if self.disc is not None:
                    fake, _, cond = self._disc_inputs(out, batch)
                    g_total = g_total + self.lambda_a * g_hinge_loss(
                        self.disc(fake, cond))

            (g_total / self.accum).backward()
            if (i + 1) % self.accum == 0:
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
                self.opt.step()
                self.opt.zero_grad(set_to_none=True)
                self.ema.update(self.model)

            if self.disc is not None:
                with self._autocast():
                    fake, real, cond = self._disc_inputs(out, batch)
                    d_loss = d_hinge_loss(self.disc(real, cond),
                                          self.disc(fake.detach(), cond))
                self.opt_d.zero_grad(set_to_none=True)
                d_loss.backward()
                self.opt_d.step()
                running_d += float(d_loss.detach())

            running += float(losses["total"].detach())
        stats = {"train_loss": running / max(1, n)}
        if self.disc is not None:
            stats["d_loss"] = running_d / max(1, n)
        return stats

    @torch.no_grad()
    def validate(self, loader, use_ema: bool = True):
        """Validate with the EMA weights (the release weights)."""
        backup = None
        if use_ema:
            backup = {k: v.detach().clone()
                      for k, v in self.model.state_dict().items()}
            self.model.load_state_dict(self.ema.state_dict())
        self.model.eval()
        agg, n = {}, 0
        for batch in loader:
            batch = to_device(batch, self.device)
            with self._autocast():
                out = self.model(batch["thermal"], batch["echo"],
                                 batch["sonar"], batch["mask"])
                losses = total_loss(out, batch, self.lambda_d, self.lambda_c,
                                    self.lambda_p, self.perceptual)
            m = evaluate_batch({k: v.float() for k, v in out.items()}, batch)
            m["val_loss"] = float(losses["total"])
            for k, v in m.items():
                agg[k] = agg.get(k, 0.0) + v
            n += 1
        if backup is not None:
            self.model.load_state_dict(backup)
        return {k: v / max(1, n) for k, v in agg.items()}

    def fit(self, train_ds, val_ds):
        t = self.cfg.train
        train_loader = make_loader(train_ds, t.batch_size, True, t.workers)
        val_loader = make_loader(val_ds, t.batch_size, False, t.workers)
        history = []
        for epoch in range(self.start_epoch, self.epochs):
            t0 = time.time()
            stats = self.train_epoch(train_loader, epoch)
            val = self.validate(val_loader)
            row = {"epoch": epoch,
                   **{k: round(v, 5) for k, v in stats.items()},
                   **{k: round(v, 5) for k, v in val.items()},
                   "secs": round(time.time() - t0, 1)}
            history.append(row)
            self._log(row)
            print(f"[epoch {epoch:03d}] train {stats['train_loss']:.4f} "
                  f"val {val['val_loss']:.4f} psnr {val['psnr']:.2f} "
                  f"ssim {val['ssim']:.3f} ({row['secs']}s)")
            self.save_checkpoint(epoch, val)
        with open(self.run_dir / "history.json", "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)
        return history
