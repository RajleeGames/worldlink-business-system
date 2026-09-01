(() => {
  const $ = (selector, context = document) => context.querySelector(selector);
  const $$ = (selector, context = document) => [...context.querySelectorAll(selector)];
  const MOBILE_BREAKPOINT = 900;


  /* ------------------------------------------------------------
     GLOBAL PRELOADER
     Visible in HTML immediately, then released after page load.
     It is also shown for real page navigations and normal form submits.
  ------------------------------------------------------------ */
  const preloader = $('[data-preloader]');
  const preloaderStatus = preloader?.querySelector('.wl-preloader-status');
  const preloaderStartedAt = performance.now();

  const hidePreloader = () => {
    if (!preloader) return;
    const elapsed = performance.now() - preloaderStartedAt;
    const wait = Math.max(0, 260 - elapsed);
    window.setTimeout(() => {
      preloader.classList.add('is-hidden');
      window.setTimeout(() => {
        if (preloader.classList.contains('is-hidden')) preloader.setAttribute('aria-hidden', 'true');
      }, 300);
    }, wait);
  };

  const showPreloader = (message = 'Loading') => {
    if (!preloader) return;
    preloader.removeAttribute('aria-hidden');
    if (preloaderStatus && message) preloaderStatus.textContent = message;
    preloader.classList.remove('is-hidden');
  };

  if (document.readyState === 'complete') hidePreloader();
  else window.addEventListener('load', hidePreloader, {once:true});

  window.addEventListener('pageshow', () => hidePreloader());

  document.addEventListener('click', event => {
    const link = event.target.closest('a[href]');
    if (!link || event.defaultPrevented) return;
    if (link.dataset.noPreloader !== undefined) return;
    if (link.target === '_blank' || link.hasAttribute('download')) return;
    if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;

    const raw = link.getAttribute('href') || '';
    if (!raw || raw.startsWith('#') || raw.startsWith('javascript:') || raw.startsWith('mailto:') || raw.startsWith('tel:')) return;

    let destination;
    try { destination = new URL(link.href, window.location.href); } catch (_) { return; }
    if (destination.origin !== window.location.origin) return;
    if (destination.href === window.location.href) return;

    showPreloader('Opening page');
  });

  document.addEventListener('submit', event => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement)) return;
    if (form.dataset.noPreloader !== undefined) return;
    if (typeof form.checkValidity === 'function' && !form.checkValidity()) return;
    showPreloader(form.closest('.login-card') ? 'Signing in' : 'Saving changes');
  });

  /* ------------------------------------------------------------
     LOGIN CONNECTED-NODE BACKGROUND
     Lightweight canvas network, only initialized when login canvas exists.
  ------------------------------------------------------------ */
  const initLoginNetwork = () => {
    const canvas = $('[data-network-canvas]');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    let width = 0;
    let height = 0;
    let ratio = 1;
    let nodes = [];
    let frame = 0;
    let lastFrame = 0;

    const reset = () => {
      width = window.innerWidth;
      height = window.innerHeight;
      ratio = Math.min(2, Math.max(1, window.devicePixelRatio || 1));
      canvas.width = Math.round(width * ratio);
      canvas.height = Math.round(height * ratio);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      ctx.setTransform(ratio, 0, 0, ratio, 0, 0);

      const count = width < 650 ? 20 : Math.min(42, Math.max(28, Math.round((width * height) / 38000)));
      nodes = Array.from({length:count}, (_, index) => ({
        x: Math.random() * width,
        y: Math.random() * height,
        vx: (Math.random() - .5) * .14,
        vy: (Math.random() - .5) * .14,
        r: index % 7 === 0 ? 1.8 : 1.25,
        phase: Math.random(),
      }));
    };

    const render = now => {
      if (!reducedMotion && now - lastFrame < 32) {
        frame = requestAnimationFrame(render);
        return;
      }
      lastFrame = now;
      ctx.clearRect(0, 0, width, height);

      for (let i = 0; i < nodes.length; i += 1) {
        const a = nodes[i];
        if (!reducedMotion) {
          a.x += a.vx;
          a.y += a.vy;
          if (a.x < -10) a.x = width + 10;
          if (a.x > width + 10) a.x = -10;
          if (a.y < -10) a.y = height + 10;
          if (a.y > height + 10) a.y = -10;
        }

        for (let j = i + 1; j < nodes.length; j += 1) {
          const b = nodes[j];
          const dx = a.x - b.x;
          const dy = a.y - b.y;
          const dist = Math.hypot(dx, dy);
          const limit = width < 650 ? 112 : 145;
          if (dist > limit) continue;

          const alpha = (1 - dist / limit) * .14;
          ctx.strokeStyle = `rgba(13,72,102,${alpha})`;
          ctx.lineWidth = .7;
          ctx.beginPath();
          ctx.moveTo(a.x, a.y);
          ctx.lineTo(b.x, b.y);
          ctx.stroke();

          if (!reducedMotion && (i + j) % 13 === 0) {
            const travel = ((now * .000055) + a.phase + b.phase) % 1;
            const px = a.x + (b.x - a.x) * travel;
            const py = a.y + (b.y - a.y) * travel;
            ctx.fillStyle = 'rgba(13,72,102,.32)';
            ctx.beginPath();
            ctx.arc(px, py, 1.35, 0, Math.PI * 2);
            ctx.fill();
          }
        }

        ctx.fillStyle = 'rgba(13,72,102,.25)';
        ctx.beginPath();
        ctx.arc(a.x, a.y, a.r, 0, Math.PI * 2);
        ctx.fill();
      }

      if (!reducedMotion) frame = requestAnimationFrame(render);
    };

    let resizeTimer;
    window.addEventListener('resize', () => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(reset, 120);
    });

    reset();
    if (reducedMotion) render(0);
    else frame = requestAnimationFrame(render);

    window.addEventListener('pagehide', () => cancelAnimationFrame(frame), {once:true});
  };

  initLoginNetwork();

  /* ------------------------------------------------------------
     SIDEBAR: desktop collapse + mobile drawer
  ------------------------------------------------------------ */
  const sidebar = $('[data-sidebar]');
  const overlay = $('[data-sidebar-overlay]');
  const sidebarToggle = $('[data-sidebar-toggle]');

  const isMobile = () => window.innerWidth <= MOBILE_BREAKPOINT;

  const syncSidebarToggle = () => {
    if (!sidebarToggle) return;
    if (isMobile()) {
      sidebarToggle.setAttribute('aria-expanded', sidebar?.classList.contains('open') ? 'true' : 'false');
    } else {
      sidebarToggle.setAttribute('aria-expanded', document.body.classList.contains('sidebar-collapsed') ? 'false' : 'true');
    }
  };

  const closeMobileSidebar = () => {
    sidebar?.classList.remove('open');
    overlay?.classList.remove('open');
    document.body.classList.remove('mobile-nav-open');
    syncSidebarToggle();
  };

  const openMobileSidebar = () => {
    sidebar?.classList.add('open');
    overlay?.classList.add('open');
    document.body.classList.add('mobile-nav-open');
    syncSidebarToggle();
  };

  const applySavedDesktopSidebarState = () => {
    if (isMobile()) {
      document.body.classList.remove('sidebar-collapsed');
      closeMobileSidebar();
      return;
    }
    const collapsed = localStorage.getItem('wl-sidebar-collapsed') === '1';
    document.body.classList.toggle('sidebar-collapsed', collapsed);
    closeMobileSidebar();
    syncSidebarToggle();
  };

  sidebarToggle?.addEventListener('click', () => {
    if (isMobile()) {
      if (sidebar?.classList.contains('open')) closeMobileSidebar();
      else openMobileSidebar();
      return;
    }

    const collapsed = document.body.classList.toggle('sidebar-collapsed');
    localStorage.setItem('wl-sidebar-collapsed', collapsed ? '1' : '0');
    syncSidebarToggle();
  });

  overlay?.addEventListener('click', closeMobileSidebar);
  $$('.nav-link').forEach(link => link.addEventListener('click', () => {
    if (isMobile()) closeMobileSidebar();
  }));

  applySavedDesktopSidebarState();

  /* ------------------------------------------------------------
     USER DROPDOWN: clean open/close + guaranteed arrow rotation
  ------------------------------------------------------------ */
  const closeDropdowns = (except = null) => {
    $$('[data-dropdown].open').forEach(menu => {
      if (menu === except) return;
      menu.classList.remove('open');
      const wrapper = menu.closest('[data-user-menu]') || menu.parentElement;
      wrapper?.classList.remove('is-open');
      wrapper?.querySelector('[data-dropdown-trigger]')?.setAttribute('aria-expanded', 'false');
    });
  };

  $$('[data-dropdown-trigger]').forEach(button => {
    button.addEventListener('click', event => {
      event.preventDefault();
      event.stopPropagation();

      const wrapper = button.closest('[data-user-menu]') || button.parentElement;
      const menu = wrapper?.querySelector('[data-dropdown]');
      if (!menu) return;

      const willOpen = !menu.classList.contains('open');
      closeDropdowns(menu);
      menu.classList.toggle('open', willOpen);
      wrapper?.classList.toggle('is-open', willOpen);
      button.setAttribute('aria-expanded', willOpen ? 'true' : 'false');
    });
  });

  $$('[data-dropdown]').forEach(menu => {
    menu.addEventListener('click', event => event.stopPropagation());
  });

  document.addEventListener('click', () => closeDropdowns());

  /* ------------------------------------------------------------
     LIVE DESKTOP DATE + TIME
  ------------------------------------------------------------ */
  const clock = $('[data-live-clock]');
  const clockDate = $('[data-clock-date]');
  const clockTime = $('[data-clock-time]');

  const updateClock = () => {
    if (!clock) return;
    const now = new Date();
    if (clockDate) {
      clockDate.textContent = now.toLocaleDateString('en-GB', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
      });
    }
    if (clockTime) {
      clockTime.textContent = now.toLocaleTimeString('en-GB', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false,
      });
    }
  };

  updateClock();
  window.setInterval(updateClock, 1000);

  /* ------------------------------------------------------------
     CUSTOM SELECTS
     Keep Django's native <select> for form submission, but render a
     consistent dropdown so Windows/Chrome cannot inject a dark native menu
     or repeat the arrow background.
  ------------------------------------------------------------ */
  const customSelects = [];

  const closeCustomSelects = (except = null) => {
    customSelects.forEach(instance => {
      if (instance.wrapper === except) return;
      instance.close();
    });
  };

  $$('select.form-control:not([multiple])').forEach(select => {
    if (select.dataset.customSelectReady === '1') return;
    select.dataset.customSelectReady = '1';

    const wrapper = document.createElement('div');
    wrapper.className = 'custom-select';
    select.parentNode.insertBefore(wrapper, select);
    wrapper.appendChild(select);
    select.classList.add('native-select-hidden');

    const trigger = document.createElement('button');
    trigger.type = 'button';
    trigger.className = 'custom-select-trigger';
    trigger.setAttribute('aria-haspopup', 'listbox');
    trigger.setAttribute('aria-expanded', 'false');

    const value = document.createElement('span');
    value.className = 'custom-select-value';

    const chevron = document.createElement('span');
    chevron.className = 'custom-select-chevron';
    chevron.setAttribute('aria-hidden', 'true');
    chevron.innerHTML = '<svg viewBox="0 0 20 20"><path d="m6 8 4 4 4-4"/></svg>';

    trigger.append(value, chevron);

    const menu = document.createElement('div');
    menu.className = 'custom-select-menu';
    menu.setAttribute('role', 'listbox');

    wrapper.append(trigger, menu);

    let optionButtons = [];
    let highlightedIndex = -1;

    const selectedOption = () => select.options[select.selectedIndex] || select.options[0] || null;

    const syncValue = () => {
      const option = selectedOption();
      const text = option?.textContent?.trim() || 'Select…';
      value.textContent = text;
      value.classList.toggle('custom-select-placeholder', !option || option.value === '');
      trigger.disabled = select.disabled;
      wrapper.classList.toggle('is-disabled', select.disabled);
      optionButtons.forEach((button, index) => {
        const isSelected = select.options[index]?.selected;
        button.classList.toggle('is-selected', Boolean(isSelected));
        button.setAttribute('aria-selected', isSelected ? 'true' : 'false');
      });
    };

    const close = () => {
      wrapper.classList.remove('is-open');
      trigger.setAttribute('aria-expanded', 'false');
      highlightedIndex = -1;
      optionButtons.forEach(button => button.classList.remove('is-highlighted'));
    };

    const open = () => {
      if (select.disabled) return;
      closeCustomSelects(wrapper);
      closeDropdowns();
      wrapper.classList.add('is-open');
      trigger.setAttribute('aria-expanded', 'true');
      const selectedIndex = Math.max(0, select.selectedIndex);
      highlightedIndex = selectedIndex;
      optionButtons[selectedIndex]?.classList.add('is-highlighted');
      optionButtons[selectedIndex]?.scrollIntoView({block:'nearest'});
    };

    const choose = index => {
      const option = select.options[index];
      if (!option || option.disabled) return;
      select.selectedIndex = index;
      select.dispatchEvent(new Event('change', {bubbles:true}));
      syncValue();
      close();
      trigger.focus();
    };

    const buildOptions = () => {
      menu.innerHTML = '';
      optionButtons = [];

      if (!select.options.length) {
        const empty = document.createElement('div');
        empty.className = 'custom-select-empty';
        empty.textContent = 'No options available';
        menu.appendChild(empty);
        syncValue();
        return;
      }

      [...select.options].forEach((option, index) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'custom-select-option';
        button.setAttribute('role', 'option');
        button.textContent = option.textContent.trim() || '—';
        button.disabled = option.disabled;
        button.classList.toggle('is-disabled', option.disabled);
        button.addEventListener('click', event => {
          event.preventDefault();
          event.stopPropagation();
          choose(index);
        });
        menu.appendChild(button);
        optionButtons.push(button);
      });

      syncValue();
    };

    trigger.addEventListener('click', event => {
      event.preventDefault();
      event.stopPropagation();
      wrapper.classList.contains('is-open') ? close() : open();
    });

    trigger.addEventListener('keydown', event => {
      const enabledIndexes = optionButtons
        .map((button, index) => button.disabled ? -1 : index)
        .filter(index => index >= 0);
      if (!enabledIndexes.length) return;

      if (['ArrowDown','ArrowUp','Home','End','Enter',' '].includes(event.key)) {
        event.preventDefault();
      }

      if (!wrapper.classList.contains('is-open') && ['ArrowDown','ArrowUp','Enter',' '].includes(event.key)) {
        open();
        return;
      }

      if (event.key === 'Escape') {
        close();
        return;
      }

      if (!wrapper.classList.contains('is-open')) return;

      const currentPos = Math.max(0, enabledIndexes.indexOf(highlightedIndex));
      let nextPos = currentPos;
      if (event.key === 'ArrowDown') nextPos = Math.min(enabledIndexes.length - 1, currentPos + 1);
      if (event.key === 'ArrowUp') nextPos = Math.max(0, currentPos - 1);
      if (event.key === 'Home') nextPos = 0;
      if (event.key === 'End') nextPos = enabledIndexes.length - 1;
      if (event.key === 'Enter' || event.key === ' ') {
        choose(highlightedIndex >= 0 ? highlightedIndex : enabledIndexes[0]);
        return;
      }

      highlightedIndex = enabledIndexes[nextPos];
      optionButtons.forEach(button => button.classList.remove('is-highlighted'));
      optionButtons[highlightedIndex]?.classList.add('is-highlighted');
      optionButtons[highlightedIndex]?.scrollIntoView({block:'nearest'});
    });

    select.addEventListener('change', syncValue);
    select.addEventListener('invalid', () => {
      wrapper.classList.add('is-invalid');
      trigger.focus();
    });
    select.addEventListener('input', () => wrapper.classList.remove('is-invalid'));

    select.form?.addEventListener('reset', () => window.setTimeout(syncValue, 0));

    const observer = new MutationObserver(() => buildOptions());
    observer.observe(select, {childList:true,subtree:true,attributes:true,attributeFilter:['disabled','selected','label']});

    buildOptions();
    customSelects.push({wrapper,close,syncValue,buildOptions});
  });

  document.addEventListener('click', () => closeCustomSelects());

  /* ------------------------------------------------------------
     TOASTS
  ------------------------------------------------------------ */
  $$('[data-toast-close]').forEach(button => {
    button.addEventListener('click', () => button.closest('[data-toast]')?.remove());
  });

  window.setTimeout(() => {
    $$('[data-toast]').forEach(toast => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(-4px)';
      window.setTimeout(() => toast.remove(), 190);
    });
  }, 4500);

  /* ------------------------------------------------------------
     MODALS
  ------------------------------------------------------------ */
  $$('[data-modal-open]').forEach(button => {
    button.addEventListener('click', () => {
      document.querySelector(`[data-modal="${button.dataset.modalOpen}"]`)?.classList.add('open');
    });
  });

  $$('[data-modal-close]').forEach(button => {
    button.addEventListener('click', () => button.closest('[data-modal]')?.classList.remove('open'));
  });

  $$('[data-modal]').forEach(modal => {
    modal.addEventListener('click', event => {
      if (event.target === modal) modal.classList.remove('open');
    });
  });

  document.addEventListener('keydown', event => {
    if (event.key !== 'Escape') return;
    $$('[data-modal].open').forEach(modal => modal.classList.remove('open'));
    closeCustomSelects();
    closeDropdowns();
    if (isMobile()) closeMobileSidebar();
  });

  /* ------------------------------------------------------------
     LOADING BUTTONS
  ------------------------------------------------------------ */
  $$('[data-loading-button]').forEach(button => {
    const ownerForm = button.closest('form');
    if (ownerForm?.matches('[data-transaction-form]')) return;
    ownerForm?.addEventListener('submit', () => {
      if (button.disabled) return;
      button.disabled = true;
      button.dataset.originalHtml = button.innerHTML;
      button.innerHTML = '<span>Working…</span>';
    });
  });

  /* ------------------------------------------------------------
     PASSWORD VISIBILITY
  ------------------------------------------------------------ */
  $$('[data-password-toggle]').forEach(button => {
    button.addEventListener('click', () => {
      const input = button.closest('.password-wrap')?.querySelector('input');
      if (!input) return;
      const showing = input.type === 'text';
      input.type = showing ? 'password' : 'text';
      button.classList.toggle('is-visible', !showing);
      button.setAttribute('aria-label', showing ? 'Show password' : 'Hide password');
    });
  });

  /* ------------------------------------------------------------
     TRANSACTION ENGINE V1.4
     Multi-line products/services/custom work with live totals.
  ------------------------------------------------------------ */
  const formatMoney = value => new Intl.NumberFormat('en-US', {
    maximumFractionDigits: 0,
  }).format(Number(value || 0));

  const parseJsonScript = id => {
    const node = document.getElementById(id);
    if (!node) return [];
    try { return JSON.parse(node.textContent || '[]'); }
    catch (_) { return []; }
  };

  const initTransactionBuilder = () => {
    const form = $('[data-transaction-form]');
    const builder = $('[data-transaction-builder]');
    if (!form || !builder) return;

    const currency = form.dataset.currency || 'TZS';
    const isAdmin = form.dataset.isAdmin === '1';
    const products = parseJsonScript('transaction-products-data');
    const services = parseJsonScript('transaction-services-data');
    const draft = parseJsonScript('transaction-line-draft');

    const hiddenLines = $('[data-transaction-lines-json]', form);
    const linesEl = $('[data-transaction-lines]', form);
    const emptyEl = $('[data-transaction-lines-empty]', form);
    const countEl = $('[data-line-count]', form);
    const searchEl = $('[data-line-search]', form);
    const resultsEl = $('[data-line-results]', form);
    const clearEl = $('[data-line-clear]', form);
    const selectedEl = $('[data-selected-item]', form);
    const customField = $('[data-custom-line-field]', form);
    const customDescription = $('[data-custom-description]', form);
    const quantityEl = $('[data-line-quantity]', form);
    const priceEl = $('[data-line-price]', form);
    const addLineButton = $('[data-add-transaction-line]', form);
    const builderError = $('[data-line-builder-error]', form);
    const discountEl = $('[data-role="transaction-discount"]', form);
    const paymentEl = $('[data-role="transaction-payment"]', form);
    const kindEl = $('[data-role="transaction-kind"]', form);
    const accountEl = $('[data-role="payment-account"]', form);
    const customerEl = $('#id_customer', form);
    const projectEl = $('#id_project', form);
    const payFullButton = $('[data-pay-full]', form);
    const summarySubtotal = $('[data-summary-subtotal]', form);
    const summaryTotal = $('[data-summary-total]', form);
    const summaryPaid = $('[data-summary-paid]', form);
    const summaryBalance = $('[data-summary-balance]', form);
    const summaryCost = $('[data-summary-cost]', form);
    const summaryProfit = $('[data-summary-profit]', form);
    const summaryMessage = $('[data-summary-message]', form);
    const mobileTotal = $('[data-mobile-total]', form);
    const completeButtons = $$('[data-complete-transaction], .tx-mobile-submit button[type="submit"]', form);
    const balanceRow = summaryBalance?.closest('.tx-summary-balance');

    let lineType = 'product';
    let selectedItem = null;
    let highlightedResult = -1;

    const toNumber = value => {
      const n = Number.parseFloat(value);
      return Number.isFinite(n) ? n : 0;
    };
    const money = value => `${currency} ${formatMoney(value)}`;
    const safeText = value => String(value ?? '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
    const makeUid = () => window.crypto?.randomUUID?.() || `line-${Date.now()}-${Math.random().toString(16).slice(2)}`;

    const catalogById = (type, itemId) => {
      const list = type === 'product' ? products : services;
      return list.find(item => String(item.id) === String(itemId)) || null;
    };

    let lines = Array.isArray(draft) ? draft.map(item => {
      const type = ['product', 'service', 'custom'].includes(item.type) ? item.type : 'custom';
      const catalog = type === 'custom' ? null : catalogById(type, item.item_id);
      return {
        uid: item.uid || makeUid(),
        type,
        item_id: type === 'custom' ? null : item.item_id,
        description: item.description || catalog?.name || '',
        quantity: Math.max(.01, toNumber(item.quantity) || 1),
        unit_price: Math.max(0, toNumber(item.unit_price)),
        unit_cost: type === 'product' ? toNumber(catalog?.cost ?? item.unit_cost) : 0,
      };
    }) : [];

    const syncHidden = () => {
      if (!hiddenLines) return;
      hiddenLines.value = JSON.stringify(lines.map(line => ({
        uid: line.uid,
        type: line.type,
        item_id: line.item_id,
        description: line.description,
        quantity: String(line.quantity),
        unit_price: String(line.unit_price),
        unit_cost: String(line.unit_cost || 0),
      })));
    };

    const showBuilderError = message => {
      if (!builderError) return;
      builderError.textContent = message;
      builderError.hidden = !message;
    };

    const clearSelectedItem = ({keepSearch = false} = {}) => {
      selectedItem = null;
      if (!keepSearch && searchEl) searchEl.value = '';
      if (clearEl) clearEl.hidden = true;
      if (selectedEl) {
        selectedEl.hidden = true;
        selectedEl.innerHTML = '';
      }
      if (priceEl) priceEl.value = '';
    };

    const showSelectedItem = item => {
      selectedItem = item;
      if (searchEl) searchEl.value = item.name || '';
      if (priceEl) priceEl.value = item.price || '';
      if (clearEl) clearEl.hidden = false;
      if (selectedEl) {
        const stock = item.type === 'product' ? ` · ${formatMoney(item.stock)} in stock` : '';
        selectedEl.innerHTML = `<strong>${safeText(item.name)}</strong> · ${safeText(item.category || '')}${safeText(stock)}`;
        selectedEl.hidden = false;
      }
      if (resultsEl) resultsEl.hidden = true;
      showBuilderError('');
    };

    const activeCatalog = () => lineType === 'product' ? products : services;

    const filteredCatalog = query => {
      const normalized = String(query || '').trim().toLowerCase();
      const list = activeCatalog();
      if (!normalized) return list.slice(0, 10);
      return list.filter(item => {
        const haystack = `${item.name || ''} ${item.sku || ''} ${item.category || ''}`.toLowerCase();
        return haystack.includes(normalized);
      }).slice(0, 12);
    };

    const renderCatalogResults = () => {
      if (!resultsEl || lineType === 'custom') return;
      const items = filteredCatalog(searchEl?.value || '');
      highlightedResult = -1;

      if (!items.length) {
        resultsEl.innerHTML = '<div class="tx-catalog-empty">No matching item found.</div>';
        resultsEl.hidden = false;
        return;
      }

      resultsEl.innerHTML = items.map((item, index) => {
        const out = item.type === 'product' && toNumber(item.stock) <= 0;
        const meta = item.type === 'product'
          ? `${item.sku || 'No SKU'} · ${item.category || 'Product'}`
          : `${item.category || 'Service'}`;
        const side = item.type === 'product'
          ? `${formatMoney(item.stock)} stock`
          : 'Saved service';
        return `<button type="button" class="tx-catalog-result" data-catalog-index="${index}" data-catalog-id="${safeText(item.id)}" ${out ? 'disabled' : ''}>
          <strong>${safeText(item.name)}</strong>
          <span>${safeText(money(item.price))}</span>
          <small>${safeText(meta)}</small>
          <small class="${out ? 'out' : ''}">${safeText(out ? 'Out of stock' : side)}</small>
        </button>`;
      }).join('');
      resultsEl.hidden = false;
    };

    const setLineType = type => {
      lineType = ['product', 'service', 'custom'].includes(type) ? type : 'product';
      $$('[data-line-type]', form).forEach(button => {
        const active = button.dataset.lineType === lineType;
        button.classList.toggle('is-active', active);
        button.setAttribute('aria-selected', active ? 'true' : 'false');
      });

      const catalogField = $('[data-catalog-field]', form);
      if (catalogField) catalogField.hidden = lineType === 'custom';
      if (customField) customField.hidden = lineType !== 'custom';
      clearSelectedItem();
      if (customDescription) customDescription.value = '';
      if (quantityEl) quantityEl.value = '1';
      if (resultsEl) resultsEl.hidden = true;
      showBuilderError('');

      if (searchEl) {
        searchEl.placeholder = lineType === 'service'
          ? 'Search saved services by name or category'
          : 'Search by name, SKU or category';
      }
    };

    const currentProductRequested = productId => lines
      .filter(line => line.type === 'product' && String(line.item_id) === String(productId))
      .reduce((sum, line) => sum + toNumber(line.quantity), 0);

    const addLine = () => {
      const quantity = toNumber(quantityEl?.value);
      const price = toNumber(priceEl?.value);
      if (quantity <= 0) {
        showBuilderError('Quantity must be greater than zero.');
        quantityEl?.focus();
        return;
      }
      if (price <= 0) {
        showBuilderError('Enter a unit price greater than zero.');
        priceEl?.focus();
        return;
      }

      let description = '';
      let itemId = null;
      let unitCost = 0;

      if (lineType === 'custom') {
        description = customDescription?.value?.trim() || '';
        if (!description) {
          showBuilderError('Enter a description for the custom item.');
          customDescription?.focus();
          return;
        }
      } else {
        if (!selectedItem) {
          showBuilderError(`Choose a ${lineType === 'product' ? 'product' : 'saved service'} first.`);
          searchEl?.focus();
          renderCatalogResults();
          return;
        }
        description = selectedItem.name;
        itemId = selectedItem.id;
        unitCost = lineType === 'product' ? toNumber(selectedItem.cost) : 0;

        if (lineType === 'product') {
          const available = toNumber(selectedItem.stock);
          const already = currentProductRequested(itemId);
          if (already + quantity > available) {
            showBuilderError(`Only ${formatMoney(available)} of ${selectedItem.name} is available. You already added ${formatMoney(already)}.`);
            quantityEl?.focus();
            return;
          }
        }
      }

      lines.push({
        uid: makeUid(),
        type: lineType,
        item_id: itemId,
        description,
        quantity,
        unit_price: price,
        unit_cost: unitCost,
      });

      renderLines();
      if (lineType === 'custom') {
        if (customDescription) customDescription.value = '';
        if (priceEl) priceEl.value = '';
        if (quantityEl) quantityEl.value = '1';
        customDescription?.focus();
      } else {
        clearSelectedItem();
        if (quantityEl) quantityEl.value = '1';
        searchEl?.focus();
      }
      showBuilderError('');
    };

    const renderLines = () => {
      if (!linesEl) return;
      if (emptyEl) emptyEl.hidden = lines.length > 0;
      if (countEl) countEl.textContent = `${lines.length} ${lines.length === 1 ? 'item' : 'items'}`;

      linesEl.innerHTML = lines.map((line, index) => {
        const catalog = line.type === 'custom' ? null : catalogById(line.type, line.item_id);
        const meta = line.type === 'product'
          ? `${catalog?.sku || 'Product'}${catalog?.category ? ` · ${catalog.category}` : ''}`
          : line.type === 'service'
            ? `${catalog?.category || 'Saved service'}`
            : 'Custom work';
        const typeLabel = line.type === 'product' ? 'Product' : line.type === 'service' ? 'Service' : 'Custom';
        const total = toNumber(line.quantity) * toNumber(line.unit_price);
        return `<div class="tx-line-row" data-line-index="${index}">
          <div class="tx-line-main">
            <strong title="${safeText(line.description)}">${safeText(line.description)}</strong>
            <div class="tx-line-meta">
              <span class="tx-line-type-badge ${safeText(line.type)}">${typeLabel}</span>
              <small>${safeText(meta)}</small>
            </div>
          </div>
          <div class="tx-line-cell" data-label="Qty">
            <input class="form-control tx-line-input" type="number" min="0.01" step="0.01" inputmode="decimal" value="${safeText(line.quantity)}" data-line-row-qty="${index}" aria-label="Quantity for ${safeText(line.description)}">
          </div>
          <div class="tx-line-cell" data-label="Unit price">
            <input class="form-control tx-line-input" type="number" min="0.01" step="0.01" inputmode="decimal" value="${safeText(line.unit_price)}" data-line-row-price="${index}" aria-label="Unit price for ${safeText(line.description)}">
          </div>
          <div class="tx-line-total" data-line-row-total="${index}">${safeText(money(total))}</div>
          <button type="button" class="tx-remove-line" data-remove-line="${index}" aria-label="Remove ${safeText(line.description)}">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M9 7V4h6v3M8 7l1 13h6l1-13M10 11v5M14 11v5"/></svg>
          </button>
        </div>`;
      }).join('');

      syncHidden();
      updateSummary();
    };

    const getTotals = () => {
      const subtotal = lines.reduce((sum, line) => sum + toNumber(line.quantity) * toNumber(line.unit_price), 0);
      const cost = lines.reduce((sum, line) => sum + toNumber(line.quantity) * toNumber(line.unit_cost), 0);
      const discount = Math.max(0, toNumber(discountEl?.value));
      const total = Math.max(0, subtotal - discount);
      const payment = Math.max(0, toNumber(paymentEl?.value));
      const balance = Math.max(0, total - payment);
      return {subtotal, cost, discount, total, payment, balance, profit: total - cost};
    };

    const updateSummary = () => {
      const totals = getTotals();
      if (summarySubtotal) summarySubtotal.textContent = money(totals.subtotal);
      if (summaryTotal) summaryTotal.textContent = money(totals.total);
      if (summaryPaid) summaryPaid.textContent = money(totals.payment);
      if (summaryBalance) summaryBalance.textContent = money(totals.balance);
      if (summaryCost) summaryCost.textContent = money(totals.cost);
      if (summaryProfit) summaryProfit.textContent = money(totals.profit);
      if (mobileTotal) mobileTotal.textContent = money(totals.total);
      balanceRow?.classList.toggle('is-debt', totals.balance > 0);

      discountEl?.classList.toggle('is-error', totals.discount >= totals.subtotal && totals.subtotal > 0);
      paymentEl?.classList.toggle('is-error', totals.payment > totals.total && totals.total > 0);

      let message = '';
      let state = '';
      if (!lines.length) {
        message = 'Add at least one item to continue.';
      } else if (totals.discount >= totals.subtotal) {
        message = 'Discount must be less than the transaction subtotal.';
        state = 'is-error';
      } else if (totals.payment > totals.total) {
        message = 'Amount received cannot be greater than the transaction total.';
        state = 'is-error';
      } else if (kindEl?.value === 'project' && !projectEl?.value) {
        message = 'Choose the project for this project transaction.';
        state = 'is-error';
      } else if (totals.payment > 0 && !accountEl?.value) {
        message = 'Choose the money account where this payment was received.';
        state = 'is-error';
      } else if (totals.balance > 0 && !customerEl?.value) {
        message = `${money(totals.balance)} would remain unpaid. Choose a customer so the debt can be tracked.`;
        state = 'is-error';
      } else if (totals.balance > 0) {
        message = `${money(totals.balance)} will remain as customer debt after this payment.`;
        state = 'is-debt';
      } else {
        message = 'Ready to complete. This transaction will be fully paid.';
        state = 'is-ready';
      }

      if (summaryMessage) {
        summaryMessage.textContent = message;
        summaryMessage.classList.remove('is-ready', 'is-debt', 'is-error');
        if (state) summaryMessage.classList.add(state);
      }

      const invalid = !lines.length
        || totals.discount >= totals.subtotal
        || totals.payment > totals.total
        || (kindEl?.value === 'project' && !projectEl?.value)
        || (totals.payment > 0 && !accountEl?.value)
        || (totals.balance > 0 && !customerEl?.value);
      completeButtons.forEach(button => { button.disabled = invalid; });
      syncHidden();
      return !invalid;
    };

    $$('[data-line-type]', form).forEach(button => {
      button.addEventListener('click', () => setLineType(button.dataset.lineType));
    });

    searchEl?.addEventListener('focus', renderCatalogResults);
    searchEl?.addEventListener('input', () => {
      selectedItem = null;
      if (clearEl) clearEl.hidden = !searchEl.value;
      if (selectedEl) selectedEl.hidden = true;
      renderCatalogResults();
    });

    searchEl?.addEventListener('keydown', event => {
      if (!resultsEl || resultsEl.hidden) {
        if (event.key === 'ArrowDown') {
          event.preventDefault();
          renderCatalogResults();
        }
        return;
      }
      const buttons = $$('[data-catalog-index]:not(:disabled)', resultsEl);
      if (!buttons.length) return;
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault();
        const direction = event.key === 'ArrowDown' ? 1 : -1;
        highlightedResult = (highlightedResult + direction + buttons.length) % buttons.length;
        buttons.forEach(button => button.classList.remove('is-highlighted'));
        buttons[highlightedResult]?.classList.add('is-highlighted');
        buttons[highlightedResult]?.scrollIntoView({block:'nearest'});
      } else if (event.key === 'Enter' && highlightedResult >= 0) {
        event.preventDefault();
        buttons[highlightedResult]?.click();
      } else if (event.key === 'Escape') {
        resultsEl.hidden = true;
      }
    });

    resultsEl?.addEventListener('click', event => {
      const button = event.target.closest('[data-catalog-id]');
      if (!button || button.disabled) return;
      const item = activeCatalog().find(candidate => String(candidate.id) === String(button.dataset.catalogId));
      if (item) showSelectedItem(item);
    });

    clearEl?.addEventListener('click', () => {
      clearSelectedItem();
      searchEl?.focus();
      renderCatalogResults();
    });

    addLineButton?.addEventListener('click', addLine);
    priceEl?.addEventListener('keydown', event => {
      if (event.key === 'Enter') {
        event.preventDefault();
        addLine();
      }
    });
    customDescription?.addEventListener('keydown', event => {
      if (event.key === 'Enter') {
        event.preventDefault();
        priceEl?.focus();
      }
    });

    linesEl?.addEventListener('input', event => {
      const qtyInput = event.target.closest('[data-line-row-qty]');
      const priceInput = event.target.closest('[data-line-row-price]');
      if (!qtyInput && !priceInput) return;
      const index = Number((qtyInput || priceInput).dataset.lineRowQty ?? (qtyInput || priceInput).dataset.lineRowPrice);
      const line = lines[index];
      if (!line) return;

      if (qtyInput) {
        const nextQty = toNumber(qtyInput.value);
        if (line.type === 'product') {
          const catalog = catalogById('product', line.item_id);
          const otherQty = lines.reduce((sum, candidate, candidateIndex) => {
            if (candidateIndex === index || candidate.type !== 'product' || String(candidate.item_id) !== String(line.item_id)) return sum;
            return sum + toNumber(candidate.quantity);
          }, 0);
          const max = Math.max(0, toNumber(catalog?.stock) - otherQty);
          qtyInput.classList.toggle('is-error', nextQty <= 0 || nextQty > max);
        } else {
          qtyInput.classList.toggle('is-error', nextQty <= 0);
        }
        line.quantity = nextQty;
      }
      if (priceInput) {
        const nextPrice = toNumber(priceInput.value);
        priceInput.classList.toggle('is-error', nextPrice <= 0);
        line.unit_price = nextPrice;
      }

      const totalNode = $(`[data-line-row-total="${index}"]`, linesEl);
      if (totalNode) totalNode.textContent = money(toNumber(line.quantity) * toNumber(line.unit_price));
      syncHidden();
      updateSummary();
    });

    linesEl?.addEventListener('click', event => {
      const button = event.target.closest('[data-remove-line]');
      if (!button) return;
      const index = Number(button.dataset.removeLine);
      if (!Number.isInteger(index) || !lines[index]) return;
      lines.splice(index, 1);
      renderLines();
    });

    [discountEl, paymentEl].forEach(input => input?.addEventListener('input', updateSummary));
    [kindEl, accountEl, customerEl, projectEl].forEach(input => input?.addEventListener('change', updateSummary));

    payFullButton?.addEventListener('click', () => {
      const {total} = getTotals();
      if (paymentEl) {
        paymentEl.value = total > 0 ? String(total) : '0';
        paymentEl.dispatchEvent(new Event('input', {bubbles:true}));
      }
      accountEl?.focus();
    });

    document.addEventListener('click', event => {
      if (!resultsEl || resultsEl.hidden) return;
      if (event.target.closest('[data-catalog-field]')) return;
      resultsEl.hidden = true;
    });

    document.addEventListener('keydown', event => {
      if (event.key === 'F2') {
        event.preventDefault();
        if (lineType === 'custom') customDescription?.focus();
        else {
          searchEl?.focus();
          renderCatalogResults();
        }
      }
      if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
        event.preventDefault();
        form.requestSubmit();
      }
    });

    form.addEventListener('submit', event => {
      syncHidden();
      const valid = updateSummary();
      if (!valid) {
        event.preventDefault();
        event.stopImmediatePropagation();
        if (summaryMessage) summaryMessage.scrollIntoView({behavior:'smooth',block:'center'});
        return;
      }

      // Validate product quantities one final time in the browser. The server
      // performs the authoritative locked stock check again inside a DB transaction.
      let lineInvalid = false;
      lines.forEach((line, index) => {
        let thisLineInvalid = toNumber(line.quantity) <= 0 || toNumber(line.unit_price) <= 0;
        if (line.type === 'product') {
          const catalog = catalogById('product', line.item_id);
          const totalRequested = currentProductRequested(line.item_id);
          if (totalRequested > toNumber(catalog?.stock)) thisLineInvalid = true;
        }
        lineInvalid = lineInvalid || thisLineInvalid;
        const row = $(`[data-line-index="${index}"]`, linesEl);
        row?.classList.toggle('has-error', thisLineInvalid);
      });
      if (lineInvalid) {
        event.preventDefault();
        event.stopImmediatePropagation();
        showBuilderError('Check item quantities and prices before completing the transaction.');
        builder.scrollIntoView({behavior:'smooth',block:'start'});
      }
    }, {capture:true});

    setLineType('product');
    renderLines();
    updateSummary();
  };

  initTransactionBuilder();

  /* ------------------------------------------------------------
     DASHBOARD CANVAS CHARTS
     Interactive month performance + income mix.
  ------------------------------------------------------------ */
  const getTheme = () => {
    const style = getComputedStyle(document.documentElement);
    return {
      primary: style.getPropertyValue('--primary').trim() || '#0d4866',
      gross: '#6ea6b5',
      expense: '#b9cfd5',
      muted: '#9aa8af',
      grid: '#e7edef',
      text: '#78858d',
      strong: '#27343c',
      empty: '#9aa5ad',
      danger: style.getPropertyValue('--danger').trim() || '#b74b4b',
      white: '#ffffff',
    };
  };

  const setupCanvas = canvas => {
    const rect = canvas.getBoundingClientRect();
    const ratio = Math.max(1, window.devicePixelRatio || 1);
    canvas.width = Math.max(1, Math.round(rect.width * ratio));
    canvas.height = Math.max(1, Math.round(rect.height * ratio));
    const ctx = canvas.getContext('2d');
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    return { ctx, width: rect.width, height: rect.height };
  };

  const readJson = id => {
    const node = document.getElementById(id);
    if (!node) return null;
    try {
      return JSON.parse(node.textContent);
    } catch (_) {
      return null;
    }
  };

  const chartFont = '10px "Aptos", "Segoe UI Variable", "Segoe UI", sans-serif';
  const chartFontMedium = '500 10px "Aptos", "Segoe UI Variable", "Segoe UI", sans-serif';

  const compactNumber = value => {
    const n = Math.abs(Number(value || 0));
    if (n >= 1000000000) return `${(n / 1000000000).toFixed(n >= 10000000000 ? 0 : 1)}B`;
    if (n >= 1000000) return `${(n / 1000000).toFixed(n >= 10000000 ? 0 : 1)}M`;
    if (n >= 1000) return `${(n / 1000).toFixed(n >= 100000 ? 0 : 1)}K`;
    return `${Math.round(n)}`;
  };

  const tooltipMoney = value => `${formatMoney(Math.round(Number(value || 0)))} TZS`;

  const drawEmpty = (ctx, width, height, message, theme) => {
    ctx.clearRect(0, 0, width, height);
    ctx.fillStyle = theme.empty;
    ctx.font = chartFont;
    ctx.textAlign = 'center';
    ctx.fillText(message, width / 2, height / 2);
  };

  const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

  const getTrendGeometry = (width, height, count, values) => {
    const left = width < 520 ? 40 : 52;
    const right = 15;
    const top = 18;
    const bottom = width < 520 ? 32 : 36;
    const chartW = Math.max(10, width - left - right);
    const chartH = Math.max(10, height - top - bottom);
    const maxRaw = Math.max(0, ...values);
    const minRaw = Math.min(0, ...values);
    let upper = maxRaw > 0 ? maxRaw * 1.12 : 1;
    let lower = minRaw < 0 ? minRaw * 1.12 : 0;
    if (upper === lower) upper = lower + 1;

    const xFor = index => count <= 1
      ? left + chartW / 2
      : left + (chartW * index / (count - 1));
    const yFor = value => top + ((upper - Number(value || 0)) / (upper - lower)) * chartH;

    return { left, right, top, bottom, chartW, chartH, upper, lower, xFor, yFor };
  };

  const hideTrendTooltip = canvas => {
    const box = canvas.closest('.chart-box');
    const tooltip = box?.querySelector('[data-chart-tooltip]');
    if (!tooltip) return;
    tooltip.classList.remove('is-visible');
    tooltip.setAttribute('aria-hidden', 'true');
  };

  const updateTrendTooltip = (canvas, index, pointerY, geometry) => {
    const state = canvas._wlTrendState;
    const box = canvas.closest('.chart-box');
    const tooltip = box?.querySelector('[data-chart-tooltip]');
    if (!state || !tooltip || index == null) return;

    const data = state.data;
    const revenue = Number(data.revenue?.[index] || 0);
    const gross = Number(data.gross?.[index] || 0);
    const expenses = Number(data.expenses?.[index] || 0);
    const net = Number(data.net?.[index] ?? (gross - expenses));

    const setText = (selector, text) => {
      const node = tooltip.querySelector(selector);
      if (node) node.textContent = text;
    };

    setText('[data-tip-date]', data.labels?.[index] || '');
    setText('[data-tip-revenue]', tooltipMoney(revenue));
    setText('[data-tip-gross]', tooltipMoney(gross));
    setText('[data-tip-expenses]', tooltipMoney(expenses));
    setText('[data-tip-net]', tooltipMoney(net));

    const netNode = tooltip.querySelector('[data-tip-net]');
    netNode?.classList.toggle('is-negative', net < 0);

    tooltip.classList.add('is-visible');
    tooltip.setAttribute('aria-hidden', 'false');

    const boxWidth = box.clientWidth;
    const boxHeight = box.clientHeight;
    const tooltipWidth = tooltip.offsetWidth || 240;
    const tooltipHeight = tooltip.offsetHeight || 190;
    const pointX = geometry.xFor(index);

    let left = pointX + 15;
    if (left + tooltipWidth > boxWidth - 8) left = pointX - tooltipWidth - 15;
    left = clamp(left, 8, Math.max(8, boxWidth - tooltipWidth - 8));

    const preferredTop = Number.isFinite(pointerY) ? pointerY - tooltipHeight / 2 : 18;
    const top = clamp(preferredTop, 8, Math.max(8, boxHeight - tooltipHeight - 8));

    tooltip.style.left = `${left}px`;
    tooltip.style.top = `${top}px`;
  };

  const renderTrendChart = canvas => {
    const state = canvas._wlTrendState;
    if (!state?.data) return;

    const data = state.data;
    const { ctx, width, height } = setupCanvas(canvas);
    const theme = getTheme();
    const labels = data.labels || [];
    const revenue = (data.revenue || []).map(Number);
    const gross = (data.gross || []).map(Number);
    const expenses = (data.expenses || []).map(Number);

    if (!labels.length) {
      drawEmpty(ctx, width, height, 'No chart data yet', theme);
      return;
    }

    const allValues = [...revenue, ...gross, ...expenses].filter(Number.isFinite);
    const g = getTrendGeometry(width, height, labels.length, allValues);
    state.geometry = g;

    ctx.clearRect(0, 0, width, height);
    ctx.lineWidth = 1;
    ctx.font = chartFont;

    const tickCount = 4;
    for (let i = 0; i <= tickCount; i += 1) {
      const ratio = i / tickCount;
      const y = g.top + g.chartH * ratio;
      const value = g.upper - ((g.upper - g.lower) * ratio);

      ctx.strokeStyle = theme.grid;
      ctx.beginPath();
      ctx.moveTo(g.left, y);
      ctx.lineTo(g.left + g.chartW, y);
      ctx.stroke();

      ctx.fillStyle = theme.text;
      ctx.textAlign = 'right';
      const prefix = value < 0 ? '-' : '';
      ctx.fillText(`${prefix}${compactNumber(value)}`, g.left - 8, y + 3);
    }

    const maxXTicks = width < 520 ? 4 : width < 800 ? 6 : 7;
    const step = labels.length <= maxXTicks ? 1 : Math.ceil((labels.length - 1) / (maxXTicks - 1));
    const xIndexes = new Set([0, labels.length - 1]);
    for (let i = 0; i < labels.length; i += step) xIndexes.add(i);

    [...xIndexes].sort((a, b) => a - b).forEach(index => {
      ctx.fillStyle = theme.text;
      ctx.textAlign = index === 0 ? 'left' : index === labels.length - 1 ? 'right' : 'center';
      ctx.fillText(labels[index], g.xFor(index), height - 9);
    });

    const drawLine = (values, color, lineWidth = 2) => {
      if (!values.length) return;
      ctx.strokeStyle = color;
      ctx.lineWidth = lineWidth;
      ctx.lineJoin = 'round';
      ctx.lineCap = 'round';
      ctx.beginPath();

      values.forEach((value, index) => {
        const x = g.xFor(index);
        const y = g.yFor(value);
        if (index === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();

      values.forEach((value, index) => {
        const x = g.xFor(index);
        const y = g.yFor(value);
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.arc(x, y, width < 520 ? 2.1 : 2.35, 0, Math.PI * 2);
        ctx.fill();
      });
    };

    // Lightest series first so the primary revenue line stays visually dominant.
    drawLine(expenses, theme.expense, 1.8);
    drawLine(gross, theme.gross, 1.9);
    drawLine(revenue, theme.primary, 2.15);

    if (state.hoverIndex != null) {
      const index = clamp(state.hoverIndex, 0, labels.length - 1);
      const x = g.xFor(index);

      ctx.save();
      ctx.strokeStyle = '#c9d5da';
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 5]);
      ctx.beginPath();
      ctx.moveTo(x, g.top);
      ctx.lineTo(x, g.top + g.chartH);
      ctx.stroke();
      ctx.restore();

      [
        [expenses[index] || 0, theme.expense],
        [gross[index] || 0, theme.gross],
        [revenue[index] || 0, theme.primary],
      ].forEach(([value, color]) => {
        const y = g.yFor(value);
        ctx.fillStyle = 'rgba(255,255,255,.92)';
        ctx.beginPath();
        ctx.arc(x, y, 7.2, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.arc(x, y, 4.1, 0, Math.PI * 2);
        ctx.fill();
      });
    }
  };

  const bindTrendInteractions = canvas => {
    if (canvas._wlTrendHandlersBound) return;
    canvas._wlTrendHandlersBound = true;

    const locate = event => {
      const state = canvas._wlTrendState;
      const g = state?.geometry;
      const count = state?.data?.labels?.length || 0;
      if (!g || !count) return null;

      const rect = canvas.getBoundingClientRect();
      const x = event.clientX - rect.left;
      const y = event.clientY - rect.top;
      if (x < g.left - 14 || x > g.left + g.chartW + 14 || y < g.top - 16 || y > g.top + g.chartH + 20) {
        return null;
      }

      const raw = count <= 1 ? 0 : ((x - g.left) / g.chartW) * (count - 1);
      return { index: clamp(Math.round(raw), 0, count - 1), y };
    };

    const showAtEvent = event => {
      const hit = locate(event);
      if (!hit) {
        canvas._wlTrendState.hoverIndex = null;
        hideTrendTooltip(canvas);
        renderTrendChart(canvas);
        return;
      }
      canvas._wlTrendState.hoverIndex = hit.index;
      canvas._wlTrendState.pointerY = hit.y;
      renderTrendChart(canvas);
      updateTrendTooltip(canvas, hit.index, hit.y, canvas._wlTrendState.geometry);
    };

    canvas.addEventListener('pointermove', event => {
      if (event.pointerType === 'touch') return;
      showAtEvent(event);
    });
    canvas.addEventListener('pointerdown', showAtEvent);
    canvas.addEventListener('pointerleave', () => {
      if (!canvas._wlTrendState) return;
      canvas._wlTrendState.hoverIndex = null;
      hideTrendTooltip(canvas);
      renderTrendChart(canvas);
    });
  };

  const drawTrendChart = () => {
    const canvas = $('[data-chart="trend"]');
    const data = readJson('dashboard-trend-data');
    if (!canvas || !data) return;

    const previousIndex = canvas._wlTrendState?.hoverIndex ?? null;
    canvas._wlTrendState = { data, hoverIndex: previousIndex, geometry: null, pointerY: null };
    bindTrendInteractions(canvas);
    hideTrendTooltip(canvas);
    renderTrendChart(canvas);
  };

  const drawKindChart = () => {
    const canvas = $('[data-chart="kind"]');
    const data = readJson('dashboard-kind-data');
    if (!canvas || !data) return;

    const { ctx, width, height } = setupCanvas(canvas);
    const theme = getTheme();
    const labels = data.labels || [];
    const values = data.values || [];
    const maxValue = Math.max(0, ...values);

    if (!labels.length || maxValue <= 0) {
      drawEmpty(ctx, width, height, 'Revenue mix will appear after transactions', theme);
      return;
    }

    ctx.clearRect(0, 0, width, height);
    const left = Math.min(118, Math.max(88, width * .34));
    const right = 16;
    const top = 16;
    const usableH = height - top - 10;
    const rowH = Math.max(38, usableH / labels.length);
    const barW = Math.max(10, width - left - right);
    ctx.font = chartFont;

    labels.forEach((label, index) => {
      const y = top + index * rowH;
      const value = Number(values[index] || 0);
      const widthValue = barW * (value / maxValue);

      ctx.fillStyle = theme.text;
      ctx.textAlign = 'left';
      const shortLabel = label.length > 18 ? `${label.slice(0, 16)}…` : label;
      ctx.fillText(shortLabel, 0, y + 13);

      ctx.fillStyle = '#edf2f4';
      ctx.fillRect(left, y + 3, barW, 11);
      ctx.fillStyle = theme.primary;
      ctx.fillRect(left, y + 3, widthValue, 11);

      ctx.fillStyle = theme.text;
      ctx.textAlign = 'right';
      const money = compactNumber(value);
      ctx.fillText(money, width - right, y + 29);
    });
  };

  const drawCharts = () => {
    drawTrendChart();
    drawKindChart();
  };

  drawCharts();

  let resizeTimer;
  let lastMobileState = isMobile();
  window.addEventListener('resize', () => {
    window.clearTimeout(resizeTimer);
    resizeTimer = window.setTimeout(() => {
      const currentMobileState = isMobile();
      if (currentMobileState !== lastMobileState) {
        applySavedDesktopSidebarState();
        lastMobileState = currentMobileState;
      }
      drawCharts();
    }, 120);
  });

  /* ------------------------------------------------------------
     WORLDLINK ACCORDION SIDEBAR
     One clean expandable navigation family at a time. Active sections
     open automatically from Django classes in sidebar.html.
  ------------------------------------------------------------ */
  const navGroups = $$('[data-nav-group]');
  const navGroupToggles = $$('[data-nav-group-toggle]');

  const setNavGroupOpen = (group, open, remember = true) => {
    if (!group) return;
    group.classList.toggle('open', open);
    group.querySelector('[data-nav-group-toggle]')
      ?.setAttribute('aria-expanded', open ? 'true' : 'false');

    if (remember && group.dataset.navGroup) {
      if (open) localStorage.setItem('wl-open-nav-group', group.dataset.navGroup);
      else if (localStorage.getItem('wl-open-nav-group') === group.dataset.navGroup) {
        localStorage.removeItem('wl-open-nav-group');
      }
    }
  };

  const closeOtherNavGroups = current => {
    navGroups.forEach(group => {
      if (group !== current) setNavGroupOpen(group, false, false);
    });
  };

  const expandDesktopSidebarForGroup = group => {
    if (isMobile() || !document.body.classList.contains('sidebar-collapsed')) return false;
    document.body.classList.remove('sidebar-collapsed');
    localStorage.setItem('wl-sidebar-collapsed', '0');
    syncSidebarToggle();
    window.setTimeout(() => {
      closeOtherNavGroups(group);
      setNavGroupOpen(group, true);
    }, 90);
    return true;
  };

  navGroupToggles.forEach(toggle => {
    toggle.addEventListener('click', event => {
      event.preventDefault();
      event.stopPropagation();

      const group = toggle.closest('[data-nav-group]');
      if (!group) return;

      if (expandDesktopSidebarForGroup(group)) return;

      const willOpen = !group.classList.contains('open');
      if (willOpen) closeOtherNavGroups(group);
      setNavGroupOpen(group, willOpen);
    });
  });

  const activeNavGroup = navGroups.find(group => group.classList.contains('active-group'));
  if (activeNavGroup) {
    closeOtherNavGroups(activeNavGroup);
    setNavGroupOpen(activeNavGroup, true, false);
  } else {
    const rememberedGroup = localStorage.getItem('wl-open-nav-group');
    const remembered = navGroups.find(group => group.dataset.navGroup === rememberedGroup);
    if (remembered && !document.body.classList.contains('sidebar-collapsed')) {
      closeOtherNavGroups(remembered);
      setNavGroupOpen(remembered, true, false);
    }
  }

  $$('.wl-nav-subitem, .wl-nav-direct').forEach(link => {
    link.addEventListener('click', () => {
      if (isMobile()) closeMobileSidebar();
    });
  });

})();

