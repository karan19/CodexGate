(() => {
  const canvas = document.getElementById('matrix');
  const context = canvas.getContext('2d');
  const toggle = document.getElementById('motion');
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  if (!context) { toggle.hidden = true; return; }
  let paused = reduced.matches, frame, last = 0, drops = [];
  const size = 19, chars = '01{}[]<>/+=:·';
  function resize() {
    const ratio = Math.min(devicePixelRatio || 1, 2);
    canvas.width = innerWidth * ratio; canvas.height = innerHeight * ratio;
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    drops = Array.from({ length: Math.ceil(innerWidth / size) }, () => -Math.random() * innerHeight / size);
    context.fillStyle = '#191410'; context.fillRect(0, 0, innerWidth, innerHeight);
  }
  function draw(time) {
    if (paused || document.hidden) return;
    if (time - last > 85) {
      last = time;
      context.fillStyle = 'rgba(25,20,16,0.08)'; context.fillRect(0, 0, innerWidth, innerHeight);
      context.font = '12px monospace'; context.fillStyle = '#d6a16b';
      drops.forEach((y, x) => {
        context.fillText(chars[Math.floor(Math.random() * chars.length)], x * size, y * size);
        drops[x] = y * size > innerHeight && Math.random() > .98 ? -Math.random() * 30 : y + .55;
      });
    }
    frame = requestAnimationFrame(draw);
  }
  function sync() {
    cancelAnimationFrame(frame);
    toggle.textContent = paused ? 'Animate background' : 'Pause background';
    toggle.setAttribute('aria-pressed', String(paused));
    if (!paused && !document.hidden) frame = requestAnimationFrame(draw);
  }
  toggle.addEventListener('click', () => { paused = !paused; sync(); });
  reduced.addEventListener('change', () => { paused = reduced.matches; sync(); });
  document.addEventListener('visibilitychange', sync);
  addEventListener('resize', resize);
  resize(); sync();
})();
