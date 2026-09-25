/* esim.ltd 比价工具。
 *
 * 刻意用原生 JS：全站只有这一个交互组件，引入框架的收益抵不上构建链的代价。
 * 数据来自 /plans.json（构建时生成），前端只做筛选与排序，零后端。
 *
 * 设计原则：
 * 1. 数据与视图分离 —— 所有计算走纯函数，方便测试
 * 2. 无框架、无依赖 —— 一个文件，clone 下来就能改
 * 3. 渐进增强 —— 没有 JS 时仍能看到静态表格
 */

(function () {
  'use strict';

  // ---------------------------------------------------------------- 常量

  var DATA_URL = '/plans.json';

  // 人民币参考汇率，仅用于估算显示。真实汇率请以支付时为准。
  var USD_TO_CNY = 7.2;

  // ---------------------------------------------------------------- 状态

  var state = {
    plans: [],
    brands: {},
    destinations: [],
    filter: {
      dest: 'all',
      days: 7,
      needGb: 5,
      unlimitedOk: true,
      hotspotOnly: false,
    },
    sort: 'value', // 'value' | 'price' | 'brand'
    loaded: false,
    error: null,
  };

  // ---------------------------------------------------------------- 工具

  function $(id) { return document.getElementById(id); }

  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (k) {
        if (k === 'class') node.className = attrs[k];
        else if (k === 'text') node.textContent = attrs[k];
        else node.setAttribute(k, attrs[k]);
      });
    }
    (children || []).forEach(function (c) {
      if (typeof c === 'string') node.appendChild(document.createTextNode(c));
      else if (c) node.appendChild(c);
    });
    return node;
  }

  function fmtUsd(n) {
    return '$' + Number(n).toFixed(2);
  }

  function fmtCny(n) {
    return '约 ¥' + Math.round(n * USD_TO_CNY);
  }

  // ---------------------------------------------------------------- 纯函数层
  // 以下函数不碰 DOM，全部可单测。

  /**
   * 计算每 GB 单价。无限流量套餐返回 null（无法按量计算）。
   */
  function pricePerGb(plan) {
    if (plan.unlimited || !plan.gb) return null;
    return plan.price / plan.gb;
  }

  /**
   * 判断套餐是否满足需求。
   * @param {object} plan
   * @param {object} f 筛选条件
   */
  function matches(plan, f) {
    if (f.dest !== 'all' && plan.dest !== f.dest) return false;
    // 天数：套餐时长必须 >= 需求天数
    if (plan.days < f.days) return false;
    // 流量：无限流量直接通过；有限流量必须够用
    if (!plan.unlimited && plan.gb < f.needGb) return false;
    // 用户不接受无限流量套餐
    if (plan.unlimited && !f.unlimitedOk) return false;
    // 必须支持热点
    if (f.hotspotOnly && !plan.hotspot) return false;
    return true;
  }

  /**
   * 排序。value = 每 GB 单价升序（无限流量排最后）。
   */
  function sortPlans(plans, mode) {
    var copy = plans.slice();
    if (mode === 'price') {
      copy.sort(function (a, b) { return a.price - b.price; });
    } else if (mode === 'brand') {
      copy.sort(function (a, b) {
        if (a.brand === b.brand) return a.price - b.price;
        return a.brand < b.brand ? -1 : 1;
      });
    } else {
      // value 模式：有限流量按每 GB 单价，无限流量统一排在其后并按总价
      copy.sort(function (a, b) {
        var pa = pricePerGb(a), pb = pricePerGb(b);
        if (pa === null && pb === null) return a.price - b.price;
        if (pa === null) return 1;
        if (pb === null) return -1;
        return pa - pb;
      });
    }
    return copy;
  }

  /**
   * 找出最便宜的方案与性价比最高的方案，用于生成结论。
   */
  function analyze(plans) {
    if (!plans.length) return null;
    var cheapest = plans.reduce(function (a, b) {
      return a.price <= b.price ? a : b;
    });
    var withGb = plans.filter(function (p) { return pricePerGb(p) !== null; });
    var bestValue = withGb.length
      ? withGb.reduce(function (a, b) {
          return pricePerGb(a) <= pricePerGb(b) ? a : b;
        })
      : null;
    return {
      count: plans.length,
      cheapest: cheapest,
      bestValue: bestValue,
      unlimited: plans.filter(function (p) { return p.unlimited; }),
    };
  }

  // ---------------------------------------------------------------- 渲染

  function brandName(id) {
    return (state.brands[id] && state.brands[id].name) || id;
  }

  function renderConclusion(result) {
    var box = $('compare-conclusion');
    if (!box) return;

    if (!result) {
      box.innerHTML = '<p class="muted">没有符合条件的套餐。试着放宽天数或流量要求。</p>';
      return;
    }

    var parts = [];
    parts.push('<p>符合条件的有 <strong>' + result.count + '</strong> 个套餐。</p>');

    if (result.bestValue) {
      parts.push(
        '<p>按每 GB 单价算，最划算的是 <strong>' +
        brandName(result.bestValue.brand) + ' ' + result.bestValue.gb + 'GB / ' +
        result.bestValue.days + '天</strong>，' +
        fmtUsd(result.bestValue.price) + '（每 GB ' +
        fmtUsd(pricePerGb(result.bestValue)) + '）。</p>'
      );
    }

    parts.push(
      '<p>总价最低的是 <strong>' + brandName(result.cheapest.brand) + ' ' +
      (result.cheapest.unlimited ? '无限流量' : result.cheapest.gb + 'GB') + ' / ' +
      result.cheapest.days + '天</strong>，' + fmtUsd(result.cheapest.price) + '。</p>'
    );

    if (result.unlimited.length) {
      parts.push(
        '<p class="muted">有 ' + result.unlimited.length +
        ' 个无限流量套餐可选。各品牌的高速流量、公平使用和热点规则不同，请在购买页核对。</p>'
      );
    }

    box.innerHTML = parts.join('');
  }

  function renderTable(plans) {
    var tbody = $('compare-tbody');
    if (!tbody) return;
    tbody.innerHTML = '';

    if (!plans.length) return;

    plans.forEach(function (p) {
      var tr = el('tr');

      var b = state.brands[p.brand] || {};
      var reviewUrl = b.review_url || ('/providers/' + p.brand + '/');
      var buyUrl = b.buy_url || '';

      // 品牌名 → 站内评测页（用户想先了解再买）
      var tdBrand = el('td');
      tdBrand.appendChild(el('a', {
        href: reviewUrl,
        class: 'brand-link',
        text: b.name || p.brand,
      }));
      tr.appendChild(tdBrand);

      tr.appendChild(el('td', {
        text: p.unlimited ? '无限' : p.gb + ' GB',
        class: p.unlimited ? 'gb-unlimited' : 'gb-finite',
      }));

      tr.appendChild(el('td', { text: p.days + ' 天' }));

      var tdPrice = el('td', { class: 'price-cell' });
      tdPrice.appendChild(el('strong', { text: fmtUsd(p.price) }));
      tdPrice.appendChild(el('span', { class: 'cny', text: fmtCny(p.price) }));
      tr.appendChild(tdPrice);

      var ppg = pricePerGb(p);
      tr.appendChild(el('td', {
        text: ppg === null ? '—' : fmtUsd(ppg),
        class: ppg === null ? 'muted' : 'per-gb',
      }));

      tr.appendChild(el('td', {
        text: p.hotspot ? '支持' : '不支持',
        class: p.hotspot ? 'yes' : 'no',
      }));

      // 操作列：官网购买链接。未接入联盟时仍指向官网，但不带追踪参数。
      var tdAction = el('td', { class: 'action-cell' });
      if (buyUrl) {
        tdAction.appendChild(el('a', {
          href: buyUrl,
          class: 'cta-buy',
          rel: 'sponsored nofollow noopener',
          target: '_blank',
          text: '查看套餐',
        }));
      }
      tdAction.appendChild(el('a', {
        href: reviewUrl,
        class: 'cta-review',
        text: '评测',
      }));
      tr.appendChild(tdAction);

      tbody.appendChild(tr);
    });
  }

  function renderStats(result) {
    var box = $('compare-stats');
    if (!box) return;
    if (!result) { box.innerHTML = ''; return; }

    var stats = [];

    stats.push({ label: '可选套餐', value: String(result.count) });

    if (result.bestValue) {
      stats.push({
        label: '最低每 GB 单价',
        value: fmtUsd(pricePerGb(result.bestValue)),
      });
    }

    stats.push({ label: '最低总价', value: fmtUsd(result.cheapest.price) });

    box.innerHTML = stats.map(function (s) {
      return '<div class="stat">' +
        '<div class="stat-label">' + s.label + '</div>' +
        '<div class="stat-value">' + s.value + '</div>' +
        '</div>';
    }).join('');
  }

  function refresh() {
    if (!state.loaded) return;

    var filtered = state.plans.filter(function (p) {
      return matches(p, state.filter);
    });
    var sorted = sortPlans(filtered, state.sort);
    var result = analyze(sorted);

    renderStats(result);
    renderConclusion(result);
    renderTable(sorted);
  }

  // ---------------------------------------------------------------- 表单绑定

  function readForm() {
    var dest = $('f-dest');
    var days = $('f-days');
    var gb = $('f-gb');
    var unl = $('f-unlimited');
    var hot = $('f-hotspot');
    var sort = $('f-sort');

    if (dest) state.filter.dest = dest.value;
    if (days) state.filter.days = parseInt(days.value, 10) || 7;
    if (gb) state.filter.needGb = parseInt(gb.value, 10) || 0;
    if (unl) state.filter.unlimitedOk = unl.checked;
    if (hot) state.filter.hotspotOnly = hot.checked;
    if (sort) state.sort = sort.value;
  }

  function bindForm() {
    ['f-dest', 'f-days', 'f-gb', 'f-unlimited', 'f-hotspot', 'f-sort'].forEach(function (id) {
      var node = $(id);
      if (!node) return;
      var evt = (node.tagName === 'SELECT' || node.type === 'checkbox') ? 'change' : 'input';
      node.addEventListener(evt, function () {
        readForm();
        updateUrl();
        refresh();
      });
    });

    var resetBtn = $('f-reset');
    if (resetBtn) {
      resetBtn.addEventListener('click', function () {
        state.filter = { dest: 'all', days: 7, needGb: 5, unlimitedOk: true, hotspotOnly: false };
        state.sort = 'value';
        writeForm(state.filter, state.sort);
        updateUrl();
        refresh();
      });
    }
  }

  function writeForm(f, sort) {
    var dest = $('f-dest'); if (dest) dest.value = f.dest;
    var days = $('f-days'); if (days) days.value = f.days;
    var gb = $('f-gb'); if (gb) gb.value = f.needGb;
    var unl = $('f-unlimited'); if (unl) unl.checked = f.unlimitedOk;
    var hot = $('f-hotspot'); if (hot) hot.checked = f.hotspotOnly;
    var s = $('f-sort'); if (s) s.value = sort;
  }

  // URL 同步：让筛选结果可分享（这对内容站很重要，用户会给朋友发链接）
  function updateUrl() {
    if (!window.history || !window.history.replaceState) return;
    var q = [];
    q.push('dest=' + encodeURIComponent(state.filter.dest));
    q.push('days=' + state.filter.days);
    q.push('gb=' + state.filter.needGb);
    if (!state.filter.unlimitedOk) q.push('nounlimited=1');
    if (state.filter.hotspotOnly) q.push('hotspot=1');
    if (state.sort !== 'value') q.push('sort=' + state.sort);
    var url = window.location.pathname + '?' + q.join('&');
    window.history.replaceState(null, '', url);
  }

  function readUrl() {
    // 优先读 URL 参数（可分享的筛选状态）
    var params = new URLSearchParams(window.location.search);
    if (params.has('dest')) state.filter.dest = params.get('dest');
    if (params.has('days')) state.filter.days = parseInt(params.get('days'), 10) || 7;
    if (params.has('gb')) state.filter.needGb = parseInt(params.get('gb'), 10) || 0;
    if (params.get('nounlimited') === '1') state.filter.unlimitedOk = false;
    if (params.get('hotspot') === '1') state.filter.hotspotOnly = true;
    if (params.has('sort')) state.sort = params.get('sort');

    // 目的地页会预设 data-dest，作为默认值（URL 参数优先）
    var root = $('compare-app');
    if (root) {
      var preset = root.getAttribute('data-dest');
      if (preset && !params.has('dest')) state.filter.dest = preset;
    }
  }

  /**
   * 目的地页不需要目的地选择器（已由页面决定），
   * 这里把该字段隐藏，避免用户在页内又切到别的国家造成困惑。
   */
  function adjustForPreset() {
    var root = $('compare-app');
    if (!root) return;
    if (root.getAttribute('data-dest')) {
      var destField = $('f-dest');
      if (destField && destField.closest) {
        var wrapper = destField.closest('.field');
        if (wrapper) wrapper.style.display = 'none';
      }
    }
  }

  function fillDestSelect() {
    var sel = $('f-dest');
    if (!sel) return;
    state.destinations.forEach(function (d) {
      var opt = el('option', { value: d.id, text: d.name });
      sel.appendChild(opt);
    });
  }

  // ---------------------------------------------------------------- 初始化

  function init() {
    var root = $('compare-app');
    if (!root) return; // 不在比价页，直接退出

    fetch(DATA_URL)
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      })
      .then(function (data) {
        state.plans = data.plans || [];
        state.destinations = data.destinations || [];
        (data.brands || []).forEach(function (b) {
          state.brands[b.id] = b;
        });
        state.loaded = true;

        fillDestSelect();
        adjustForPreset();
        readUrl();
        writeForm(state.filter, state.sort);
        refresh();

        // 显示数据更新时间（合规：必须标注）
        var stamp = $('compare-updated');
        if (stamp && data._updated) {
          stamp.textContent = '资费数据更新于 ' + data._updated;
        }
      })
      .catch(function (err) {
        state.error = err;
        var box = $('compare-conclusion');
        if (box) {
          box.innerHTML =
            '<p class="muted">资费数据加载失败（' + err.message + '）。' +
            '你可以刷新页面重试，或到各品牌官网直接查询。</p>';
        }
      });

    bindForm();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // 导出纯函数供测试使用（浏览器环境挂在 window 上）
  if (typeof window !== 'undefined') {
    window.__esimCompare = {
      pricePerGb: pricePerGb,
      matches: matches,
      sortPlans: sortPlans,
      analyze: analyze,
    };
  }
})();
