// client/src/BoardStage.jsx
import React, { useEffect, useMemo, useRef, useState } from 'react';
import Konva from 'konva';
import { Stage, Layer, Group, Rect } from 'react-konva';

/* ===== tweakable constants ======================================= */
const CELL                = 30;
const PARTICLES_PER_BLOCK = 200;   // explosion density
const LOCK_EFFECT         = 'tint';   // 'tint' (brighten) or 'mute' (darken)
const LOCK_FLASH_MS       = 120;   // ms duration of lock flash
const CLEAR_STYLE         = 'explode';
/* ================================================================ */

/* canonical NES/TGM colours */
const BASE = {
  1: '#00FFFF', 2: '#0000FF', 3: '#FF7700',
  4: '#FFFF00', 5: '#00FF00', 6: '#FF0000', 7: '#AA00FF'
};

/* colour helpers */
const toRgb = h => [0,2,4].map(i => parseInt(h.slice(1+i,3+i), 16));
const toHex = rgb => '#' + rgb.map(v =>
  Math.max(0, Math.min(255, Math.round(v)))
    .toString(16).padStart(2,'0')
).join('');
const mix   = (h, tgt, t) => toHex(toRgb(h).map((v,i) => v + (tgt[i] - v) * t));
const LIGHT = h => mix(h, [255,255,255], 0.5);
const MID   = h => mix(h, [255,255,255], 0.25);
const DARK  = h => mix(h, [0,0,0], 0.5);
const TINT  = h => mix(h, [255,255,255], 0.6);
const MUTE  = h => mix(h, [0,0,0], 0.6);

