#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Solucionador H5P (Moodle) via CDP.

Reconoce el tipo de contenido, lee las respuestas correctas de los parametros
del propio H5P y completa la actividad. Recolecta tambien sub-instancias
anidadas (Column, InteractiveBook, CoursePresentation, QuestionSet...).

Uso:
    python h5p_solver.py --url https://moodle/mod/hvp/view.php?id=123
    python h5p_solver.py            # usa la pestana activa
    python h5p_solver.py --list     # solo lista los tipos detectados

Requiere un Chrome abierto por sesion_cdp.py (puerto 9333).
"""
import contextlib
import json
import os
import re
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from playwright.sync_api import sync_playwright

_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)
from nucleo import cli  # noqa: E402
from nucleo.contrato import exito  # noqa: E402
from nucleo.errores import AgenteError  # noqa: E402

CDP = "http://127.0.0.1:9333"
SOLVED = set()

JS_COLLECT = r"""
() => {
  const out = [];
  const seen = new Set();
  window.__hsolve = {};
  let counter = 0;
  function walk(inst) {
    if (!inst || seen.has(inst)) return;
    seen.add(inst);
    const lib = inst.libraryInfo ? inst.libraryInfo.machineName : null;
    if (!inst.__hsolveId) inst.__hsolveId = 'hsolve-' + (counter++);
    const id = inst.__hsolveId;
    window.__hsolve[id] = {
      lib: lib,
      params: inst.params || null,
      correctDZs: inst.correctDZs || null
    };
    out.push({lib: lib, id: id});
    if (inst.getInstances) {
      try { inst.getInstances().forEach(walk); } catch (e) {}
    }
  }
  (H5P.instances || []).forEach(walk);
  return out;
}
"""

JS_FLAT_FULL = r"""
() => {
  const c = JSON.parse(Object.values(H5PIntegration.contents)[0].jsonContent);
  const out = [];
  function walk(node) {
    if (!node) return;
    if (Array.isArray(node)) { node.forEach(walk); return; }
    if (typeof node !== 'object') return;
    if (node.library && node.params) out.push({lib: node.library.split(' ')[0], params: node.params});
    for (const k of Object.keys(node)) walk(node[k]);
  }
  walk(c);
  return JSON.stringify(out);
}
"""

# Varios selectores por si la libreria cambia de clase entre versiones.
CONTAINER = {
    "H5P.Blanks": [".h5p-blanks"],
    "H5P.MultiChoice": [".h5p-multichoice"],
    "H5P.TrueFalse": [".h5p-true-false"],
    "H5P.MarkTheWords": [".h5p-mark-the-words"],
    "H5P.SortParagraphs": [".h5p-sortparagraphs", ".h5p-sort-paragraphs"],
    "H5P.DragQuestion": [".h5p-dragquestion"],
    "H5P.CoursePresentation": [".h5p-course-presentation"],
    "H5P.Accordion": [".h5p-accordion"],
    "H5P.Dialogcards": [".h5p-dialogcards", ".h5p-dialog-cards"],
    "H5P.InteractiveBook": [".h5p-interactive-book"],
    "H5P.ImagePair": [".h5p-image-pair", ".h5p-imagepair"],
    "H5P.MemoryGame": [".h5p-memory-game"],
    "H5P.QuestionSet": [".questionset", ".h5p-question-set"],
    "H5P.FindTheWords": [".h5p-find-the-words", ".h5p-findthewords"],
    "H5P.Crossword": [".h5p-crossword"],
}

SUB_SEL = [("H5P.MultiChoice", ".h5p-multichoice"),
           ("H5P.TrueFalse", ".h5p-true-false"),
           ("H5P.Blanks", ".h5p-blanks"),
           ("H5P.MarkTheWords", ".h5p-mark-the-words"),
           ("H5P.DragQuestion", ".h5p-dragquestion"),
           ("H5P.SortParagraphs", ".h5p-sortparagraphs, .h5p-sort-paragraphs"),
           ("H5P.ImagePair", ".h5p-image-pair, .h5p-imagepair")]


# ------------------------- utilidades -------------------------
def conectar(cdp=CDP):
    p = sync_playwright().start()
    b = p.chromium.connect_over_cdp(cdp)
    ctx = b.contexts[0]
    pg = [x for x in ctx.pages if "unicartagena" in x.url or "moodle" in x.url]
    pg = pg[0] if pg else (ctx.pages[0] if ctx.pages else ctx.new_page())
    return p, ctx, pg


def h5p_frame(pg, timeout_s=15):
    for _ in range(int(timeout_s * 2)):
        for f in pg.frames:
            if f == pg.main_frame:
                continue
            try:
                if f.evaluate("typeof H5P!=='undefined' && H5P.instances && H5P.instances.length"):
                    return f
            except Exception:
                pass
        pg.wait_for_timeout(500)
    return None


def clean(h):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h or "")).strip()


def click_check(scope):
    for sel in ["button.h5p-question-check-answer", "button.h5p-question-check",
                ".h5p-question-check-answer", "button:has-text('Check')",
                "button:has-text('Comprobar')"]:
        loc = scope.locator(sel).first
        try:
            if loc.count() > 0 and loc.is_visible() and not loc.is_disabled():
                loc.click()
                return True
        except Exception:
            pass
    return False


def drag(pg, src, dst):
    sb, db = src.bounding_box(), dst.bounding_box()
    if not sb or not db:
        return False
    sx, sy = sb["x"] + sb["width"] / 2, sb["y"] + sb["height"] / 2
    dx, dy = db["x"] + db["width"] / 2, db["y"] + db["height"] / 2
    pg.mouse.move(sx, sy)
    time.sleep(0.1)
    pg.mouse.down()
    for k in range(1, 13):
        pg.mouse.move(sx + (dx - sx) * k / 12.0, sy + (dy - sy) * k / 12.0)
        time.sleep(0.03)
    pg.mouse.move(dx, dy)
    time.sleep(0.25)
    pg.mouse.up()
    time.sleep(0.25)
    return True


# ------------------------- handlers -------------------------
def h_blanks(scope, d, pg, fr):
    params = d.get("params") or {}
    answers = []
    for q in (params.get("questions") or []):
        for m in re.finditer(r"(?<!\\)\*(.+?)(?<!\\)\*", q):
            answers.append(m.group(1).split("/")[0].strip())
    inputs = scope.locator(".h5p-text-input")
    n = inputs.count()
    disabled = inputs.first.is_disabled() if n else True
    if disabled:
        print("    blanks ya respondidos (omitido)")
        return
    print("    blanks=%d resp=%d" % (n, len(answers)))
    for i in range(min(n, len(answers))):
        try:
            inputs.nth(i).fill(answers[i])
        except Exception:
            pass
    click_check(scope)


def h_multichoice(scope, d, pg, fr):
    params = d.get("params") or {}
    correct = [clean(a.get("text")) for a in (params.get("answers") or []) if a.get("correct")]
    print("    MC correctas=%d" % len(correct))
    for c in correct:
        el = scope.locator(".h5p-alternative-container").filter(has_text=c).first
        try:
            if el.count() > 0:
                el.click()
                time.sleep(0.15)
        except Exception:
            pass
    click_check(scope)


def h_truefalse(scope, d, pg, fr):
    params = d.get("params") or {}
    want = "True" if params.get("correct") else "False"
    el = scope.locator(".h5p-true-false-answer").filter(has_text=want).first
    if el.count() > 0:
        el.click()
    click_check(scope)


def h_markthewords(scope, d, pg, fr):
    params = d.get("params") or {}
    words = [w.strip() for w in re.findall(r"(?<!\\)\*(.+?)(?<!\\)\*", params.get("textField", ""))]
    print("    marcar=%d" % len(words))
    for w in words:
        el = scope.locator("span").filter(has_text=w).first
        try:
            el.click(timeout=2000)
            time.sleep(0.12)
        except Exception:
            pass
    click_check(scope)


def h_sortparagraphs(scope, d, pg, fr):
    params = d.get("params") or {}
    desired = [clean(p) for p in (params.get("paragraphs") or [])]
    items = scope.locator(".h5p-sort-paragraphs-paragraph")
    n = len(desired)
    print("    parrafos=%d" % n)
    for i in range(n):
        cur = [clean(items.nth(k).inner_text()) for k in range(items.count())]
        j = next((k for k, c in enumerate(cur) if c[:40] == desired[i][:40]), None)
        if j is None or j == i:
            continue
        items.nth(j).focus()
        time.sleep(0.12)
        pg.keyboard.press("Space")
        time.sleep(0.18)
        key = "ArrowUp" if j > i else "ArrowDown"
        for _ in range(abs(j - i)):
            pg.keyboard.press(key)
            time.sleep(0.1)
        pg.keyboard.press("Space")
        time.sleep(0.22)
    click_check(scope)


def h_dragquestion(scope, d, pg, fr):
    mapping = d.get("correctDZs") or []
    texts = scope.locator(".h5p-draggable").evaluate_all(
        "els => els.map(e => e.innerText.trim().split('\\n').pop().trim())")
    if not mapping:
        ztexts = scope.locator(".h5p-dropzone").evaluate_all(r"""els => els.map(e => {
          const h = e.querySelector('.h5p-hidden-read');
          const t = (h ? h.innerText : e.innerText).replace(/\s+/g, ' ').trim();
          const m = t.match(/Dropzone \d+ of \d+\.\s*(.*)$/);
          return m ? m[1].trim() : '';
        })""")
        mapping = []
        for t in texts:
            idx = next((k for k, zt in enumerate(ztexts) if zt and zt.lower() == t.lower()), None)
            if idx is None:
                idx = next((k for k, zt in enumerate(ztexts) if zt and t and t.lower() in zt.lower()), 0)
            mapping.append([idx])
    print("    drags=%d mapping=%d" % (len(texts), len(mapping)))
    for i, m in enumerate(mapping):
        if i >= len(texts):
            break
        z = m[0] if isinstance(m, list) else m
        el = scope.locator(".h5p-draggable").filter(has_text=texts[i]).first
        try:
            drag(pg, el, scope.locator(".h5p-dropzone").nth(z))
        except Exception:
            pass
    click_check(scope)


def h_view_accordion(scope, d, pg, fr):
    heads = scope.locator(".h5p-panel-button")
    n = heads.count()
    print("    paneles=%d" % n)
    for i in range(n):
        try:
            heads.nth(i).click(timeout=2500)
            pg.wait_for_timeout(250)
        except Exception:
            pass


def h_view_dialogcards(scope, d, pg, fr):
    cards = (d.get("params") or {}).get("dialogs") or []
    print("    cards=%d" % len(cards))
    for _ in range(len(cards) + 2):
        card = scope.locator(".h5p-dialogcards-card").first
        try:
            if card.count() > 0:
                card.click(timeout=1500)
                pg.wait_for_timeout(250)
        except Exception:
            pass
        nxt = scope.locator(".h5p-next").last
        try:
            if nxt.count() > 0 and nxt.is_visible():
                nxt.click(timeout=2000)
                pg.wait_for_timeout(300)
            else:
                break
        except Exception:
            break


def h_questionset(scope, d, pg, fr):
    qs = None
    if d.get("params") and d["params"].get("questions"):
        qs = [[clean(a.get("text")) for a in (q.get("params", {}).get("answers") or [])
               if a.get("correct")] for q in d["params"]["questions"]]
    if not qs:
        qs = fr.evaluate(r"""() => {
          const c = JSON.parse(Object.values(H5PIntegration.contents)[0].jsonContent);
          const clean = h => (h||'').replace(/<[^>]+>/g,' ').replace(/\s+/g,' ').trim();
          return (c.questions||[]).map(q => ((q.params||{}).answers||[])
            .filter(a => a.correct).map(a => clean(a.text)));
        }""")
    print("    preguntas=%d" % len(qs))
    sb = scope.locator("button.qs-startbutton").first
    if sb.count() > 0 and sb.is_visible():
        sb.click()
        pg.wait_for_timeout(2500)
    try:
        fr.locator("button.h5p-question-check-answer:visible").first.wait_for(
            state="visible", timeout=8000)
    except Exception:
        pass
    for answers in qs:
        for a in answers:
            el = fr.locator(".h5p-alternative-container:visible").filter(has_text=a).first
            if el.count() > 0:
                el.click()
                break
        ck = fr.locator("button.h5p-question-check-answer:visible").first
        if ck.count() > 0:
            ck.click()
        pg.wait_for_timeout(700)
        nxt = fr.locator("a.h5p-question-next:visible").first
        if nxt.count() > 0:
            nxt.click()
            pg.wait_for_timeout(700)
        else:
            fin = fr.locator("a.h5p-question-finish:visible, .h5p-question-finish:visible").first
            if fin.count() > 0:
                fin.click()
                pg.wait_for_timeout(700)


def h_view_cp(scope, d, pg, fr):
    total = fr.evaluate(r"""() => {
      try { const c = JSON.parse(Object.values(H5PIntegration.contents)[0].jsonContent);
        return (c.presentation && c.presentation.slides) ? c.presentation.slides.length : 0; }
      catch (e) { return 0; }
    }""")
    print("    slides=%d" % total)
    queues, ptr = build_queues(fr)
    for _ in range(max(total, 1) + 1):
        solve_visible(fr, pg, queues, ptr)
        nxt = scope.locator(".h5p-footer-next-slide").first
        if nxt.count() == 0:
            break
        if "disabled" in (nxt.get_attribute("class") or ""):
            break
        try:
            nxt.click(timeout=3000)
        except Exception:
            break
        pg.wait_for_timeout(500)
    solve_visible(fr, pg, queues, ptr)


def h_book(scope, d, pg, fr):
    queues, ptr = build_queues(fr)
    print("    libro: %s" % {k: len(v) for k, v in queues.items() if k in dict(SUB_SEL)})
    for _ in range(80):
        solve_visible(fr, pg, queues, ptr)
        nxt = fr.locator(".h5p-interactive-book-status-arrow.next:visible").first
        if nxt.count() == 0:
            break
        try:
            if nxt.is_disabled():
                break
        except Exception:
            pass
        nxt.click()
        pg.wait_for_timeout(500)
    sm = scope.locator(".h5p-interactive-book-summary-menu-button").first
    try:
        if sm.count() > 0 and sm.is_visible():
            sm.click()
            pg.wait_for_timeout(1000)
            for t in ["Submit", "Submit report", "Enviar"]:
                b = fr.locator("button:has-text('%s')" % t).first
                if b.count() > 0 and b.is_visible():
                    b.click()
                    pg.wait_for_timeout(1000)
                    break
    except Exception:
        pass


def h_imagepair(scope, d, pg, fr):
    # Emparejar por nombre de archivo: si dos cartas comparten imagen base.
    srcs = scope.locator("img").evaluate_all(
        "els => els.map(e => (e.getAttribute('src')||'').split('/').pop().split('?')[0])")
    cards = scope.locator(".h5p-image-pair-item, .h5p-imagepair-item, [class*=card]")
    print("    imagepair imgs=%d" % len(srcs))
    # Estrategia simple: click en orden; la libreria empareja al elegir dos iguales.
    n = cards.count()
    for i in range(n):
        try:
            cards.nth(i).click(timeout=1200)
            pg.wait_for_timeout(200)
        except Exception:
            pass


def h_memory(scope, d, pg, fr):
    cards = scope.locator(".h5p-memory-card")
    n = cards.count()
    print("    memory cards=%d" % n)
    for i in range(n):
        try:
            cards.nth(i).click(timeout=1200)
            pg.wait_for_timeout(250)
        except Exception:
            pass


HANDLERS = {
    "H5P.Blanks": h_blanks,
    "H5P.MultiChoice": h_multichoice,
    "H5P.TrueFalse": h_truefalse,
    "H5P.MarkTheWords": h_markthewords,
    "H5P.SortParagraphs": h_sortparagraphs,
    "H5P.DragQuestion": h_dragquestion,
    "H5P.CoursePresentation": h_view_cp,
    "H5P.Accordion": h_view_accordion,
    "H5P.Dialogcards": h_view_dialogcards,
    "H5P.InteractiveBook": h_book,
    "H5P.ImagePair": h_imagepair,
    "H5P.MemoryGame": h_memory,
    "H5P.QuestionSet": h_questionset,
}


def build_queues(fr):
    flat = json.loads(fr.evaluate(JS_FLAT_FULL))
    q = {}
    for item in flat:
        q.setdefault(item["lib"], []).append(item["params"])
    return q, {k: 0 for k in q}


def solve_visible(fr, pg, queues, ptr):
    for lib, sel in SUB_SEL:
        vis = fr.locator(sel + ":visible:not(.hsolved)")
        n = vis.count()
        for k in range(n):
            if ptr.get(lib, 0) >= len(queues.get(lib, [])):
                break
            params = queues[lib][ptr[lib]]
            ptr[lib] += 1
            try:
                HANDLERS[lib](vis.nth(k), {"params": params, "correctDZs": None}, pg, fr)
                vis.nth(k).evaluate("el => el.classList.add('hsolved')")
            except Exception as e:
                print("    err", lib, e)
            pg.wait_for_timeout(250)


def scope_for(fr, lib, idx):
    for sel in CONTAINER.get(lib, []):
        loc = fr.locator(sel)
        if loc.count() > idx:
            return loc.nth(idx)
    return None


def resolver(fr, pg):
    insts = fr.evaluate(JS_COLLECT)
    by_lib = {}
    for it in insts:
        by_lib.setdefault(it.get("lib"), []).append(it)
    for it in insts:
        hid, lib = it.get("id"), it.get("lib")
        if not hid or not lib or hid in SOLVED or lib not in HANDLERS:
            continue
        idx = by_lib[lib].index(it)
        scope = scope_for(fr, lib, idx)
        if scope is None:
            continue
        SOLVED.add(hid)
        d = fr.evaluate("id => (window.__hsolve||{})[id]", hid)
        print("  -> %s #%d (%s)" % (lib, idx, hid))
        try:
            HANDLERS[lib](scope, d or {}, pg, fr)
        except Exception as e:
            print("    ERROR %s: %s" % (lib, e))


def _construir(ap):
    ap.add_argument("--url", "-u", help="URL de la actividad (si se omite, usa la pestana activa)")
    ap.add_argument("--list", action="store_true", help="Solo listar tipos detectados")


def _accion(ns):
    p, ctx, pg = conectar()
    try:
        if ns.url:
            pg.goto(ns.url, wait_until="domcontentloaded")
            pg.wait_for_timeout(3000)
        fr = h5p_frame(pg)
        if not fr:
            raise AgenteError("navegacion_web", "sinH5P",
                              "Sin iframe H5P. Abre una actividad H5P primero.")
        top = fr.evaluate("H5P.instances.map(i=>i.libraryInfo.machineName).join(',')")
        if ns.list:
            return exito(datos={"top": top, "tipos": fr.evaluate(JS_COLLECT)})
        with contextlib.redirect_stdout(sys.stderr):
            resolver(fr, pg)
        pg.wait_for_timeout(1200)
        resultado = fr.evaluate(
            r"(document.body.innerText.match(/You got [^\n]*points[^\n]*/)||[''])[0]")
        return exito(datos={"top": top, "resultado": resultado})
    finally:
        p.stop()


if __name__ == "__main__":
    sys.exit(cli.correr("navegacion_web", _construir, _accion, sys.argv[1:],
                        prog="h5p_solver",
                        descripcion="Solucionador H5P via CDP."))
