(function () {
  var root = document.documentElement, btn = document.getElementById('theme');
  function cur() {
    return root.dataset.theme ||
      (window.matchMedia && matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  }
  function label() { if (btn) btn.textContent = cur() === 'dark' ? 'Светлая' : 'Тёмная'; }
  label();
  if (btn) btn.addEventListener('click', function () {
    var t = cur() === 'dark' ? 'light' : 'dark';
    root.dataset.theme = t; try { localStorage.setItem('theme', t); } catch (e) {} label();
  });

  // музыка: один плеер на страницу, следующий трек альбома играет сам
  var bar = document.querySelector('.player');
  if (!bar) return;
  var audio = bar.querySelector('audio'), title = bar.querySelector('b'), current = null;
  function play(li) {
    if (current) current.classList.remove('on');
    current = li; li.classList.add('on');
    audio.src = li.dataset.src; title.textContent = li.dataset.title;
    bar.classList.add('on'); audio.play();
  }
  document.querySelectorAll('.album li').forEach(function (li) {
    li.querySelector('button').addEventListener('click', function () {
      if (current === li && !audio.paused) audio.pause(); else if (current === li) audio.play(); else play(li);
    });
  });
  audio.addEventListener('ended', function () {
    var next = current && current.nextElementSibling;
    if (next) play(next);
  });
})();
