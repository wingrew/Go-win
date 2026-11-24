"use strict";

const el = (id) => document.getElementById(id);
const sideLabel = (side) => side === 1 ? "黑方" : "白方";
const coord = (row, col) => String.fromCharCode(65 + col) + (row + 1);

class BoardView {
  constructor(canvas, onPlay, onInvalid) {
    this.canvas = canvas;
    this.context = canvas.getContext("2d");
    this.onPlay = onPlay;
    this.onInvalid = onInvalid;
    this.state = null;
    this.hover = null;
    new ResizeObserver(() => this.draw()).observe(canvas);
    canvas.addEventListener("pointermove", (event) => {
      this.hover = this.pointAt(event);
      this.draw();
    });
    canvas.addEventListener("pointerleave", () => { this.hover = null; this.draw(); });
    canvas.addEventListener("blur", () => { this.hover = null; this.draw(); });
    canvas.addEventListener("click", (event) => {
      const point = this.pointAt(event);
      if (!point) return this.onInvalid("请点击棋盘上的交叉点。");
      this.onPlay(coord(...point));
    });
    canvas.addEventListener("keydown", (event) => this.key(event));
  }

  get size() { return this.state?.size ?? 15; }

  update(state) {
    if (this.state?.size !== state?.size) this.hover = null;
    this.state = state;
    this.draw();
  }

  geometry() {
    const width = this.canvas.getBoundingClientRect().width;
    const margin = Math.max(25, width * 0.08, width * 0.84 / this.size);
    return { width, margin, step: (width - 2 * margin) / (this.size - 1) };
  }

  pointAt(event) {
    const { margin, step } = this.geometry();
    const rect = this.canvas.getBoundingClientRect();
    const row = Math.round((event.clientY - rect.top - margin) / step);
    const col = Math.round((event.clientX - rect.left - margin) / step);
    return row >= 0 && row < this.size && col >= 0 && col < this.size ? [row, col] : null;
  }

  key(event) {
    const arrows = { ArrowUp: [-1, 0], ArrowDown: [1, 0], ArrowLeft: [0, -1], ArrowRight: [0, 1] };
    if (event.key === "Enter" && this.hover) {
      event.preventDefault();
      this.onPlay(coord(...this.hover));
    } else if (arrows[event.key]) {
      event.preventDefault();
      const [dy, dx] = arrows[event.key];
      const [row, col] = this.hover ?? [Math.floor(this.size / 2), Math.floor(this.size / 2)];
      const clamp = (n) => Math.max(0, Math.min(this.size - 1, n));
      this.hover = [clamp(row + dy), clamp(col + dx)];
      this.draw();
    }
  }

  draw() {
    const { width, margin, step } = this.geometry();
    if (!width) return;
    const canvas = this.canvas;
    const pixels = Math.round(width * window.devicePixelRatio);
    if (canvas.width !== pixels || canvas.height !== pixels) canvas.width = canvas.height = pixels;
    const g = this.context;
    g.setTransform(pixels / width, 0, 0, pixels / width, 0, 0);
    this.drawBoard(g, width, margin, step);
    const radius = step * 0.43;
    this.state?.cells.forEach((stone, index) => {
      if (stone === 0) return;
      const x = margin + step * (index % this.size);
      const y = margin + step * Math.floor(index / this.size);
      this.drawStone(g, x, y, radius, stone);
      if (index === this.state.last) {
        g.strokeStyle = stone === 1 ? "#f0c88d" : "#956234";
        g.lineWidth = 1.6;
        g.beginPath();
        g.arc(x, y, Math.max(2, radius * 0.24), 0, 2 * Math.PI);
        g.stroke();
      }
    });
    if (!this.hover || !this.state || this.state.outcome) return;
    const [row, col] = this.hover;
    const x = margin + step * col;
    const y = margin + step * row;
    if (!this.state.cells[row * this.size + col]) {
      g.save();
      g.globalAlpha = 0.45;
      this.drawStone(g, x, y, radius, this.state.side);
      g.restore();
    } else {
      g.strokeStyle = "#9e352d";
      g.lineWidth = 2;
      g.beginPath();
      g.arc(x, y, radius, 0, 2 * Math.PI);
      g.stroke();
    }
  }

  drawBoard(g, width, margin, step) {
    const surface = g.createLinearGradient(0, 0, width, width);
    surface.addColorStop(0, "#efd3a3");
    surface.addColorStop(0.52, "#e5b97d");
    surface.addColorStop(1, "#d2a065");
    g.fillStyle = surface;
    g.fillRect(0, 0, width, width);
    g.lineWidth = 1;
    g.strokeStyle = "#784d2c12";
    g.beginPath();
    for (let y = 4; y < width; y += 5.1) {
      g.moveTo(0, y);
      g.bezierCurveTo(width * .32, y + Math.sin(y) * 6, width * .71, y - 3, width, y + 1);
    }
    g.stroke();

    g.strokeStyle = "#553b26a1";
    g.fillStyle = "#503923";
    g.textAlign = "center";
    g.textBaseline = "middle";
    g.font = Math.min(13, step * .43) + "px system-ui";
    const end = width - margin;
    g.beginPath();
    for (let i = 0; i < this.size; i += 1) {
      const p = margin + i * step;
      g.moveTo(margin, p);
      g.lineTo(end, p);
      g.moveTo(p, margin);
      g.lineTo(p, end);
      g.fillText(String.fromCharCode(65 + i), p, margin * .36);
      g.fillText(String(i + 1), margin * .36, p);
    }
    g.stroke();
    const stars = {
      9: [[2, 2], [2, 6], [4, 4], [6, 2], [6, 6]],
      13: [[3, 3], [3, 9], [6, 6], [9, 3], [9, 9]],
      19: [3, 9, 15].flatMap((row) => [3, 9, 15].map((col) => [row, col])),
    };
    for (const [row, col] of stars[this.size] ?? []) {
      g.beginPath();
      g.arc(margin + col * step, margin + row * step, Math.min(3, step * .12), 0, 2 * Math.PI);
      g.fill();
    }
  }

