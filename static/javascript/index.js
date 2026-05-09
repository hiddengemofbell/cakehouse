// ── FILTER ──
const filterBtns = document.querySelectorAll('.filter-btn');
const items = document.querySelectorAll('.gallery-item');
const emptyState = document.getElementById('emptyState');

filterBtns.forEach(btn => {
  btn.addEventListener('click', () => {
    filterBtns.forEach(b => b.classList.remove('active'));
    btn.classList.add('active');

    const filter = btn.dataset.filter;
    let visible = 0;

    items.forEach(item => {
      const match = filter === 'all' || item.dataset.category === filter;
      item.classList.toggle('hidden', !match);
      if (match) visible++;
    });

    if (emptyState) {
      emptyState.style.display = visible === 0 ? 'block' : 'none';
    }
  });
});

// ── LIKE / DISLIKE ──
const gallery = document.querySelector('.gllry');
const isLoggedIn = gallery && gallery.dataset.loggedIn === 'true';

items.forEach(item => {
  const likeBtn = item.querySelector('.like-btn');
  const dislikeBtn = item.querySelector('.dislike-btn');
  const countEl = item.querySelector('.like-count');
  if (!likeBtn || !dislikeBtn) return;

  let likes = 0;
  let state = null; // null | 'liked' | 'disliked'

  likeBtn.addEventListener('click', e => {
    e.stopPropagation();

    if (!isLoggedIn) {
      /* to be edited */
      alert('Please log in to like a photo.');
      return;
    }

    if (state === 'liked') {
      likes--;
      state = null;
      likeBtn.classList.remove('liked');
      likeBtn.textContent = '♡';
    } else {
      if (state === 'disliked') dislikeBtn.classList.remove('disliked');
      likes++;
      state = 'liked';
      likeBtn.classList.add('liked');
      likeBtn.textContent = '♥';
      dislikeBtn.classList.remove('disliked');
      likeBtn.animate([
        { transform: 'scale(1)' },
        { transform: 'scale(1.4)' },
        { transform: 'scale(1)' }
      ], { duration: 300, easing: 'ease-out' });
    }
    updateCount();
  });

  dislikeBtn.addEventListener('click', e => {
    e.stopPropagation();

    if (!isLoggedIn) {
      alert('Please log in to react to a photo.');
      return;
    }

    if (state === 'disliked') {
      state = null;
      dislikeBtn.classList.remove('disliked');
    } else {
      if (state === 'liked') {
        likes--;
        likeBtn.classList.remove('liked');
        likeBtn.textContent = '♡';
      }
      state = 'disliked';
      dislikeBtn.classList.add('disliked');
    }
    updateCount();
  });

  function updateCount() {
    countEl.textContent = likes > 0 ? `${likes} ♡` : '0 ♡';
    countEl.classList.toggle('has-likes', likes > 0);
  }
});