export default function BoardStage({ board = [], players = {}, linesToClear = [] }) {
  const rows = board.length;
  const cols = board[0]?.length || 0;
  const W = cols * CELL;
  const H = rows * CELL;

  /* ─── sound refs ───────────────────────────────────────────────── */
  const lockSfx  = useRef(new Audio(`${process.env.PUBLIC_URL}/sounds/lock_sound.wav`));
  const clearSfx = useRef(new Audio(`${process.env.PUBLIC_URL}/sounds/clear.mp3`));

  /* preload audio to avoid first‐play delay */
  useEffect(() => {
    lockSfx.current.preload = 'auto';
    clearSfx.current.preload = 'auto';
  }, []);

  /* ─── lock‑flash canvas overlay ─────────────────────────────────── */
  const flashCanvasRef = useRef(null);
  const [flashes, setFlashes] = useState([]);

  useEffect(() => {
    const prev = flashCanvasRef.current.__prevBoard || [];
    const fresh = [];

    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        if (!prev[r]?.[c] && board[r]?.[c]) {
          const base  = BASE[board[r][c].value] || '#888';
          const color = (LOCK_EFFECT === 'tint' ? TINT(base) : MUTE(base));
          fresh.push({ x: c, y: r, color, ts: Date.now() });
        }
      }
    }

    if (fresh.length) {
      lockSfx.current.currentTime = 0;
      lockSfx.current.play().catch(() => {});
      setFlashes(fs => [...fs, ...fresh]);
    }

    flashCanvasRef.current.__prevBoard = board.map(r => [...r]);
  }, [board, rows, cols]);

  useEffect(() => {
    const canvas = flashCanvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let raf;

    const draw = () => {
      ctx.clearRect(0, 0, W, H);
      const now = Date.now();

      setFlashes(fs => {
        const alive = [];
        fs.forEach(f => {
          const age = now - f.ts;
          if (age < LOCK_FLASH_MS) {
            const alphaHex = Math.floor((1 - age / LOCK_FLASH_MS) * 255)
                                  .toString(16).padStart(2,'0');
            ctx.fillStyle = f.color + alphaHex;
            ctx.fillRect(f.x * CELL, f.y * CELL, CELL, CELL);
            alive.push(f);
          }
        });
        return alive;
      });

      raf = requestAnimationFrame(draw);
    };

    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, [W, H]);

  /* ─── explosion on line‑clear ──────────────────────────────────── */
  const [particles, setParticles] = useState([]);
  const clearHandled = useRef(false);

  useEffect(() => {
    if (!linesToClear.length) {
      clearHandled.current = false;
      return;
    }
    if (clearHandled.current) return;
    clearHandled.current = true;

    clearSfx.current.currentTime = 0;
    clearSfx.current.play().catch(() => {});

    const rowsSet = new Set(linesToClear);
    const newP = [];

    board.forEach((row, r) => {
      row.forEach((cell, c) => {
        if (!cell || !rowsSet.has(r)) return;
        const base = BASE[cell.value] || '#888';

        for (let i = 0; i < PARTICLES_PER_BLOCK; i++) {
          const ang = Math.random() * 2 * Math.PI;
          const spd = 2 + Math.random() * 2;
          newP.push({
            id:   `p-${r}-${c}-${i}-${Date.now()}`,
            x:    c * CELL + Math.random() * CELL,
            y:    r * CELL + Math.random() * CELL,
            w:    2, h: 2,
            color: base,
            dx:   Math.cos(ang) * spd,
            dy:   Math.sin(ang) * spd - 0.3,
            life: 40
          });
        }
      });
    });

    setParticles(p => [...p, ...newP]);
  }, [linesToClear, board]);

  /* ─── particle update loop ───────────────────────────────────── */
  useEffect(() => {
    if (!particles.length) return;
    let raf;

    const step = () => {
      setParticles(ps => ps.flatMap(p => {
        const nx = p.x + p.dx;
        const ny = p.y + p.dy + 0.35;
        const nl = p.life - 1;
        return nl > 0
          ? [{ ...p, x: nx, y: ny, life: nl }]
          : [];
      }));
      raf = requestAnimationFrame(step);
    };

    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [particles.length]);

  /* ─── memoise locked & active cells ───────────────────────────── */
  const locked = useMemo(() =>
    board.flatMap((row, r) => {
      if (CLEAR_STYLE === 'explode' && linesToClear.includes(r)) return [];
      return row.map((cell, c) => {
        if (!cell) return null;
        return {
          id:    `l-${r}-${c}`,
          x:     c,
          y:     r,
          color: BASE[cell.value] ?? '#888'
        };
      }).filter(Boolean);
    }), [board, linesToClear]
  );

  const active = useMemo(() =>
    Object.values(players).flatMap(p => {
      const shp = p?.currentPiece?.shape;
      if (!shp) return [];
      return shp.flatMap((row, dr) => 
        row.map((v, dc) => {
          if (!v) return null;
          const gx = p.x + dc, gy = p.y + dr;
          if (
            gx < 0 || gx >= cols ||
            gy < 0 || gy >= rows ||
            (CLEAR_STYLE === 'explode' && linesToClear.includes(gy))
          ) return null;
          return {
            id:    `a-${gx}-${gy}`,
            x:     gx,
            y:     gy,
            color: BASE[v] ?? '#888'
          };
        }).filter(Boolean)
      );
    }), [players, cols, rows, linesToClear]
  );

  /* ─── glossy Block component ───────────────────────────────────── */
  const Block = ({ x, y, color }) => (
    <Group x={x * CELL} y={y * CELL} listening={false}>
      {/* border */}
      <Rect
        width={CELL}
        height={CELL}
        fill="transparent"
        stroke="#666"
        strokeWidth={1.2}
        cornerRadius={3}
      />
      {/* bevel gradient */}
      <Rect
        x={1}
        y={1}
        width={CELL - 2}
        height={CELL - 2}
        cornerRadius={2.5}
        fillLinearGradientStartPoint={{ x: 0, y: 0 }}
        fillLinearGradientEndPoint={{ x: 0, y: CELL }}
        fillLinearGradientColorStops={[
          0, LIGHT(color),
          0.45, MID(color),
          1, DARK(color)
        ]}
      />
      {/* highlight */}
      <Rect
        x={CELL * 0.15}
        y={CELL * 0.05}
        width={CELL * 0.7}
        height={CELL * 0.25}
        cornerRadius={CELL * 0.35}
        fillRadialGradientStartPoint={{ x: CELL * 0.35, y: CELL * 0.2 }}
        fillRadialGradientStartRadius={1}
        fillRadialGradientEndPoint={{ x: CELL * 0.35, y: CELL * 0.2 }}
        fillRadialGradientEndRadius={CELL * 0.35}
        fillRadialGradientColorStops={[
          0, 'rgba(255,255,255,0.85)',
          1, 'rgba(255,255,255,0)'
        ]}
      />
    </Group>
  );

  /* ─── render ───────────────────────────────────────────────────── */
  return (
    <div style={{ position: 'relative', width: W, height: H }}>
      <Stage width={W} height={H}>
        <Layer listening={false}>
          {/* background & grid */}
          <Rect x={0} y={0} width={W} height={H} fill="#111" />
          <Group opacity={0.12}>
            {Array(rows+1).fill().map((_, i) => (
              <Rect
                key={`h${i}`}
                x={0}
                y={i * CELL}
                width={W}
                height={1}
                fill="#888"
              />
            ))}
            {Array(cols+1).fill().map((_, i) => (
              <Rect
                key={`v${i}`}
                x={i * CELL}
                y={0}
                width={1}
                height={H}
                fill="#888"
              />
            ))}
          </Group>

          {/* locked & active blocks */}
          {locked.map(b => <Block key={b.id} {...b} />)}
          {active.map(b => <Block key={b.id} {...b} />)}

          {/* explosion particles */}
          {particles.map(p => (
            <Rect
              key={p.id}
              x={p.x}
              y={p.y}
              width={p.w}
              height={p.h}
              fill={p.color}
              opacity={p.life / 40}
              listening={false}
            />
          ))}
        </Layer>
      </Stage>

      {/* lock‑flash overlay */}
      <canvas
        ref={flashCanvasRef}
        width={W}
        height={H}
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          pointerEvents: 'none'
        }}
      />
    </div>
  );
}