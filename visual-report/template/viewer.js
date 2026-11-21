(() => {
  const MEDIA = 'img, video';
  const inPage = el => !el.closest('[data-no-zoom], .vr-viewer');
  const slideOf = el => el.closest('.pair') || el.closest('figure') || el;

  const slides = () => {
    const list = [];
    for (const el of document.querySelectorAll(MEDIA)) {
      if (!inPage(el)) continue;
      const slide = slideOf(el);
      if (!list.includes(slide)) list.push(slide);
    }
    return list;
  };

  const ownCaption = node => {
    const cap = [...node.children].find(child => child.tagName === 'FIGCAPTION');
    return cap ? cap.textContent.trim() : '';
  };

  const mediaLabel = el => {
    const figure = el.closest('figure');
    const fromFigure = figure && !figure.classList.contains('pair') ? ownCaption(figure) : '';
    return fromFigure || el.getAttribute('title') || el.getAttribute('alt') || '';
  };

  const slideCaption = slide => {
    if (slide.matches(MEDIA)) return mediaLabel(slide);
    const own = ownCaption(slide);
    if (own) return own;
    const first = slide.querySelector(MEDIA);
    return first ? mediaLabel(first) : '';
  };

  const viewer = document.createElement('div');
  viewer.className = 'vr-viewer';
  viewer.hidden = true;
  viewer.setAttribute('role', 'dialog');
  viewer.setAttribute('aria-modal', 'true');
  viewer.innerHTML = '<div class="vr-stage"></div>'
    + '<div class="vr-bar"><span class="vr-count"></span><span class="vr-caption"></span></div>'
    + '<button type="button" class="vr-nav vr-prev" aria-label="Previous">&#8249;</button>'
    + '<button type="button" class="vr-nav vr-next" aria-label="Next">&#8250;</button>'
    + '<button type="button" class="vr-close" aria-label="Close">&#215;</button>';
  document.body.appendChild(viewer);

  const stage = viewer.querySelector('.vr-stage');
  let current = -1;
  let opener = null;

  const stopVideos = () => stage.querySelectorAll('video').forEach(v => v.pause());

  const render = index => {
    const all = slides();
    if (!all.length) return;
    current = (index + all.length) % all.length;
    const slide = all[current];
    stopVideos();
    stage.replaceChildren();
    const items = slide.matches(MEDIA) ? [slide] : [...slide.querySelectorAll(MEDIA)].filter(inPage);
    stage.dataset.count = String(items.length);
    const videos = [];
    for (const el of items) {
      const item = document.createElement('figure');
      item.className = 'vr-item';
      let copy;
      if (el.tagName === 'VIDEO') {
        copy = document.createElement('video');
        copy.src = el.currentSrc || el.getAttribute('src') || el.querySelector('source')?.getAttribute('src') || '';
        if (el.poster) copy.poster = el.poster;
        copy.controls = true;
        copy.muted = true;
        copy.loop = true;
        copy.playsInline = true;
        videos.push(copy);
      } else {
        copy = document.createElement('img');
        copy.src = el.currentSrc || el.src;
        copy.alt = el.alt || '';
      }
      item.appendChild(copy);
      if (items.length > 1) {
        const label = document.createElement('figcaption');
        label.textContent = mediaLabel(el);
        item.appendChild(label);
      }
      stage.appendChild(item);
    }
    videos.forEach(v => { v.currentTime = 0; v.play().catch(() => {}); });
    viewer.querySelector('.vr-count').textContent = `${current + 1} / ${all.length}`;
    viewer.querySelector('.vr-caption').textContent = slideCaption(slide);
    const single = all.length < 2;
    viewer.querySelectorAll('.vr-nav').forEach(b => { b.hidden = single; });
  };

  const open = slide => {
    opener = document.activeElement;
    viewer.hidden = false;
    document.documentElement.classList.add('vr-open');
    render(slides().indexOf(slide));
    viewer.querySelector('.vr-close').focus();
  };

  const close = () => {
    stopVideos();
    stage.replaceChildren();
    viewer.hidden = true;
    document.documentElement.classList.remove('vr-open');
    current = -1;
    if (opener && opener.focus) opener.focus();
  };

  viewer.querySelector('.vr-close').addEventListener('click', close);
  viewer.querySelector('.vr-prev').addEventListener('click', () => render(current - 1));
  viewer.querySelector('.vr-next').addEventListener('click', () => render(current + 1));
  viewer.addEventListener('click', event => {
    if (event.target === viewer || event.target === stage) close();
  });
  document.addEventListener('keydown', event => {
    if (viewer.hidden) return;
    if (event.key === 'Escape') close();
    else if (event.key === 'ArrowRight') render(current + 1);
    else if (event.key === 'ArrowLeft') render(current - 1);
  });

  document.addEventListener('click', event => {
    const img = event.target.closest('img');
    if (img && inPage(img) && !img.closest('a')) {
      event.preventDefault();
      open(slideOf(img));
    }
  });

  for (const video of document.querySelectorAll('video')) {
    if (!inPage(video)) continue;
    const holder = document.createElement('span');
    holder.className = 'vr-wrap';
    video.replaceWith(holder);
    holder.appendChild(video);
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'vr-expand';
    button.setAttribute('aria-label', 'Enlarge');
    button.innerHTML = '&#10530;';
    button.addEventListener('click', () => open(slideOf(video)));
    holder.appendChild(button);
  }
})();
