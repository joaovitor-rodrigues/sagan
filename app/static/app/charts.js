/* SAGAN — camada de hover para as figuras SVG geradas por scripts/make_figures.py.
 * Linhas/pontos: cruz vertical + ponto destacado + tooltip com os valores.
 * Barras: tooltip a partir do atributo data-tip. Sem dependências. */
(function () {
  "use strict";
  var NS = "http://www.w3.org/2000/svg";

  function fmt(v, d) {
    return Number(v).toLocaleString("pt-BR", { minimumFractionDigits: d, maximumFractionDigits: d, useGrouping: Math.abs(v) >= 10000 });
  }

  function tooltipFor(fig) {
    var tip = fig.querySelector(".sg-tooltip");
    if (!tip) {
      tip = document.createElement("div");
      tip.className = "sg-tooltip";
      tip.setAttribute("role", "status");
      fig.appendChild(tip);
    }
    return tip;
  }

  function place(tip, fig, clientX, clientY) {
    var r = fig.getBoundingClientRect();
    var x = Math.min(Math.max(clientX - r.left, 70), r.width - 70);
    tip.style.left = x + "px";
    tip.style.top = (clientY - r.top) + "px";
    tip.classList.add("on");
  }

  function svgPoint(svg, evt) {
    var pt = svg.createSVGPoint();
    pt.x = evt.clientX; pt.y = evt.clientY;
    return pt.matrixTransform(svg.getScreenCTM().inverse());
  }

  function nearest(xs, v) {
    var lo = 0, hi = xs.length - 1;
    while (hi - lo > 1) {
      var mid = (lo + hi) >> 1;
      if (xs[mid] < v) lo = mid; else hi = mid;
    }
    return Math.abs(xs[lo] - v) <= Math.abs(xs[hi] - v) ? lo : hi;
  }

  function initSeries(svg) {
    var h = JSON.parse(svg.getAttribute("data-hover"));
    var fig = svg.closest(".figure") || svg.parentNode;
    var tip = tooltipFor(fig);
    var tx = function (v) { return h.logx ? Math.log10(v) : v; };
    var X = function (v) { return h.sx[2] + (tx(v) - h.sx[0]) / (h.sx[1] - h.sx[0]) * (h.sx[3] - h.sx[2]); };
    var Y = function (v) { return h.sy[2] + (v - h.sy[0]) / (h.sy[1] - h.sy[0]) * (h.sy[3] - h.sy[2]); };
    var invX = function (px) {
      var v = h.sx[0] + (px - h.sx[2]) / (h.sx[3] - h.sx[2]) * (h.sx[1] - h.sx[0]);
      return h.logx ? Math.pow(10, v) : v;
    };

    var cross = document.createElementNS(NS, "line");
    cross.setAttribute("class", "sg-cross");
    cross.setAttribute("y1", h.sy[3]); cross.setAttribute("y2", h.sy[2]);
    var dot = document.createElementNS(NS, "circle");
    dot.setAttribute("class", "sg-hl"); dot.setAttribute("r", 5);
    dot.style.fill = h.color;
    var g = document.createElementNS(NS, "g");
    g.setAttribute("class", "sg-hover"); g.style.display = "none";
    g.appendChild(cross); g.appendChild(dot);
    svg.appendChild(g);

    function show(evt) {
      var p = svgPoint(svg, evt);
      if (p.x < h.sx[2] || p.x > h.sx[3]) { hide(); return; }
      var i = nearest(h.x, invX(p.x));
      if (h.y[i] === null) return;
      var px = X(h.x[i]), py = Y(h.y[i]);
      cross.setAttribute("x1", px); cross.setAttribute("x2", px);
      dot.setAttribute("cx", px); dot.setAttribute("cy", py);
      g.style.display = "";
      var txt = h.xl + ": " + fmt(h.x[i], h.xd) + " · " + h.yl + ": " + fmt(h.y[i], h.yd);
      (h.series || []).forEach(function (s) { txt += " · " + s.name + ": " + fmt(s.y[i], s.d); });
      tip.textContent = txt;
      var ctm = svg.getScreenCTM();
      place(tip, fig, ctm.a * px + ctm.e, ctm.d * py + ctm.f);
    }
    function hide() { g.style.display = "none"; tip.classList.remove("on"); }
    svg.addEventListener("mousemove", show);
    svg.addEventListener("mouseleave", hide);
    svg.addEventListener("touchstart", function (e) { show(e.touches[0]); }, { passive: true });
  }

  function initBars(svg) {
    var fig = svg.closest(".figure") || svg.parentNode;
    var tip = tooltipFor(fig);
    svg.querySelectorAll("[data-tip]").forEach(function (el) {
      el.addEventListener("mousemove", function (e) {
        tip.textContent = el.getAttribute("data-tip");
        place(tip, fig, e.clientX, e.clientY);
      });
      el.addEventListener("mouseleave", function () { tip.classList.remove("on"); });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("svg.sg-chart[data-hover]").forEach(initSeries);
    document.querySelectorAll("svg.sg-chart").forEach(function (s) {
      if (s.querySelector("[data-tip]")) initBars(s);
    });
  });
})();