  drawStone(g, x, y, radius, stone) {
    g.fillStyle = "#2c1b1945";
    g.beginPath();
    g.arc(x + radius * .09, y + radius * .14, radius, 0, 2 * Math.PI);
    g.fill();
    const fill = g.createRadialGradient(x - radius * .34, y - radius * .42, 0, x, y, radius);
    fill.addColorStop(0, stone === 1 ? "#555e5c" : "#fffefa");
    fill.addColorStop(1, stone === 1 ? "#1a1e1d" : "#e5dcd0");
    g.beginPath();
    g.arc(x, y, radius, 0, 2 * Math.PI);
    g.fillStyle = fill;
    g.fill();
    g.lineWidth = 1;
    g.strokeStyle = stone === 1 ? "#171c1a" : "#b6a28b";
    g.stroke();
  }
}

class Gui {
  constructor() {
    this.state = null;
    this.busy = false;
    this.board = new BoardView(el("board"),
      (coordinate) => this.act("play", { coordinate }),
      (message) => this.feedback(message, true));
    el("setup").addEventListener("submit", (event) => {
      event.preventDefault();
      this.act("new", { kind: el("kind").value, size: el("size").valueAsNumber });
    });
    for (const action of ["restart", "undo", "pass", "resign"]) {
      el(action).addEventListener("click", () => this.act(action));
    }
    el("save").addEventListener("click", () => this.save());
    el("load").addEventListener("click", () => el("file").click());
    el("file").addEventListener("change", () => {
      const [file] = el("file").files;
      el("file").value = "";
      if (file) this.load(file);
    });
    el("tips-toggle").addEventListener("click", () => {
      const hidden = !el("tips").hidden;
      el("tips").hidden = hidden;
      el("tips-toggle").textContent = hidden ? "显示提示" : "隐藏提示";
      el("tips-toggle").setAttribute("aria-expanded", String(!hidden));
    });
    this.request("/api/state");
  }

  render() {
    const s = this.state;
    const active = Boolean(s && !s.outcome);
    el("board-title").textContent = s?.label ?? "棋盘";
    el("board-size").textContent = s ? s.size + " × " + s.size : "";
    const heading = document.createElement("div");
    heading.className = "turn";
    if (active) {
      const stone = document.createElement("span");
      stone.className = s.side === 1 ? "stone black" : "stone";
      heading.append(stone, "轮到 " + sideLabel(s.side));
    } else {
      heading.textContent = s?.outcome ?? "当前没有对局";
    }
    const details = document.createElement("div");
    if (s) {
      const captures = s.allows_pass ? " · 提子 黑 " + s.captures[0] + " / 白 " + s.captures[1] : "";
      details.textContent = "第 " + s.turns + " 步 · 剩余悔棋 " + s.undo_left + " 次" + captures;
      if (s.allows_pass && s.passes) details.textContent += " · 连续虚着 " + s.passes + " 次";
    }
    el("status").replaceChildren(heading, details);
    for (const id of ["kind", "size", "start"]) el(id).disabled = this.busy || active;
    el("restart").disabled = this.busy || !active;
    el("undo").disabled = this.busy || !s || !s.turns || !s.undo_left;
    el("pass").disabled = this.busy || !active || !s.allows_pass;
    el("resign").disabled = this.busy || !active;
    el("save").disabled = this.busy || !s;
    el("load").disabled = this.busy;
    this.board.update(s);
  }

  feedback(message, error = false) {
    el("feedback").textContent = message;
    el("feedback").classList.toggle("error", error);
  }

  async request(path, body, onResponse) {
    if (this.busy) return;
    this.busy = true;
    this.render();
    try {
      const response = await fetch(path, body === undefined ? {} : {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body,
      });
      if (response.ok && onResponse) {
        await onResponse(response);
      } else {
        const data = await response.json();
        if ("state" in data) this.state = data.state;
        if (data.message) this.feedback(data.message, !response.ok);
      }
    } catch {
      this.feedback("与本机服务通信失败，请确认程序仍在运行。", true);
    } finally {
      this.busy = false;
      this.render();
    }
  }

  act(action, fields = {}) {
    return this.request("/api/action", JSON.stringify({ action, ...fields }));
  }

  load(file) {
    if (file.size > 1024 * 1024) return this.feedback("存档超过 1 MiB。", true);
    return this.request("/api/load", file);
  }

  save() {
    return this.request("/api/archive", undefined, async (response) => {
      const url = URL.createObjectURL(await response.blob());
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "go-win-" + this.state.kind + ".gowin.json";
      anchor.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      this.feedback("已导出存档，请在浏览器下载记录中查看。");
    });
  }
}

new Gui();
