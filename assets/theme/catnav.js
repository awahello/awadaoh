/* ── Awadaoh 左侧分类导航 ─────────────────────────────────────────
   通过官方 /custom/index.js 扩展点注入，不改官方 bundle。

   做三件事：
     1. 读取首页各分组标题，生成左侧固定分类栏
     2. 点击分类 → 平滑滚动到对应分组
     3. 滚动时按视口位置高亮当前分类

   兼容官方两套首页布局：
     V2  .item-card-group-box > .item-card-group-title-box > .item-card-group-title-title
     V1  .group-title
   ------------------------------------------------------------------ */
(function () {
	'use strict';

	if (window.__akCatnavLoaded) return;
	window.__akCatnavLoaded = true;

	var W = 232; // 侧栏宽度，与 nav-theme.css 中 --ak-catnav-w 保持一致
	var BARRIER = 96; // 判定"滚到某分组"时预留的顶部高度
	var TITLE_SEL = '.item-card-group-title-title, .group-title';
	var PANEL_ID = 'ak-catnav';

	var panel = null;
	var items = [];
	var targets = [];
	var activeIdx = -1;
	var rafPending = false;

	function textOf(el) {
		return (el.textContent || '').replace(/\s+/g, ' ').trim();
	}

	/* 找到真正的"分组标题"元素，排除侧栏自身 */
	function collectGroups() {
		var all = [].slice.call(document.querySelectorAll(TITLE_SEL));
		var out = [];
		var seen = {};

		all.forEach(function (el) {
			if (panel && panel.contains(el)) return;
			var name = textOf(el);
			if (!name) return;
			if (name.length > 24) return; // 明显不是分组名
			// 同一分组在两套布局里可能命中最内层和次外层，去重
			var key = name + '@' + Math.round(el.getBoundingClientRect().top);
			if (seen[key]) return;
			seen[key] = 1;
			out.push({ name: name, el: el });
		});
		return out;
	}

	function countOf(titleEl) {
		// 从标题往上找分组容器，统计里面的图标卡数量
		var box = titleEl;
		for (var i = 0; i < 4 && box; i++) {
			box = box.parentElement;
			if (!box) break;
			if (box.querySelector('.item-card-small-icon, .item-card')) {
				return box.querySelectorAll('.item-card-small-icon, .item-card').length;
			}
		}
		return 0;
	}

	function buildPanel() {
		panel = document.createElement('aside');
		panel.id = PANEL_ID;
		panel.innerHTML =
			'<div class="ak-cn-head">' +
			'<span class="ak-cn-title">分类</span>' +
			'<button class="ak-cn-toggle" type="button" title="收起分类栏" aria-label="收起分类栏">‹</button>' +
			'</div>' +
			'<nav class="ak-cn-list" role="navigation" aria-label="站点分类"></nav>';

		panel.querySelector('.ak-cn-toggle').addEventListener('click', function () {
			var collapsed = document.body.classList.toggle('ak-catnav-collapsed');
			this.textContent = collapsed ? '›' : '‹';
			this.title = collapsed ? '展开分类栏' : '收起分类栏';
		});

		document.body.appendChild(panel);
	}

	function goalTop(el) {
		var y = el.getBoundingClientRect().top + (window.pageYOffset || document.documentElement.scrollTop);
		return Math.max(0, y - BARRIER);
	}

	function setActive(i) {
		if (i === activeIdx) return;
		activeIdx = i;
		[].forEach.call(panel.querySelectorAll('.ak-cn-item'), function (n, k) {
			n.classList.toggle('is-active', k === i);
		});
		var cur = panel.querySelector('.ak-cn-item.is-active');
		if (cur && cur.scrollIntoView) {
			cur.scrollIntoView({ block: 'nearest' });
		}
	}

	function onScroll() {
		if (rafPending) return;
		rafPending = true;
		requestAnimationFrame(function () {
			rafPending = false;
			if (!targets.length) return;
			var sy = (window.pageYOffset || document.documentElement.scrollTop) + BARRIER + 8;
			var idx = 0;
			for (var i = 0; i < targets.length; i++) {
				if (goalTop(targets[i].el) <= sy) idx = i;
				else break;
			}
			setActive(idx);
		});
	}

	function render() {
		var groups = collectGroups();
		if (!groups.length) {
			document.body.classList.remove('ak-catnav-on', 'ak-catnav-collapsed');
			if (panel) panel.style.display = 'none';
			targets = [];
			items = [];
			return;
		}

		if (!panel) buildPanel();
		panel.style.display = '';

		// 分组没变化就不重建，避免闪烁
		var sig = groups.map(function (g) { return g.name; }).join('|');
		if (panel.dataset.sig === sig) {
			targets = groups;
			document.body.classList.add('ak-catnav-on');
			onScroll();
			return;
		}

		var list = panel.querySelector('.ak-cn-list');
		list.textContent = '';
		items = [];

		groups.forEach(function (g, i) {
			var a = document.createElement('a');
			a.className = 'ak-cn-item';
			a.href = 'javascript:void(0)';
			a.dataset.idx = String(i);

			var dot = document.createElement('span');
			dot.className = 'ak-cn-dot';

			var name = document.createElement('span');
			name.className = 'ak-cn-name';
			name.textContent = g.name;

			var cnt = document.createElement('span');
			cnt.className = 'ak-cn-count';
			var n = countOf(g.el);
			cnt.textContent = n ? String(n) : '';

			a.appendChild(dot);
			a.appendChild(name);
			a.appendChild(cnt);

			a.addEventListener('click', function (e) {
				e.preventDefault();
				window.scrollTo({ top: goalTop(g.el), behavior: 'smooth' });
				setActive(i);
			});

			list.appendChild(a);
			items.push(a);
		});

		panel.dataset.sig = sig;
		targets = groups;
		activeIdx = -1;
		document.body.classList.add('ak-catnav-on');
		onScroll();
	}

	/* 官方首页是异步渲染 + 路由切换会重建 DOM，用观察器保持同步 */
	function boot() {
		var timer = null;
		var mo = new MutationObserver(function () {
			if (timer) return;
			timer = setTimeout(function () {
				timer = null;
				render();
			}, 120);
		});
		mo.observe(document.body, { childList: true, subtree: true });

		window.addEventListener('scroll', onScroll, { passive: true });
		window.addEventListener('resize', function () {
			render();
		});

		// 首屏可能已经渲染完
		render();
	}

	if (document.readyState === 'loading') {
		document.addEventListener('DOMContentLoaded', boot);
	} else {
		boot();
	}
})();