/* ========================================================================== */
/* V1.6 SMS CENTER                                                           */
/* ========================================================================== */

(() => {
  const q = (selector, context = document) => context.querySelector(selector);
  const qa = (selector, context = document) => [...context.querySelectorAll(selector)];

  const segmentCount = message => {
    const text = message || '';
    if (!text.length) return 0;
    const unicode = [...text].some(char => char.charCodeAt(0) > 127);
    const single = unicode ? 70 : 160;
    const multipart = unicode ? 67 : 153;
    return text.length <= single ? 1 : Math.ceil(text.length / multipart);
  };

  const refreshBalance = async button => {
    const url = button?.dataset.url;
    if (!url || button.classList.contains('is-loading')) return;
    button.classList.add('is-loading');
    button.disabled = true;
    try {
      const response = await fetch(url, {
        headers: {'X-Requested-With': 'XMLHttpRequest'},
        credentials: 'same-origin',
      });
      const data = await response.json();
      qa('[data-sms-balance-value]').forEach(node => { node.textContent = data.display || 'Unavailable'; });
      qa('[data-sms-balance-message]').forEach(node => { node.textContent = data.message || ''; });
    } catch (_) {
      qa('[data-sms-balance-message]').forEach(node => { node.textContent = 'Could not refresh balance.'; });
    } finally {
      button.classList.remove('is-loading');
      button.disabled = false;
    }
  };

  qa('[data-sms-refresh-balance]').forEach(button => {
    button.addEventListener('click', () => refreshBalance(button));
  });

  const composer = q('[data-sms-compose]');
  if (composer) {
    const sourceTabs = qa('[data-sms-source]', composer);
    const recipientRows = qa('[data-sms-recipient]', composer);
    const checks = qa('[data-sms-recipient-check]', composer);
    const search = q('[data-sms-recipient-search]', composer);
    const selectedCount = q('[data-sms-selected-count]', composer);
    const summaryRecipients = q('[data-sms-summary-recipients]', composer);
    const message = q('[data-sms-message]', composer);
    const charCount = q('[data-sms-char-count]', composer);
    const segmentCountNode = q('[data-sms-segment-count]', composer);
    const summaryChars = q('[data-sms-summary-chars]', composer);
    const summarySegments = q('[data-sms-summary-segments]', composer);
    const estimatedUnits = q('[data-sms-estimated-units]', composer);
    const preview = q('[data-sms-preview]', composer);
    const templateSelect = q('[data-sms-template-select]', composer);
    let activeSource = 'customer';

    const updateRecipients = () => {
      const selected = checks.filter(input => input.checked && !input.disabled).length;
      if (selectedCount) selectedCount.textContent = selected.toLocaleString();
      if (summaryRecipients) summaryRecipients.textContent = selected.toLocaleString();
      const segments = segmentCount(message?.value || '');
      if (estimatedUnits) estimatedUnits.textContent = (selected * segments).toLocaleString();
    };

    const updateMessage = () => {
      const value = message?.value || '';
      const segments = segmentCount(value);
      if (charCount) charCount.textContent = value.length.toLocaleString();
      if (segmentCountNode) {
        segmentCountNode.textContent = segments.toLocaleString();
        const suffix = segmentCountNode.parentElement;
        if (suffix) {
          suffix.lastChild.textContent = segments === 1 ? ' SMS segment' : ' SMS segments';
        }
      }
      if (summaryChars) summaryChars.textContent = value.length.toLocaleString();
      if (summarySegments) summarySegments.textContent = segments.toLocaleString();
      if (preview) {
        const sample = value
          .replaceAll('{name}', 'Customer')
          .replaceAll('{first_name}', 'Customer')
          .replaceAll('{phone}', '255700000000');
        preview.textContent = sample || 'Your message preview will appear here.';
      }
      updateRecipients();
    };

    const applyRecipientFilter = () => {
      const term = (search?.value || '').trim().toLowerCase();
      recipientRows.forEach(row => {
        const sameSource = row.dataset.source === activeSource;
        const matches = !term || (row.dataset.search || '').includes(term);
        row.classList.toggle('is-hidden-source', !sameSource);
        row.classList.toggle('is-filtered', sameSource && !matches);
      });
      qa('[data-source-empty]', composer).forEach(node => {
        node.classList.toggle('is-hidden-source', node.dataset.sourceEmpty !== activeSource);
      });
    };

    sourceTabs.forEach(tab => {
      tab.addEventListener('click', () => {
        activeSource = tab.dataset.smsSource || 'customer';
        sourceTabs.forEach(item => item.classList.toggle('active', item === tab));
        applyRecipientFilter();
      });
    });

    search?.addEventListener('input', applyRecipientFilter);
    checks.forEach(input => input.addEventListener('change', updateRecipients));

    q('[data-sms-select-visible]', composer)?.addEventListener('click', () => {
      recipientRows.forEach(row => {
        if (row.classList.contains('is-hidden-source') || row.classList.contains('is-filtered') || row.classList.contains('is-disabled')) return;
        const input = q('[data-sms-recipient-check]', row);
        if (input && !input.disabled) input.checked = true;
      });
      updateRecipients();
    });

    q('[data-sms-clear-selection]', composer)?.addEventListener('click', () => {
      checks.forEach(input => { input.checked = false; });
      updateRecipients();
    });

    message?.addEventListener('input', updateMessage);

    qa('[data-sms-token]', composer).forEach(button => {
      button.addEventListener('click', () => {
        if (!message) return;
        const token = button.dataset.smsToken || '';
        const start = message.selectionStart ?? message.value.length;
        const end = message.selectionEnd ?? message.value.length;
        message.setRangeText(token, start, end, 'end');
        message.focus();
        updateMessage();
      });
    });

    templateSelect?.addEventListener('change', () => {
      const option = templateSelect.options[templateSelect.selectedIndex];
      const body = option?.dataset.body;
      if (body !== undefined && message) {
        message.value = body;
        updateMessage();
        message.focus();
      }
    });

    const clientError = q('[data-sms-client-error]', composer);
    const showClientError = text => {
      if (!clientError) return;
      clientError.textContent = text;
      clientError.hidden = false;
      clientError.scrollIntoView({behavior:'smooth', block:'nearest'});
    };
    const clearClientError = () => {
      if (!clientError) return;
      clientError.textContent = '';
      clientError.hidden = true;
    };

    composer.addEventListener('submit', event => {
      clearClientError();
      const selected = checks.filter(input => input.checked && !input.disabled).length;
      const manual = composer.querySelector('[name="manual_recipients"]')?.value.trim() || '';
      if (!selected && !manual) {
        event.preventDefault();
        showClientError('Select at least one recipient or enter a manual phone number.');
        sourceTabs[0]?.focus();
        return;
      }
      if (!message?.value.trim()) {
        event.preventDefault();
        showClientError('Write the SMS message before sending.');
        message?.focus();
      }
    });

    applyRecipientFilter();
    updateMessage();
    updateRecipients();
  }

  const fileInput = q('[data-sms-file-input]');
  const dropZone = q('[data-sms-drop-zone]');
  const fileName = q('[data-sms-file-name]');
  if (fileInput && dropZone) {
    const syncName = () => {
      if (fileName) fileName.textContent = fileInput.files?.[0]?.name || 'Choose CSV file';
    };
    fileInput.addEventListener('change', syncName);
    ['dragenter','dragover'].forEach(name => dropZone.addEventListener(name, () => dropZone.classList.add('is-dragging')));
    ['dragleave','drop'].forEach(name => dropZone.addEventListener(name, () => dropZone.classList.remove('is-dragging')));
  }

  qa('[data-sms-counter-input]').forEach(input => {
    const wrapper = document.createElement('div');
    wrapper.className = 'sms-inline-counter';
    input.insertAdjacentElement('afterend', wrapper);
    const sync = () => {
      const segments = segmentCount(input.value || '');
      wrapper.textContent = `${input.value.length} chars · ${segments} SMS segment${segments === 1 ? '' : 's'}`;
    };
    input.addEventListener('input', sync);
    sync();
  });
})();
