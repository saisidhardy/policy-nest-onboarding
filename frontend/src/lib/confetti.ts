// Zero-dependency Canvas Confetti Burst Engine for Dopamine Celebrations

interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  size: number;
  color: string;
  rotation: number;
  vRot: number;
  alpha: number;
}

export function fireConfetti(originX?: number, originY?: number) {
  if (typeof window === "undefined") return;

  const canvas = document.createElement("canvas");
  canvas.style.position = "fixed";
  canvas.style.top = "0";
  canvas.style.left = "0";
  canvas.style.width = "100vw";
  canvas.style.height = "100vh";
  canvas.style.pointerEvents = "none";
  canvas.style.zIndex = "99999";
  document.body.appendChild(canvas);

  const ctx = canvas.getContext("2d");
  if (!ctx) {
    document.body.removeChild(canvas);
    return;
  }

  const dpr = window.devicePixelRatio || 1;
  canvas.width = window.innerWidth * dpr;
  canvas.height = window.innerHeight * dpr;
  ctx.scale(dpr, dpr);

  const startX = originX ?? window.innerWidth / 2;
  const startY = originY ?? window.innerHeight * 0.7;

  const colors = [
    "#10b981", // Emerald
    "#f59e0b", // Gold
    "#3b82f6", // Blue
    "#8b5cf6", // Purple
    "#ec4899", // Pink
    "#06b6d4", // Cyan
  ];

  const particles: Particle[] = [];
  const particleCount = 120;

  for (let i = 0; i < particleCount; i++) {
    const angle = (Math.PI / 6) + Math.random() * (Math.PI * 2 / 3);
    const speed = 8 + Math.random() * 16;
    const spread = (Math.random() - 0.5) * 14;

    particles.push({
      x: startX,
      y: startY,
      vx: Math.cos(angle) * speed + spread,
      vy: -Math.sin(angle) * speed,
      size: 6 + Math.random() * 8,
      color: colors[Math.floor(Math.random() * colors.length)],
      rotation: Math.random() * 360,
      vRot: (Math.random() - 0.5) * 12,
      alpha: 1,
    });
  }

  let animId: number;
  const startTime = performance.now();

  function animate(now: number) {
    const elapsed = now - startTime;
    ctx?.clearRect(0, 0, window.innerWidth, window.innerHeight);

    let aliveCount = 0;

    particles.forEach((p) => {
      p.x += p.vx;
      p.y += p.vy;
      p.vy += 0.38; // Gravity
      p.vx *= 0.98; // Air resistance
      p.rotation += p.vRot;

      if (elapsed > 1200) {
        p.alpha -= 0.02;
      }

      if (p.alpha > 0 && p.y < window.innerHeight + 50) {
        aliveCount++;
        if (ctx) {
          ctx.save();
          ctx.globalAlpha = Math.max(0, p.alpha);
          ctx.translate(p.x, p.y);
          ctx.rotate((p.rotation * Math.PI) / 180);
          ctx.fillStyle = p.color;
          ctx.fillRect(-p.size / 2, -p.size / 2, p.size, p.size * 0.6);
          ctx.restore();
        }
      }
    });

    if (aliveCount > 0 && elapsed < 3500) {
      animId = requestAnimationFrame(animate);
    } else {
      cancelAnimationFrame(animId);
      if (document.body.contains(canvas)) {
        document.body.removeChild(canvas);
      }
    }
  }

  animId = requestAnimationFrame(animate);
}
